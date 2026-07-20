[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$Cutover,
    [switch]$DecommissionMicroK8s
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$RepoRoot = Split-Path -Parent $PSScriptRoot
$SshTarget = 'steijnserver'

$selectedModes = @(@($DryRun, $Cutover, $DecommissionMicroK8s) | Where-Object { $_ })
if ($selectedModes.Count -ne 1) {
    throw 'Specify exactly one of -DryRun, -Cutover, or -DecommissionMicroK8s.'
}

function Invoke-Native {
    param([scriptblock]$Command, [string]$FailureMessage)
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$FailureMessage (exit code $LASTEXITCODE)" }
}

function Invoke-Remote {
    param([string]$Command)
    & ssh -o BatchMode=yes $SshTarget $Command
    if ($LASTEXITCODE -ne 0) { throw "Remote preflight or migration failed (exit code $LASTEXITCODE)." }
}

foreach ($envName in 'distro', 'ocean') {
    $envPath = Join-Path $RepoRoot ".env.$envName"
    if (-not (Test-Path -LiteralPath $envPath -PathType Leaf)) {
        throw "Missing local environment file .env.$envName."
    }
}

Push-Location $RepoRoot
try {
    $dirty = (& git status --porcelain)
    if ($LASTEXITCODE -ne 0) { throw 'Unable to read Git status.' }
    if ($dirty) { throw 'The working tree must be clean before migration.' }
    Invoke-Native { git fetch origin main --quiet } 'Unable to fetch origin/main'
    $revision = (& git rev-parse HEAD).Trim()
    $originRevision = (& git rev-parse origin/main).Trim()
    if ($revision -ne $originRevision) {
        throw "HEAD must equal origin/main before migration. HEAD=$revision origin/main=$originRevision"
    }

    $preflight = @'
set -eu
test "$(id -un)" = psteijn
test "$(podman info --format '{{.Host.Security.Rootless}}')" = true
test "$(podman info --format '{{.Host.CgroupsVersion}}')" = v2
version="$(podman version --format '{{.Client.Version}}')"
test "$(printf '%s\n' 5.7.0 "$version" | sort -V | head -n1)" = 5.7.0
test "$(df -Pk "$HOME" | awk 'NR==2 {print ($4 >= 1048576)}')" = 1
for instance in distro ocean; do
  test "$(microk8s kubectl -n distro-event-tracker get "deployment/distro-event-tracker-$instance" -o jsonpath='{.spec.replicas}')" = __EXPECTED_REPLICAS__
  if [ "__EXPECTED_REPLICAS__" = 1 ]; then
    microk8s kubectl -n distro-event-tracker wait --for=condition=Available "deployment/distro-event-tracker-$instance" --timeout=60s >/dev/null
  fi
  microk8s kubectl -n distro-event-tracker get "pvc/distro-event-tracker-$instance-data" >/dev/null
done
for unit in homeassistant.service piper.service zwave-js-ui.service; do
  systemctl is-active --quiet "$unit"
done
echo "Migration preflight passed for Podman $version."
'@
    $expectedReplicas = if ($DecommissionMicroK8s) { '0' } else { '1' }
    $preflight = $preflight.Replace('__EXPECTED_REPLICAS__', $expectedReplicas)
    Invoke-Remote $preflight

    if ($DryRun) {
        Invoke-Native {
            powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoRoot 'deploy.ps1') -DryRun
        } 'Podman deployment dry run failed'
        $linger = (& ssh -o BatchMode=yes $SshTarget 'loginctl show-user psteijn -p Linger --value').Trim()
        if ($LASTEXITCODE -ne 0) { throw 'Unable to inspect user lingering.' }
        Write-Host "Migration dry run passed. Current psteijn linger setting: $linger"
        exit 0
    }

    $linger = (& ssh -o BatchMode=yes $SshTarget 'loginctl show-user psteijn -p Linger --value').Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Unable to inspect user lingering.' }
    if ($linger -ne 'yes') {
        Write-Host 'Enabling the psteijn user manager at boot. SSH will request sudo authentication.'
        Invoke-Native {
            ssh -t $SshTarget 'sudo loginctl enable-linger psteijn'
        } 'Unable to enable user lingering'
    }
    Invoke-Remote 'test "$(loginctl show-user psteijn -p Linger --value)" = yes'

    if (-not $DecommissionMicroK8s) {
        Invoke-Native {
            powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoRoot 'deploy.ps1') -SyncSecrets -StageOnly
        } 'Unable to stage the Podman release and configuration'

        $releasePath = "/srv/releases/distro-event-tracker/$revision"
        $migrationEnv = if ($Cutover) { 'SKIP_FULL_INIT=1 ' } else { '' }
        Invoke-Remote ("RELEASE_ROOT='{0}' {1}bash '{0}/ops/podman/migrate.sh' '{2}'" -f $releasePath, $migrationEnv, $revision)
    } else {
        Invoke-Remote 'for instance in distro ocean; do podman inspect "distro-event-tracker-$instance" >/dev/null; done'
    }

    if ($Cutover) {
        $cutoverCheck = @'
set -eu
for instance in distro ocean; do
  test "$(microk8s kubectl -n distro-event-tracker get "deployment/distro-event-tracker-$instance" -o jsonpath='{.spec.replicas}')" = 0
  systemctl --user is-active --quiet "distro-event-tracker-$instance.service"
  if [ "__SKIP_HEALTH__" != "True" ]; then
    test "$(podman inspect --format '{{.State.Health.Status}}' "distro-event-tracker-$instance")" = healthy
  fi
done
test "$(loginctl show-user psteijn -p Linger --value)" = yes
snap list microk8s >/dev/null
for unit in homeassistant.service piper.service zwave-js-ui.service; do
  systemctl is-active --quiet "$unit"
done
echo "Podman cutover verified; MicroK8s remains installed for the Discord validation window."
'@
        $cutoverCheck = $cutoverCheck.Replace('__SKIP_HEALTH__', $Cutover.IsPresent.ToString())
        Invoke-Remote $cutoverCheck
        Write-Host 'Cutover complete. Both bots are running under Podman; MicroK8s was intentionally left installed for validation.'
        exit 0
    }

    $confirmation = Read-Host 'Both bots passed Podman verification. Type PURGE MICROK8S to permanently remove MicroK8s'
    if ($confirmation -cne 'PURGE MICROK8S') {
        throw 'MicroK8s purge was not confirmed. Bots remain healthy in Podman and Kubernetes replicas remain at zero.'
    }

    Write-Host 'Purging MicroK8s. SSH will request sudo authentication.'
    Invoke-Native {
        ssh -t $SshTarget 'sudo microk8s stop && sudo snap remove microk8s --purge'
    } 'MicroK8s purge failed'

    $postcheck = @'
set -eu
if snap list microk8s >/dev/null 2>&1; then
  echo "MicroK8s snap is still installed." >&2
  exit 1
fi
if pgrep -x kubelite >/dev/null || pgrep -x k8s-dqlite >/dev/null; then
  echo "MicroK8s processes are still running." >&2
  exit 1
fi
for instance in distro ocean; do
  systemctl --user is-active --quiet "distro-event-tracker-$instance.service"
  test "$(podman inspect --format '{{.State.Health.Status}}' "distro-event-tracker-$instance")" = healthy
done
for unit in homeassistant.service piper.service zwave-js-ui.service; do
  systemctl is-active --quiet "$unit"
done
echo "Podman migration verified and MicroK8s purged."
'@
    Invoke-Remote $postcheck
}
finally {
    Pop-Location
}
