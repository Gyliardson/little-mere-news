from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BATCH = ROOT / "Infrastructure" / "Run-LMN-Batch.ps1"
LAUNCHER = ROOT / "Infrastructure" / "Run-LMN.bat"
INSTALLER = ROOT / "Infrastructure" / "Install-LMN.ps1"


def test_official_launchers_run_from_infrastructure_directory():
    launcher = LAUNCHER.read_text(encoding="utf-8")
    installer = INSTALLER.read_text(encoding="utf-8")

    assert 'pushd "%~dp0"' in launcher
    assert "$Shortcut.WorkingDirectory = $InfrastructureDir" in installer


def test_batch_resolves_worker_sources_from_repository_root():
    script = BATCH.read_text(encoding="utf-8")

    assert "$ProjectRoot = Split-Path $PSScriptRoot -Parent" in script
    assert 'Join-Path $ProjectRoot "Backend-Harvester\\feeds.json"' in script
    assert 'Join-Path $ProjectRoot "Backend-Harvester\\main.py"' in script
    assert 'Join-Path $ProjectRoot "Backend-Publisher\\main.py"' in script
    assert 'scp @SshOptions ".\\Backend-Harvester' not in script
    assert 'scp @SshOptions ".\\Backend-Publisher' not in script


def test_local_worker_sources_fail_before_vm_start():
    script = BATCH.read_text(encoding="utf-8")

    validation = script.index("$RequiredLocalSources = @(")
    missing_source_error = script.index("Required repository source file was not found")
    vm_start = script.index("Start-VM -Name $VMs")

    assert validation < missing_source_error < vm_start
    assert "no VMs were started" in script
