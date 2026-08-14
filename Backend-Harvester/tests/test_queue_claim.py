import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


harvester = load_module("lmn_harvester_claim_test", ROOT / "main.py")
queue_claim = load_module("lmn_harvester_queue_claim", ROOT / "queue_claim.py")


def item(url):
    return {"source_url": url}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_claimed_snapshot_cleanup_cannot_delete_later_pending_batch(tmp_path):
    """Forced Race B: claim A, persist B, acknowledge only A; B must survive."""
    pending = tmp_path / "pending.json"
    harvester.persist_pending_batch(pending, [item("https://example.com/a")])

    claim = queue_claim.claim_pending_batch(
        pending, batch_id_factory=lambda: "batch-" + "a" * 32
    )
    assert claim is not None
    assert read_json(claim) == [item("https://example.com/a")]
    assert not pending.exists()

    # This is the deterministic interleaving point: a newer Harvester write occurs
    # after launcher A owns its immutable claim but before A completes the handoff.
    harvester.persist_pending_batch(pending, [item("https://example.com/b")])
    assert read_json(pending) == [item("https://example.com/b")]

    assert queue_claim.complete_claim(pending, "batch-" + "a" * 32)
    assert not claim.exists()
    assert read_json(pending) == [item("https://example.com/b")]


def test_claim_survives_launcher_crash_and_is_recovered_before_new_pending(tmp_path):
    """Test D for the Harvester side: claimed work remains discoverable after crash."""
    pending = tmp_path / "pending.json"
    harvester.persist_pending_batch(pending, [item("https://example.com/a")])

    first = queue_claim.claim_pending_batch(
        pending, batch_id_factory=lambda: "batch-" + "b" * 32
    )
    assert first is not None

    # Simulate launcher death by deliberately omitting complete_claim(). A later
    # invocation must recover the exact previous claim rather than claiming newer work.
    harvester.persist_pending_batch(pending, [item("https://example.com/b")])
    recovered = queue_claim.claim_pending_batch(
        pending, batch_id_factory=lambda: "batch-" + "c" * 32
    )
    assert recovered == first
    assert read_json(recovered) == [item("https://example.com/a")]
    assert read_json(pending) == [item("https://example.com/b")]


def test_control_case_proves_legacy_snapshot_then_unlink_loses_new_work(tmp_path):
    """Test-the-test control: the old copy+later-unlink protocol deterministically loses B."""
    pending = tmp_path / "legacy-pending.json"
    harvester.persist_pending_batch(pending, [item("https://example.com/a")])

    # Launcher takes an old snapshot A without claiming ownership.
    snapshot = read_json(pending)
    assert snapshot == [item("https://example.com/a")]

    # New Harvester work B lands after the snapshot.
    harvester.persist_pending_batch(pending, [item("https://example.com/b")])
    assert read_json(pending) == [
        item("https://example.com/a"),
        item("https://example.com/b"),
    ]

    # This models the old remote `rm -f`: it destroys B even though B was not part of
    # the transferred snapshot. The assertion documents that the harness crosses the
    # vulnerable boundary rather than relying on scheduler timing.
    pending.unlink()
    assert not pending.exists()
