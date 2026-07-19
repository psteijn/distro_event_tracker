[CmdletBinding()]
param(
    [ValidatePattern('^[0-9]+[smhd]$')]
    [string]$Since = '1h'
)

$ErrorActionPreference = 'Stop'
$script = @'
set -u
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
  echo "RECENT_SIGNALS $instance"
  podman logs --since "$since" "$container" 2>&1 \
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

$startInfo = [System.Diagnostics.ProcessStartInfo]::new()
$startInfo.FileName = (Get-Command ssh -ErrorAction Stop).Source
$startInfo.Arguments = "-o BatchMode=yes steijnserver bash -s -- $Since"
$startInfo.UseShellExecute = $false
$startInfo.RedirectStandardInput = $true
$startInfo.RedirectStandardOutput = $true
$startInfo.RedirectStandardError = $true
$startInfo.CreateNoWindow = $true
$process = [System.Diagnostics.Process]::new()
$process.StartInfo = $startInfo
if (-not $process.Start()) { throw 'Unable to start remote status check.' }
$process.StandardInput.Write($script)
$process.StandardInput.Close()
$stdout = $process.StandardOutput.ReadToEnd()
$stderr = $process.StandardError.ReadToEnd()
$process.WaitForExit()
if ($stdout) { Write-Host $stdout.TrimEnd() }
if ($process.ExitCode -ne 0) {
    throw "Remote status check failed (exit code $($process.ExitCode)): $stderr"
}
