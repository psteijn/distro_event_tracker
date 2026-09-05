[CmdletBinding()]
param([switch]$TransferProbe)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'ssh_transport.ps1')
Invoke-ServerCommand -User codex -Command 'test "$(id -un)" = codex; test "$(sudo -n id -u)" = 0; sudo -n journalctl -n 1 --no-pager >/dev/null' | Out-Null
Invoke-ServerCommand -User psteijn -Command 'test "$(id -un)" = psteijn; test -w /home/psteijn' | Out-Null
$failure = Invoke-ServerCommand -User codex -Command 'false; echo failure-was-masked' -AllowFailure
if ($failure.ExitCode -eq 0 -or $failure.Stdout) { throw 'Remote failure propagation is broken.' }
Write-Host 'Explicit login, protected journal access, staging permissions and fail-fast behavior verified.'
if (-not $TransferProbe) { exit 0 }

$id = [guid]::NewGuid().ToString('N')
$local = Join-Path ([IO.Path]::GetTempPath()) "transport probe $id.txt"
$download = Join-Path ([IO.Path]::GetTempPath()) "transport download $id.txt"
$remote = "/home/psteijn/.transport-probe-$id.txt"
try {
    [IO.File]::WriteAllText($local, "Non-secret SSH transport probe $id", (New-Object Text.UTF8Encoding($false)))
    Copy-ServerFile -User psteijn -LocalPath $local -RemotePath $remote
    Copy-ServerFile -User psteijn -LocalPath $download -RemotePath $remote -Download
    if ((Get-FileHash -LiteralPath $local).Hash -ne (Get-FileHash -LiteralPath $download).Hash) {
        throw 'Transfer round-trip checksum mismatch.'
    }
    Write-Host 'Non-secret upload/download checksums match.'
}
finally {
    $cleanup = Invoke-ServerCommand -User psteijn -Command "rm -f -- '$remote'" -AllowFailure
    foreach ($file in @($local, $download)) {
        if (Test-Path -LiteralPath $file) { Remove-Item -LiteralPath $file -Force }
    }
    if ($cleanup.ExitCode -ne 0) { throw "Unable to remove probe: $remote" }
}
Write-Host 'Only the disposable probe files were removed.'
