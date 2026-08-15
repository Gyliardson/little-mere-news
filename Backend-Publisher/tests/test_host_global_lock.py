import shutil
import subprocess
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


def test_two_launcher_processes_from_different_checkouts_share_one_host_lock(tmp_path):
    """Forced Test C: parent holds the shared lock while a child checkout must fail closed."""
    pwsh = shutil.which("pwsh")
    assert pwsh is not None, "GitHub runner must provide pwsh for Hyper-V contract tests"

    checkout_a = tmp_path / "clone-a"
    checkout_b = tmp_path / "clone-b"
    lock_root = tmp_path / "host-global-lock-root"
    path_a_file = tmp_path / "path-a.txt"
    path_b_file = tmp_path / "path-b.txt"
    contender_file = tmp_path / "contender.ps1"
    recovery_file = tmp_path / "recovery.ps1"
    orchestrator_file = tmp_path / "orchestrator.ps1"
    checkout_a.mkdir()
    checkout_b.mkdir()

    resources = ", ".join(ps_quote(resource) for resource in RESOURCES)
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
    recovery_file.write_text(
        f"""$ErrorActionPreference = 'Stop'
. {ps_quote(HELPER)}
$resources = @({resources})
$lock = Enter-LmnHostLock -ResourceIds $resources -LockRootOverride {ps_quote(lock_root)}
try {{ exit 0 }} finally {{ $lock.Dispose() }}
""",
        encoding="utf-8",
    )
    orchestrator_file.write_text(
        f"""$ErrorActionPreference = 'Stop'
. {ps_quote(HELPER)}
$resources = @({resources})
$root = {ps_quote(lock_root)}
$pwsh = {ps_quote(pwsh)}
Set-Location {ps_quote(checkout_a)}
$pathA = Get-LmnHostLockPath -ResourceIds $resources -LockRootOverride $root
Set-Content -LiteralPath {ps_quote(path_a_file)} -Value $pathA -NoNewline
$holder = Enter-LmnHostLock -ResourceIds $resources -LockRootOverride $root
try {{
    # Forced interleaving: this independent pwsh process is invoked synchronously
    # only after the holder already owns the shared resource lock. There is no
    # scheduler/time-based marker to wait for.
    & $pwsh -NoProfile -NonInteractive -File {ps_quote(contender_file)}
    if ($LASTEXITCODE -ne 0) {{ throw "contender did not fail closed while holder owned the lock (exit $LASTEXITCODE)" }}
}} finally {{
    $holder.Dispose()
}}

$pathB = Get-Content -LiteralPath {ps_quote(path_b_file)} -Raw
if ($pathA -ne $pathB) {{ throw 'same remote resources produced checkout-specific lock paths' }}

# After explicit release, another independent process must be able to acquire the
# same resource lock. This proves serialization rather than a permanently wedged file.
& $pwsh -NoProfile -NonInteractive -File {ps_quote(recovery_file)}
if ($LASTEXITCODE -ne 0) {{ throw "lock was not recoverable after release (exit $LASTEXITCODE)" }}
""",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [pwsh, "-NoProfile", "-NonInteractive", "-File", str(orchestrator_file)],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert path_a_file.read_text(encoding="utf-8") == path_b_file.read_text(encoding="utf-8")
    assert "batch-" in path_a_file.read_text(encoding="utf-8")


def test_host_lock_default_is_not_repository_relative():
    text = HELPER.read_text(encoding="utf-8")
    assert "CommonApplicationData" in text
    assert "$ProjectRoot" not in text
    assert "FileShare]::None" in text
