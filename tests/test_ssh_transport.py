"""Behavioral tests for the standalone Windows SSH transport contract."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "ops/ssh_transport.ps1"
POWERSHELL = shutil.which("powershell.exe")
pytestmark = pytest.mark.skipif(
    os.name != "nt" or not POWERSHELL, reason="Windows PowerShell transport"
)


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def run_ps(tmp_path, body):
    script = tmp_path / "harness with spaces.ps1"
    script.write_text(
        "$ErrorActionPreference = 'Stop'\n" f". {quote(HELPER)}\n{body}\n",
        encoding="utf-8-sig",
    )
    return subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_native_arguments_and_streamed_utf8_input(tmp_path):
    child = tmp_path / "child with spaces.py"
    child.write_text(
        "import json, sys\n"
        "print(json.dumps([sys.argv[1:], sys.stdin.buffer.read().decode('utf-8')]))\n",
        encoding="utf-8",
    )
    arguments = [
        str(child),
        r"C:\Users\Peter Steijn\.ssh\steijnserver_codex",
        'embedded "quote"',
        "trailing space\\",
        "",
        "$(not executed); $HOME",
    ]
    stdin = "non-secret café\nsecond line\n"
    result = run_ps(
        tmp_path,
        f"$r = Invoke-SshProcess -Executable {quote(sys.executable)} "
        f"-Arguments @({','.join(quote(arg) for arg in arguments)}) "
        f"-StandardInput ({quote(stdin)}.Replace(\"`r\", ''))\n$r.Stdout",
    )
    assert result.returncode == 0, result.stderr
    argv, received = json.loads(result.stdout)
    assert argv == arguments[1:]
    assert received == stdin


@pytest.mark.parametrize("allow_failure", [False, True])
def test_remote_error_is_not_hidden(tmp_path, allow_failure):
    child = tmp_path / "fail.py"
    child.write_text(
        "import sys\nsys.stderr.write('failure-marker')\nsys.exit(23)\n",
        encoding="utf-8",
    )
    flag = " -AllowFailure" if allow_failure else ""
    result = run_ps(
        tmp_path,
        f"$r = Invoke-SshProcess -Executable {quote(sys.executable)} "
        f"-Arguments @({quote(child)}){flag}\n"
        "$r | ConvertTo-Json -Compress",
    )
    if allow_failure:
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["ExitCode"] == 23
        assert data["Stderr"] == "failure-marker"
    else:
        assert result.returncode != 0
        assert "failure-marker" in result.stderr
        assert "23" in result.stderr


@pytest.mark.parametrize("user", ["codex", "psteijn"])
def test_ssh_scp_and_streaming_always_select_explicit_account(tmp_path, user):
    capture = tmp_path / "calls.jsonl"
    local_path = str(tmp_path / "upload with spaces.txt")
    body = (
        "function Invoke-SshProcess {\n"
        "param($Executable, $Arguments, $StandardInput, [switch]$AllowFailure)\n"
        "@{exe=$Executable; argv=$Arguments; stdin=$StandardInput} "
        f"| ConvertTo-Json -Compress | Add-Content -LiteralPath {quote(capture)}\n"
        "[pscustomobject]@{ExitCode=0; Stdout=''; Stderr=''}\n}\n"
        f"Invoke-ServerCommand -User {user} -Command 'false; echo unreachable' "
        "-StandardInput 'stream-marker' | Out-Null\n"
        f"Copy-ServerFile -User {user} -LocalPath {quote(local_path)} "
        "-RemotePath '/tmp/transport-probe'\n"
        f"Copy-ServerFile -User {user} -LocalPath {quote(local_path)} "
        "-RemotePath '/tmp/transport-probe' -Download\n"
    )
    result = run_ps(tmp_path, body)
    assert result.returncode == 0, result.stderr
    calls = [json.loads(line) for line in capture.read_text().splitlines()]
    assert [call["exe"] for call in calls] == ["ssh.exe", "scp.exe", "scp.exe"]
    for call in calls:
        args = call["argv"]
        for option in (
            "BatchMode=yes",
            "StrictHostKeyChecking=yes",
            "ConnectTimeout=10",
            "IdentitiesOnly=yes",
            f"User={user}",
        ):
            index = args.index(option)
            assert args[index - 1] == "-o"
        assert "-tt" not in args
    assert calls[0]["argv"][-2] == "steijnserver"
    assert calls[0]["argv"][-1] == "set -eu\nfalse; echo unreachable"
    assert calls[0]["stdin"] == "stream-marker"
    assert calls[1]["argv"][-2:] == [local_path, "steijnserver:/tmp/transport-probe"]
    assert calls[2]["argv"][-2:] == ["steijnserver:/tmp/transport-probe", local_path]


@pytest.mark.parametrize("user", ["codex", "psteijn"])
def test_alias_default_user_cannot_override_role(tmp_path, user):
    config = tmp_path / "isolated ssh config"
    config.write_text(
        "Host steijnserver\n  HostName 127.0.0.1\n  User wrong-account\n",
        encoding="ascii",
    )
    result = run_ps(
        tmp_path,
        f"$arguments = @(Get-ServerSshArguments -User {user}) "
        f"+ @('-F', {quote(config)}, '-G', 'steijnserver')\n"
        "(Invoke-SshProcess -Executable ssh.exe -Arguments $arguments).Stdout",
    )
    assert result.returncode == 0, result.stderr
    assert f"user {user}" in result.stdout.splitlines()
    assert "batchmode yes" in result.stdout.splitlines()
    assert "stricthostkeychecking true" in result.stdout.splitlines()


def test_all_operational_powershell_scripts_parse(tmp_path):
    result = run_ps(
        tmp_path,
        f"$files = @(Get-ChildItem -LiteralPath {quote(ROOT / 'ops')} "
        "-Recurse -Filter '*.ps1')\n"
        f"$files += @(Get-ChildItem -LiteralPath {quote(ROOT)} -Filter '*.ps1')\n"
        "foreach ($file in $files) {\n"
        "  $tokens = $null; $errors = $null\n"
        "  [System.Management.Automation.Language.Parser]::ParseFile("
        "$file.FullName, [ref]$tokens, [ref]$errors) | Out-Null\n"
        "  if ($errors) { throw ($file.FullName + ': ' + ($errors -join '; ')) }\n"
        "}\n",
    )
    assert result.returncode == 0, result.stderr
