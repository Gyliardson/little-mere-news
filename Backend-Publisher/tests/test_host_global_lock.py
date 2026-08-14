import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER = REPO_ROOT / "Infrastructure" / "Lmn-HostLock.ps1"
RESOURCES = ["LMN-Harvester", "LMN-Brain", "LMN-Publisher"]


def ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def test_two_checkouts_targeting_same_vms_share_one_host_lock(tmp_path):
    """Forced Test C: clone/worktree location cannot create a distinct lock domain."""
    pwsh = shutil.which("pwsh")
    assert pwsh is not None, "GitHub runner must provide pwsh for Hyper-V contract tests"

    checkout_a = tmp_path / "clone-a"
    checkout_b = tmp_path / "clone-b"
    lock_root = tmp_path / "host-global-lock-root"
    checkout_a.mkdir()
    checkout_b.mkdir()

    resources = ", ".join(ps_quote(resource) for resource in RESOURCES)
    script = f"""
$ErrorActionPreference = 'Stop'
. {ps_quote(HELPER)}
$resources = @({resources})
$root = {ps_quote(lock_root)}
Set-Location {ps_quote(checkout_a)}
$pathA = Get-LmnHostLockPath -ResourceIds $resources -LockRootOverride $root
Set-Location {ps_quote(checkout_b)}
$pathB = Get-LmnHostLockPath -ResourceIds $resources -LockRootOverride $root
if ($pathA -ne $pathB) {{ throw 'same remote resources produced checkout-specific lock paths' }}
$first = Enter-LmnHostLock -ResourceIds $resources -LockRootOverride $root
try {{
    $overlapBlocked = $false
    try {{
        $second = Enter-LmnHostLock -ResourceIds $resources -LockRootOverride $root
        if ($null -ne $second) {{ $second.Dispose() }}
    }} catch [System.IO.IOException] {{
        $overlapBlocked = $true
    }}
    if (-not $overlapBlocked) {{ throw 'second checkout acquired overlapping shared-resource lock' }}
}} finally {{
    $first.Dispose()
}}
Write-Output $pathA
"""

    completed = subprocess.run(
        [pwsh, "-NoProfile", "-NonInteractive", "-Command", script],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert "batch-" in completed.stdout


def test_host_lock_default_is_not_repository_relative():
    text = HELPER.read_text(encoding="utf-8")
    assert "CommonApplicationData" in text
    assert "$ProjectRoot" not in text
    assert "FileShare]::None" in text
