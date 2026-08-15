from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SETUP = ROOT / "Infrastructure" / "Setup-LMN-Infrastructure.ps1"
ENV_EXAMPLE = ROOT / ".env.example"


def test_setup_is_repository_relative_not_workstation_specific():
    script = SETUP.read_text(encoding="utf-8")

    assert 'C:\\Arquivos\\GitHub\\Projetos\\Little Mere News' not in script
    assert "$InfraRoot     = $PSScriptRoot" in script
    assert "$ProjectRoot   = Split-Path $InfraRoot -Parent" in script


def test_iso_requires_explicit_sha256_before_reuse_or_provisioning():
    script = SETUP.read_text(encoding="utf-8")

    assert "LMN_UBUNTU_ISO_SHA256" in script
    assert "^[0-9a-f]{64}$" in script
    assert "Get-FileHash -LiteralPath $Path -Algorithm SHA256" in script
    assert "Assert-LmnIsoDigestConfiguration" in script
    assert "Assert-LmnIsoIntegrity -Path $ISOFullPath" in script
    assert "Refusing to use unverified boot media" in script

    main = script.split("# Stage 1: Hyper-V Check", 1)[1]
    assert main.index("Assert-LmnIsoDigestConfiguration") < main.index("Invoke-NetworkSetup")
    assert main.index("Invoke-ISODownload") < main.index("Invoke-VMProvisioning")


def test_default_iso_source_is_current_explicit_and_overridable():
    script = SETUP.read_text(encoding="utf-8")

    assert "LMN_UBUNTU_ISO_URL" in script
    assert "ubuntu-24.04.4-live-server-amd64.iso" in script
    assert "ubuntu-24.04.2-live-server-amd64.iso" not in script
    assert 'Scheme -ne "https"' in script


def test_root_env_example_documents_trusted_iso_digest_input():
    example = ENV_EXAMPLE.read_text(encoding="utf-8")

    assert "LMN_UBUNTU_ISO_SHA256" in example
    assert "LMN_UBUNTU_ISO_URL" in example
    assert "official Ubuntu release manifest" in example
