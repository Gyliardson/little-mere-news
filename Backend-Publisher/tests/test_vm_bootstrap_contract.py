import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INFRA = REPO_ROOT / "Infrastructure"
HARVESTER_REQUIREMENTS = REPO_ROOT / "Backend-Harvester" / "requirements.txt"
PUBLISHER_REQUIREMENTS = REPO_ROOT / "Backend-Publisher" / "requirements.txt"


def non_comment_lines(path):
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def test_runtime_requirements_are_exact_direct_pins():
    assert non_comment_lines(HARVESTER_REQUIREMENTS) == [
        "feedparser==6.0.12",
        "requests==2.33.1",
        "beautifulsoup4==4.14.3",
    ]
    assert non_comment_lines(PUBLISHER_REQUIREMENTS) == [
        "supabase==2.29.0",
        "requests==2.33.1",
    ]
    for path in (HARVESTER_REQUIREMENTS, PUBLISHER_REQUIREMENTS):
        assert all("==" in line for line in non_comment_lines(path))


def test_guest_python_setup_consumes_transferred_requirements_not_bare_packages():
    harvester = (INFRA / "setup_harvester.sh").read_text(encoding="utf-8")
    publisher = (INFRA / "setup_publisher.sh").read_text(encoding="utf-8")

    for script in (harvester, publisher):
        assert 'REQUIREMENTS_FILE="${1:-}"' in script
        assert 'pip install --requirement "$REQUIREMENTS_FILE"' in script
        assert "pip check" in script
        assert "must contain only blank/comment lines or exact == pins" in script

    assert "pip install feedparser requests beautifulsoup4" not in harvester
    assert "pip install supabase requests" not in publisher


def test_supported_host_bootstrap_transfers_canonical_requirements():
    bootstrap = (INFRA / "Bootstrap-LMN-Guests.ps1").read_text(encoding="utf-8")
    infrastructure_setup = (INFRA / "Setup-LMN-Infrastructure.ps1").read_text(encoding="utf-8")

    assert 'Backend-Harvester\\requirements.txt' in bootstrap
    assert 'Backend-Publisher\\requirements.txt' in bootstrap
    assert "harvester-requirements.txt" in bootstrap
    assert "publisher-requirements.txt" in bootstrap
    assert "Could not transfer Harvester requirements" in bootstrap
    assert "Could not transfer Publisher requirements" in bootstrap
    assert "StrictHostKeyChecking=yes" in bootstrap
    assert "sudo bash '$RemoteBootstrapDir/setup_harvester.sh' '$RemoteBootstrapDir/harvester-requirements.txt'" in bootstrap
    assert "sudo bash '$RemoteBootstrapDir/setup_publisher.sh' '$RemoteBootstrapDir/publisher-requirements.txt'" in bootstrap

    assert "Bootstrap-LMN-Guests.ps1" in infrastructure_setup
    assert "Execute the Python setup scripts on the respective instances." not in infrastructure_setup


def test_ollama_bootstrap_is_version_and_integrity_bounded():
    script = (INFRA / "setup_ollama.sh").read_text(encoding="utf-8")

    assert 'OLLAMA_VERSION="0.32.5"' in script
    assert 'OLLAMA_INSTALL_SCRIPT_SHA256="25f64b810b947145095956533e1bdf56eacea2673c55a7e586be4515fc882c9f"' in script
    assert 'https://github.com/ollama/ollama/releases/download/v${OLLAMA_VERSION}/install.sh' in script
    assert "sha256sum --check --strict" in script
    assert 'OLLAMA_VERSION="$OLLAMA_VERSION" sh "$INSTALLER"' in script
    assert "https://ollama.com/install.sh" not in script

    assert 'OLLAMA_MODEL="llama3:8b"' in script
    assert 'OLLAMA_MODEL_DIGEST_PREFIX="365c0bd3c000"' in script
    assert 'OLLAMA_RUNTIME_ALIAS="llama3:latest"' in script
    assert "api/tags" in script
    assert "does not match the repository-reviewed identity" in script
    assert 'ollama pull "$OLLAMA_MODEL"' in script
    assert 'ollama cp "$OLLAMA_MODEL" "$OLLAMA_RUNTIME_ALIAS"' in script
    assert "ollama pull llama3\n" not in script


def test_bootstrap_scripts_parse_without_executing_external_operations():
    bash = shutil.which("bash")
    assert bash is not None
    for name in ("setup_harvester.sh", "setup_publisher.sh", "setup_ollama.sh"):
        completed = subprocess.run(
            [bash, "-n", str(INFRA / name)],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert completed.returncode == 0, completed.stderr or completed.stdout

    pwsh = shutil.which("pwsh")
    assert pwsh is not None, "GitHub runner must provide pwsh for infrastructure contract tests"
    for name in ("Bootstrap-LMN-Guests.ps1", "Setup-LMN-Infrastructure.ps1"):
        path = str(INFRA / name).replace("'", "''")
        command = (
            "$tokens=$null; $errors=$null; "
            f"[System.Management.Automation.Language.Parser]::ParseFile('{path}', [ref]$tokens, [ref]$errors) | Out-Null; "
            "if ($errors.Count -gt 0) { $errors | ForEach-Object { Write-Error $_.Message }; exit 1 }"
        )
        completed = subprocess.run(
            [pwsh, "-NoProfile", "-NonInteractive", "-Command", command],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert completed.returncode == 0, completed.stderr or completed.stdout
