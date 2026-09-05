# Standalone transport contract: explicit SSH identity, no prompts, exact exit status.
# Keep this copy local to this repository; do not dot-source a sibling checkout.
Set-StrictMode -Version Latest

function ConvertTo-NativeArgument {
    param([AllowEmptyString()][string]$Value)
    # Windows CommandLineToArgvW quoting, including embedded quotes and trailing slashes.
    '"' + [regex]::Replace([regex]::Replace($Value, '(\\*)"', '$1$1\"'), '(\\+)$', '$1$1') + '"'
}

function Invoke-SshProcess {
    param(
        [Parameter(Mandatory)][string]$Executable,
        [string[]]$Arguments,
        [AllowEmptyString()][string]$StandardInput = '',
        [switch]$AllowFailure
    )
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = (Get-Command $Executable -ErrorAction Stop).Source
    $info.Arguments = ($Arguments | ForEach-Object { ConvertTo-NativeArgument $_ }) -join ' '
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardInput = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $info.StandardOutputEncoding = New-Object System.Text.UTF8Encoding($false)
    $info.StandardErrorEncoding = New-Object System.Text.UTF8Encoding($false)
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $info
    try {
        if (-not $process.Start()) { throw "Unable to launch $Executable." }
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        # BaseStream also works on Windows PowerShell 5.1/.NET Framework.
        $inputBytes = [System.Text.Encoding]::UTF8.GetBytes($StandardInput)
        try { $process.StandardInput.BaseStream.Write($inputBytes, 0, $inputBytes.Length) }
        finally { $process.StandardInput.Close() }
        $process.WaitForExit()
        $result = [pscustomobject]@{
            ExitCode = $process.ExitCode
            Stdout = $stdoutTask.GetAwaiter().GetResult()
            Stderr = $stderrTask.GetAwaiter().GetResult()
        }
        if ($result.ExitCode -ne 0 -and -not $AllowFailure) {
            throw "$Executable failed (exit $($result.ExitCode)): $($result.Stderr.Trim())"
        }
        return $result
    }
    finally { $process.Dispose() }
}

function Get-ServerSshArguments {
    param([ValidateSet('codex', 'psteijn')][string]$User = 'codex')
    @('-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
      '-o', 'ConnectTimeout=10', '-o', 'IdentitiesOnly=yes', '-o', "User=$User")
}

function Invoke-ServerCommand {
    param(
        [Parameter(Mandatory)][string]$Command,
        [ValidateSet('codex', 'psteijn')][string]$User = 'codex',
        [AllowEmptyString()][string]$StandardInput = '',
        [switch]$AllowFailure
    )
    $remoteCommand = "set -eu`n" + $Command.Replace("`r", '')
    $arguments = @(Get-ServerSshArguments -User $User) + @('steijnserver', $remoteCommand)
    Invoke-SshProcess -Executable ssh.exe -Arguments $arguments -StandardInput $StandardInput -AllowFailure:$AllowFailure
}

function Copy-ServerFile {
    param(
        [Parameter(Mandatory)][string]$LocalPath,
        [Parameter(Mandatory)][string]$RemotePath,
        [ValidateSet('codex', 'psteijn')][string]$User = 'codex',
        [switch]$Download
    )
    $arguments = @(Get-ServerSshArguments -User $User) + @('-q', '--')
    if ($Download) { $arguments += @("steijnserver:$RemotePath", $LocalPath) }
    else { $arguments += @($LocalPath, "steijnserver:$RemotePath") }
    Invoke-SshProcess -Executable scp.exe -Arguments $arguments | Out-Null
}
