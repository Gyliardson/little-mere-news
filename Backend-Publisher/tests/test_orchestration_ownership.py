from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = REPO_ROOT / "Infrastructure" / "Run-LMN-Batch.ps1"


def test_launcher_uses_claim_spool_protocol_instead_of_mutable_path_cleanup():
    text = LAUNCHER.read_text(encoding="utf-8")

    assert "queue_claim.py claim" in text
    assert "queue_claim.py complete" in text
    assert "spool.py enqueue" in text
    assert "spool.py claim-next" in text
    assert "Enter-LmnHostLock" in text
    assert "CommonApplicationData" not in text  # topology belongs to shared helper, not checkout logic

    # Regression guards for the independently reproduced races.
    assert 'Join-Path $ProjectRoot "lmn-batch.lock"' not in text
    assert "news_to_publish.inbound.json" not in text
    assert "rm -f '$HarvesterPending'" not in text
    assert "rm -f '$HarvesterQueue'" not in text
    assert "PublisherStaging" in text
    assert "batch-[0-9a-f]{32}" in text


def test_launcher_transfers_ownership_helpers_to_the_worker_vms():
    text = LAUNCHER.read_text(encoding="utf-8")
    assert 'Backend-Harvester\\queue_claim.py' in text
    assert 'Backend-Publisher\\spool.py' in text
    assert "Could not transfer Harvester claim helper" in text
    assert "Could not transfer Publisher spool helper" in text
