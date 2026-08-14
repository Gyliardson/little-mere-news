import shutil
import subprocess
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER = REPO_ROOT / "Infrastructure" / "Lmn-HostLock.ps1"
RESOURCES = [
    "hyperv:LMN-Harvester",
    "hyperv:LMN-Brain",
    "hyperv:LMN-Publisher",
    "ssh:10.0.100.10",
    "ssh:10.0.100.20",
    "ssh:10.0.100.30",
]


def ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def wait_for(path, process, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            return
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            raise AssertionError(f"lock holder exited before barrier: {stdout}\n{stderr}")
        time.sleep(0.05)
    stdout = stderr = ""
    if process.poll() is not None:
        stdout, stderr = process.communicate()
    raise AssertionError(
        f"timed out waiting for lock-holder barrier; rc={process.poll()} stdout={stdout} stderr={stderr}"
    )


def test_two_launcher_processes_from_different_checkouts_share_one_host_lock(tmp_path):
    """Forced Test C: two real pwsh launchers cannot overlap on the same VM resources."""
    pwsh = shutil.which("pwsh")
    assert pwsh is not None, "GitHub runner must provide pwsh for Hyper-V contract tests"

    checkout_a = tmp_path / "clone-a"
    checkout_b = tmp_path / "clone-b"
    lock_root = tmp_path / "host-global-lock-root"
    ready = tmp_path / "holder-ready"
    release = tmp_path / "holder-release"
    path_a_file = tmp_path / "path-a.txt"
    path_b_file = tmp_path / "path-b.txt"
    holder_file = tmp_path / "holder.ps1"
    contender_file = tmp_path / "contender.ps1"
    checkout_a.mkdir()
    checkout_b.mkdir()

    resources = ", ".join(ps_quote(resource) for resource in RESOURCES)
    holder_file.write_text(
        f"""$ErrorActionPreference = 'Stop'
. {ps_quote(HELPER)}
$resources = @({resources})
$root = {ps_quote(lock_root)}
Set-Location {ps_quote(checkout_a)}
$path = Get-LmnHostLockPath -ResourceIds $resources -LockRootOverride $root
Set-Content -LiteralPath {ps_quote(path_a_file)} -Value $path -NoNewline
$lock = Enter-LmnHostLock -ResourceIds $resources -LockRootOverride $root
try {{
    New-Item -ItemType File -Path {ps_quote(ready)} -Force | Out-Null
    $deadline = (Get-Date).AddSeconds(10)
    while (-not (Test-Path -LiteralPath {ps_quote(release)})) {{
        if ((Get-Date) -ge $deadline) {{ throw 'holder release barrier timed out' }}
        Start-Sleep -Milliseconds 50
    }}
}} finally {{
    $lock.Dispose()
}}
""",
        encoding="utf-8",
    )
    contender_file.write_text(
        f"""$ErrorActionPreference = 'Stop'
. {ps_quote(HELPER)}
$resources = @({resources})
$root = {ps_quote(lock_root)}
Set-Location {ps_quote(checkout_b)}
$path = Get-LmnHostLockPath -ResourceIds $resources -LockRootOverride $root
Set-Content -LiteralPath {ps_quote(path_b_file)} -Value $path -NoNewline
try {{
    $lock = Enter-LmnHostLock -ResourceIds $resources -LockRootOverride $root
    try {{ Write-Error 'overlap unexpectedly acquired' }} finally {{ $lock.Dispose() }}
    exit 9
}} catch [System.IO.IOException] {{
    exit 0
}}
""",
        encoding="utf-8",
    )

    holder = subprocess.Popen(
        [pwsh, "-NoProfile", "-NonInteractive", "-File", str(holder_file)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        wait_for(ready, holder)
        contender = subprocess.run(
            [pwsh, "-NoProfile", "-NonInteractive", "-File", str(contender_file)],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert contender.returncode == 0, contender.stderr or contender.stdout
        assert path_a_file.read_text(encoding="utf-8") == path_b_file.read_text(encoding="utf-8")
        assert "batch-" in path_a_file.read_text(encoding="utf-8")
    finally:
        release.write_text("release", encoding="utf-8")
        stdout, stderr = holder.communicate(timeout=10)
        assert holder.returncode == 0, stderr or stdout


def test_host_lock_default_is_not_repository_relative():
    text = HELPER.read_text(encoding="utf-8")
    assert "CommonApplicationData" in text
    assert "$ProjectRoot" not in text
    assert "FileShare]::None" in text
