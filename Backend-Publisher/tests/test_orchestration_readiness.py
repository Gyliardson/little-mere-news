from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ORCHESTRATOR = ROOT / "Infrastructure" / "Run-LMN-Batch.ps1"
ENV_EXAMPLE = ROOT / ".env.example"


def test_hyperv_vm_readiness_has_a_finite_configurable_deadline():
    script = ORCHESTRATOR.read_text(encoding="utf-8")

    assert "while ($true)" not in script
    assert "function Wait-LmnVmNetwork" in script
    assert ".AddSeconds($TimeoutSeconds)" in script
    assert "$VmReadyTimeoutSeconds = 120" in script
    assert "LMN_VM_READY_TIMEOUT_SECONDS" in script
    assert "[int]::TryParse" in script
    assert "$parsedVmReadyTimeout -lt 5" in script
    assert "$parsedVmReadyTimeout -gt 600" in script
    assert "Wait-LmnVmNetwork -IpAddress $ip" in script
    assert "did not become reachable within $TimeoutSeconds seconds" in script
    assert "Fail-LmnBatch" in script


def test_root_env_example_documents_optional_readiness_timeout():
    example = ENV_EXAMPLE.read_text(encoding="utf-8")

    assert "LMN_VM_READY_TIMEOUT_SECONDS=120" in example
    assert "5-600" in example
