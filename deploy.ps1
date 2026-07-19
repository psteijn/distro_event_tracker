[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$SyncSecrets,
    [switch]$SecretsOnly,
    [switch]$StageOnly,
    [ValidatePattern('^[0-9a-f]{40}$')]
    [string]$Rollback
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$RepoRoot = $PSScriptRoot
$SshTarget = 'steijnserver'
$ReleaseBase = '/srv/releases/distro-event-tracker'

if ($DryRun -and ($SyncSecrets -or $SecretsOnly -or $StageOnly -or $Rollback)) {
    throw '-DryRun cannot be combined with a secret-changing option, -StageOnly, or -Rollback.'
}
if ($SecretsOnly -and ($StageOnly -or $Rollback)) {
    throw '-SecretsOnly cannot be combined with -StageOnly or -Rollback.'
}

function Invoke-Native {
    param([scriptblock]$Command, [string]$FailureMessage)
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$FailureMessage (exit code $LASTEXITCODE)" }
}

function Invoke-Remote {
    param([Parameter(Mandatory)][string]$Command)
    & ssh -o BatchMode=yes $SshTarget $Command
    if ($LASTEXITCODE -ne 0) { throw "Remote command failed (exit code $LASTEXITCODE)." }
}

function Sync-PodmanEnvironment {
    param(
        [Parameter(Mandatory)][ValidateSet('distro', 'ocean')][string]$Instance,
        [Parameter(Mandatory)][string]$EnvFile
    )
    if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) {
        throw "Missing local environment file for $Instance."
    }

    $remoteCommand = 'set -eu; dir="$HOME/.config/distro-event-tracker"; install -d -m 700 "$dir"; umask 077; tmp="$dir/.{0}.env.tmp"; tr -d ''\r'' > "$tmp"; chmod 600 "$tmp"; mv -f "$tmp" "$dir/{0}.env"' -f $Instance
    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = (Get-Command ssh -ErrorAction Stop).Source
    $startInfo.Arguments = '-o BatchMode=yes {0} "{1}"' -f $SshTarget, $remoteCommand
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardInput = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.CreateNoWindow = $true

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    if (-not $process.Start()) { throw "Unable to start SSH for $Instance configuration synchronization." }
    $process.StandardInput.Write([System.IO.File]::ReadAllText($EnvFile))
    $process.StandardInput.Close()
    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()
    if ($process.ExitCode -ne 0) {
        throw ('Configuration synchronization failed for {0}: {1}' -f $Instance, $stderr)
    }
    if ($stdout.Trim()) { Write-Host $stdout.Trim() }
}

function Sync-AllEnvironments {
    Sync-PodmanEnvironment -Instance distro -EnvFile (Join-Path $RepoRoot '.env.distro')
    Sync-PodmanEnvironment -Instance ocean -EnvFile (Join-Path $RepoRoot '.env.ocean')
}

function Get-ReleaseRevision {
    $dirty = (& git status --porcelain)
    if ($LASTEXITCODE -ne 0) { throw 'Unable to read Git status.' }
    if ($dirty) { throw 'The working tree must be clean before deployment.' }
    Invoke-Native { git fetch origin main --quiet } 'Unable to fetch origin/main'
    $revision = (& git rev-parse HEAD).Trim()
    $originRevision = (& git rev-parse origin/main).Trim()
    if ($revision -ne $originRevision) {
        throw "HEAD must equal origin/main before deployment. HEAD=$revision origin/main=$originRevision"
    }
    if ($revision -notmatch '^[0-9a-f]{40}$') { throw 'Git did not return a full commit SHA.' }
    return $revision
}

function Send-ReleaseArchive {
    param([string]$Revision, [bool]$Temporary)
    $tempDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("distro-event-tracker-" + [guid]::NewGuid())
    [System.IO.Directory]::CreateDirectory($tempDirectory) | Out-Null
    try {
        $archive = Join-Path $tempDirectory "$Revision.tar"
        Invoke-Native { git archive --format=tar --output=$archive $Revision } 'Unable to create release archive'
        $remoteArchive = "/home/psteijn/$Revision.tar"
        Invoke-Native { scp -q -- $archive ($SshTarget + ':' + $remoteArchive) } 'Unable to transfer release archive'
        if ($Temporary) {
            $command = 'set -eu; archive=''{0}''; work=$(mktemp -d); trap ''rm -rf -- "$work" "$archive"'' EXIT; tar -xf "$archive" -C "$work"; echo -n ''{1}'' > "$work/.release-revision"; RELEASE_ROOT="$work" bash "$work/ops/podman/deploy.sh" ''{1}'' --dry-run' -f $remoteArchive, $Revision
            Invoke-Remote $command
            return
        }
        $command = 'set -eu; base=''{0}''; final="$base/{1}"; incoming="$base/.incoming-{1}"; mkdir -p "$base"; if [ ! -d "$final" ]; then rm -rf -- "$incoming"; mkdir -p "$incoming"; tar -xf ''{2}'' -C "$incoming"; echo -n ''{1}'' > "$incoming/.release-revision"; mv "$incoming" "$final"; fi; rm -f -- ''{2}''' -f $ReleaseBase, $Revision, $remoteArchive
        Invoke-Remote $command
    }
    finally {
        if (Test-Path -LiteralPath $tempDirectory) {
            Remove-Item -LiteralPath $tempDirectory -Recurse -Force
        }
    }
}

Push-Location $RepoRoot
try {
    Invoke-Remote 'true'
    if ($SecretsOnly) {
        Sync-AllEnvironments
        $command = 'set -eu; root=''{0}/current''; source "$root/ops/podman/common.sh"; for instance in distro ocean; do systemctl --user restart "$(service_name "$instance")"; wait_for_bot "$instance"; done' -f $ReleaseBase
        Invoke-Remote $command
        Write-Host 'Configuration synchronized and both Podman bot services restarted successfully.'
        exit 0
    }
    if ($Rollback) {
        $releasePath = "$ReleaseBase/$Rollback"
        Invoke-Remote ('test -f ''{0}/.release-revision'' && RELEASE_ROOT=''{0}'' bash ''{0}/ops/podman/deploy.sh'' ''{1}''' -f $releasePath, $Rollback)
        exit 0
    }

    $revision = Get-ReleaseRevision
    Invoke-Native { & (Join-Path $RepoRoot 'check.bat') } 'Local validation failed'
    if ($SyncSecrets) { Sync-AllEnvironments }
    if ($DryRun) {
        Send-ReleaseArchive -Revision $revision -Temporary $true
        exit 0
    }
    Send-ReleaseArchive -Revision $revision -Temporary $false
    $releasePath = "$ReleaseBase/$revision"
    $mode = if ($StageOnly) { ' --stage-only' } else { '' }
    Invoke-Remote ("RELEASE_ROOT='{0}' bash '{0}/ops/podman/deploy.sh' '{1}'{2}" -f $releasePath, $revision, $mode)
}
finally {
    Pop-Location
}
