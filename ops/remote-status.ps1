[CmdletBinding()]
param(
    [ValidatePattern('^[0-9]+[smhd]$')]
    [string]$Since = '1h'
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'remote.ps1')
Assert-DistroRuntime
$script = @'
set -eu
cd "$HOME"
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"
since="$1"
echo "ROOTLESS_USER_MANAGER"
loginctl show-user "$(id -un)" -p Linger
for instance in distro ocean; do
  service="distro-event-tracker-$instance.service"
  container="distro-event-tracker-$instance"
  echo "BOT $instance"
  systemctl --user show "$service" -p ActiveState -p SubState -p NRestarts --no-pager
  podman inspect --format 'image={{.ImageName}} revision={{index .Config.Labels "org.opencontainers.image.revision"}} health={{.State.Health.Status}} started={{.State.StartedAt}}' "$container"
  podman port "$container"
  data_file="$HOME/.local/share/distro-event-tracker/$instance/reminders_opt_out.txt"
  if [[ -f "$data_file" ]]; then
    stat -c 'data_mode=%a data_owner=%u:%g data_bytes=%s' "$data_file"
    sha256sum "$data_file" | awk '{print "data_sha256=" $1}'
  fi
  recent_logs="$(podman logs --since "$since" "$container" 2>&1 || true)"
  latest_connection="$(printf '%s\n' "$recent_logs" | grep -F 'has connected to Discord!' | tail -n 1 || true)"
  latest_progress="$(printf '%s\n' "$recent_logs" | grep -F 'Reconstruction progress:' | tail -n 1 || true)"
  reconstructed_events="$(printf '%s\n' "$recent_logs" | grep -Fc 'Reconstructed event:' || true)"
  echo "latest_discord_connection=${latest_connection:-none}"
  echo "latest_reconstruction_progress=${latest_progress:-none}"
  echo "reconstructed_events_since=$reconstructed_events"
  echo "RECENT_SIGNALS $instance"
  printf '%s\n' "$recent_logs" \
    | grep -Ei 'connected to Discord|fully initialized|warning|error|exception|traceback|name or service not known|temporary failure in name resolution' \
    | tail -n 100 || true
done
echo "RELATED_SYSTEM_SERVICES"
for unit in homeassistant.service piper.service zwave-js-ui.service; do
  systemctl show "$unit" -p Id -p ActiveState -p SubState --no-pager
done
echo "MICROK8S"
if snap list microk8s >/dev/null 2>&1; then
  echo "installed"
else
  echo "absent"
fi
'@

(Invoke-ServerCommand -User psteijn -Command "bash -se -- $Since" -StandardInput $script.Replace("`r", '')).Stdout | Write-Host
