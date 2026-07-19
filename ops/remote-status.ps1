[CmdletBinding()]
param(
    [ValidatePattern('^[0-9]+[smhd]$')]
    [string]$Since = '1h'
)

$ErrorActionPreference = 'Stop'
$namespace = 'distro-event-tracker'
$command = "microk8s kubectl -n $namespace get deployments,pods,pvc -o wide; microk8s kubectl -n $namespace get events --field-selector type=Warning --sort-by=.lastTimestamp; microk8s kubectl -n $namespace logs deployment/distro-event-tracker-distro --since=$Since --tail=200; microk8s kubectl -n $namespace logs deployment/distro-event-tracker-ocean --since=$Since --tail=200"
& ssh -o BatchMode=yes steijnserver $command
if ($LASTEXITCODE -ne 0) {
    throw "Remote status check failed (exit code $LASTEXITCODE)."
}
