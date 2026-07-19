[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$SyncSecrets,
    [switch]$SecretsOnly,
    [ValidatePattern('^[0-9a-f]{40}$')]
    [string]$Rollback
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$RepoRoot = $PSScriptRoot
$SshTarget = 'steijnserver'
$ReleaseBase = '/srv/releases/distro-event-tracker'
$Namespace = 'distro-event-tracker'

if ($DryRun -and ($SyncSecrets -or $SecretsOnly)) {
    throw '-DryRun cannot be combined with a secret-changing option.'
}
if ($SecretsOnly -and $Rollback) {
    throw '-SecretsOnly cannot be combined with -Rollback.'
}

function Invoke-Native {
    param([scriptblock]$Command, [string]$FailureMessage)
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$FailureMessage (exit code $LASTEXITCODE)"
    }
}

function Invoke-Remote {
    param([Parameter(Mandatory)][string]$Command)
    & ssh -o BatchMode=yes $SshTarget $Command
    if ($LASTEXITCODE -ne 0) {
        throw "Remote command failed (exit code $LASTEXITCODE)."
    }
}

function Sync-KubernetesSecret {
    param(
        [Parameter(Mandatory)][string]$Instance,
        [Parameter(Mandatory)][string]$EnvFile
    )

    if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) {
        throw "Missing local environment file for $Instance."
    }

    $secretName = "distro-event-tracker-$Instance"
    $remoteCommand = "microk8s kubectl -n $Namespace create secret generic $secretName --from-env-file=/dev/stdin --dry-run=client -o yaml | microk8s kubectl apply -f -"
    $sshPath = (Get-Command ssh -ErrorAction Stop).Source
    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $sshPath
    $startInfo.Arguments = "-o BatchMode=yes $SshTarget `"$remoteCommand`""
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardInput = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.CreateNoWindow = $true

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    if (-not $process.Start()) {
        throw "Unable to start SSH for $Instance secret synchronization."
    }

    $content = [System.IO.File]::ReadAllText($EnvFile)
    $process.StandardInput.Write($content)
    $process.StandardInput.Close()
    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()

    if ($process.ExitCode -ne 0) {
        throw "Secret synchronization failed for $Instance`: $stderr"
    }
    if ($stdout.Trim()) {
        Write-Host $stdout.Trim()
    }
}

function Sync-AllSecrets {
    Sync-KubernetesSecret -Instance 'distro' -EnvFile (Join-Path $RepoRoot '.env.distro')
    Sync-KubernetesSecret -Instance 'ocean' -EnvFile (Join-Path $RepoRoot '.env.ocean')
}

Push-Location $RepoRoot
try {
    Invoke-Remote 'true'

    if ($SecretsOnly) {
        Sync-AllSecrets
        Invoke-Remote "microk8s kubectl -n $Namespace rollout restart deployment/distro-event-tracker-distro deployment/distro-event-tracker-ocean && microk8s kubectl -n $Namespace rollout status deployment/distro-event-tracker-distro --timeout=600s && microk8s kubectl -n $Namespace rollout status deployment/distro-event-tracker-ocean --timeout=600s"
        Write-Host 'Secrets synchronized and both bot deployments restarted successfully.'
        exit 0
    }

    if ($Rollback) {
        $releasePath = "$ReleaseBase/$Rollback"
        $currentHelper = "$ReleaseBase/current/ops/k8s/deploy.sh"
        Invoke-Remote "test -f '$releasePath/.release-revision' && test -f '$currentHelper' && RELEASE_ROOT='$releasePath' bash '$currentHelper' '$Rollback'"
        exit 0
    }

    $dirty = (& git status --porcelain)
    if ($LASTEXITCODE -ne 0) { throw 'Unable to read Git status.' }
    if ($dirty) { throw 'The working tree must be clean before deployment.' }

    Invoke-Native { git fetch origin main --quiet } 'Unable to fetch origin/main'
    $revision = (& git rev-parse HEAD).Trim()
    $originRevision = (& git rev-parse origin/main).Trim()
    if ($revision -ne $originRevision) {
        throw "HEAD must equal origin/main before deployment. HEAD=$revision origin/main=$originRevision"
    }
    if ($revision -notmatch '^[0-9a-f]{40}$') {
        throw 'Git did not return a full commit SHA.'
    }

    Invoke-Native { & (Join-Path $RepoRoot 'check.bat') } 'Local validation failed'

    if ($SyncSecrets) {
        Sync-AllSecrets
    }

    $tempDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("distro-event-tracker-" + [guid]::NewGuid())
    [System.IO.Directory]::CreateDirectory($tempDirectory) | Out-Null
    try {
        $archive = Join-Path $tempDirectory "$revision.tar"
        Invoke-Native { git archive --format=tar --output=$archive HEAD } 'Unable to create release archive'

        $remoteArchive = "/home/psteijn/$revision.tar"
        Invoke-Native { scp -q -- $archive "${SshTarget}:$remoteArchive" } 'Unable to transfer release archive'
        $stageCommand = "set -eu; base='$ReleaseBase'; final=`"`$base/$revision`"; incoming=`"`$base/.incoming-$revision`"; mkdir -p `"`$base`"; if [ ! -d `"`$final`" ]; then rm -rf -- `"`$incoming`"; mkdir -p `"`$incoming`"; tar -xf '$remoteArchive' -C `"`$incoming`"; printf '%s\n' '$revision' > `"`$incoming/.release-revision`"; mv `"`$incoming`" `"`$final`"; fi; rm -f -- '$remoteArchive'; bash `"`$final/ops/k8s/deploy.sh`" '$revision'"
        if ($DryRun) {
            $stageCommand += ' --dry-run'
        }
        Invoke-Remote $stageCommand
    }
    finally {
        if (Test-Path -LiteralPath $tempDirectory) {
            Remove-Item -LiteralPath $tempDirectory -Recurse -Force
        }
    }
}
finally {
    Pop-Location
}
