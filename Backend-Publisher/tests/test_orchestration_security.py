from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ORCHESTRATOR = ROOT / "Infrastructure" / "Run-LMN-Batch.ps1"
DEPLOYMENT = ROOT / "docs" / "operations" / "DEPLOYMENT.md"
ROOT_ENV_EXAMPLE = ROOT / ".env.example"


def test_hyperv_orchestrator_requires_verified_host_keys():
    script = ORCHESTRATOR.read_text(encoding="utf-8")

    assert "StrictHostKeyChecking=no" not in script
    assert '"StrictHostKeyChecking=yes"' in script
    assert '"UserKnownHostsFile=$KnownHostsFile"' in script
    assert '"BatchMode=yes"' in script
    assert "LMN_KNOWN_HOSTS_FILE" in script
    assert "Test-Path -LiteralPath $KnownHostsFile -PathType Leaf" in script


def test_hyperv_orchestrator_does_not_interpolate_publisher_secret_from_host():
    script = ORCHESTRATOR.read_text(encoding="utf-8")

    assert "$env:SUPABASE_KEY" not in script
    assert "$env:SUPABASE_URL" not in script
    assert "export SUPABASE_KEY='" not in script
    assert "export SUPABASE_URL='" not in script
    assert "/home/lmnadmin/.config/lmn/publisher.env" in script
    assert "test -n `\"`$SUPABASE_KEY`\"" in script
    assert "test -n `\"`$SUPABASE_URL`\"" in script


def test_root_infrastructure_example_does_not_reintroduce_host_secret_or_shared_queue():
    example = ROOT_ENV_EXAMPLE.read_text(encoding="utf-8")

    active_lines = [
        line.strip()
        for line in example.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert not any(line.startswith("SUPABASE_URL=") for line in active_lines)
    assert not any(line.startswith("SUPABASE_KEY=") for line in active_lines)
    assert "publisher.env" in example
    assert "LMN_KNOWN_HOSTS_FILE" in example
    assert "harvester.pending.json" in example
    assert "publisher.inbound.json" in example
    assert "publisher.retry.json" in example
    assert "publisher.rejected.json" in example


def test_deployment_docs_require_trusted_host_enrollment_and_remote_secret_provisioning():
    docs = DEPLOYMENT.read_text(encoding="utf-8").lower()

    assert "known_hosts" in docs
    assert "fingerprint" in docs
    assert "trusted" in docs
    assert "publisher.env" in docs
    assert "chmod 600" in docs
    assert "ssh-keyscan" in docs
    assert "not" in docs.split("ssh-keyscan", 1)[1][:200]
