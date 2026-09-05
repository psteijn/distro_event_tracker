. (Join-Path $PSScriptRoot 'ssh_transport.ps1')

function Assert-DistroRuntime {
    $command = @'
test "$(id -un)" = psteijn
test "$HOME" = /home/psteijn
cd "$HOME"
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"
test -S "$XDG_RUNTIME_DIR/bus"
systemctl --user show-environment >/dev/null
test "$(podman info --format '{{.Host.Security.Rootless}}')" = true
'@
    Invoke-ServerCommand -User psteijn -Command $command | Out-Null
}

function Invoke-DistroAdmin {
    param([Parameter(Mandatory)][string]$Command)
    # Command is a Bash script executed as root; stdin avoids nested shell quoting.
    Invoke-ServerCommand -User codex -Command 'test "$(id -un)" = codex; sudo -n bash -se' -StandardInput $Command.Replace("`r", '')
}

function Invoke-DistroRuntime {
    param([Parameter(Mandatory)][string]$Command)
    $context = @'
test "$(id -un)" = psteijn
test "$HOME" = /home/psteijn
cd "$HOME"
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"
'@
    Invoke-ServerCommand -User psteijn -Command ($context + "`n" + $Command)
}
