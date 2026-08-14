import importlib.util
import json
import threading
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


publisher = load_module("lmn_publisher_spool_test", ROOT / "main.py")
spool = load_module("lmn_publisher_spool", ROOT / "spool.py")


def valid_item(url, title="Title"):
    return {
        "category": "AI",
        "source_name": "Example",
        "source_url": url,
        "title_en": title,
        "title_pt": title,
        "summary_en": "Summary",
        "summary_pt": "Resumo",
    }


def stage_batch(tmp_path, name, items):
    path = tmp_path / name
    path.write_text(json.dumps(items), encoding="utf-8")
    return path


class FakeQuery:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.items = []

    def upsert(self, item, **kwargs):
        self.items.append(item)
        return self

    def execute(self):
        outcome = self.outcomes.pop(0)
        if callable(outcome):
            outcome = outcome()
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(data=outcome)


class FakeClient:
    def __init__(self, outcomes):
        self.query = FakeQuery(outcomes)

    def table(self, name):
        assert name == "news"
        return self.query


def test_producer_can_enqueue_b_while_consumer_processes_a_without_b_loss(monkeypatch, tmp_path):
    """Forced Test A: consumer owns processing/A while producer publishes immutable inbox/B."""
    spool_root = tmp_path / "spool"
    batch_a = "batch-" + "a" * 32
    batch_b = "batch-" + "b" * 32
    item_a = valid_item("https://example.com/a", "A")
    item_b = valid_item("https://example.com/b", "B")

    spool.enqueue_staged_batch(stage_batch(tmp_path, "a.json", [item_a]), spool_root, batch_a)
    claimed_a = spool.claim_next_batch(spool_root)
    assert claimed_a is not None and claimed_a.name == f"{batch_a}.json"

    consumer_entered = threading.Event()
    allow_consumer_finish = threading.Event()

    def blocking_success():
        consumer_entered.set()
        assert allow_consumer_finish.wait(timeout=5), "producer interleaving never released consumer"
        return [{"id": 1}]

    client = FakeClient([blocking_success])
    monkeypatch.setattr(publisher, "create_client", lambda *_: client)
    retry = tmp_path / "retry.json"
    rejected = tmp_path / "rejected.json"
    result = {}

    def consume_a():
        result["exit"] = publisher.run_locked_publisher(
            claimed_a, retry, rejected, "https://example.supabase.co", "test-key"
        )

    thread = threading.Thread(target=consume_a, daemon=True)
    thread.start()
    assert consumer_entered.wait(timeout=5), "consumer did not reach forced processing barrier"

    # Exact vulnerable interval: A is already in consumer memory/processing, then B arrives.
    spool.enqueue_staged_batch(stage_batch(tmp_path, "b.json", [item_b]), spool_root, batch_b)
    inbox_b = spool_root / "inbox" / f"{batch_b}.json"
    assert inbox_b.exists()

    allow_consumer_finish.set()
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert result["exit"] == 0
    assert not claimed_a.exists()
    assert inbox_b.exists(), "consumer A must never unlink producer B"

    claimed_b = spool.claim_next_batch(spool_root)
    assert claimed_b is not None and claimed_b.name == f"{batch_b}.json"


def test_claimed_publisher_batch_survives_crash_before_completion(tmp_path):
    """Test D: a crash after claim leaves processing state discoverable and recoverable."""
    spool_root = tmp_path / "spool"
    batch_id = "batch-" + "c" * 32
    spool.enqueue_staged_batch(
        stage_batch(tmp_path, "a.json", [valid_item("https://example.com/a")]),
        spool_root,
        batch_id,
    )

    first_claim = spool.claim_next_batch(spool_root)
    assert first_claim is not None and first_claim.exists()

    # Simulated crash: no Publisher completion/unlink occurs.
    recovered_claim = spool.claim_next_batch(spool_root)
    assert recovered_claim == first_claim
    assert recovered_claim.exists()


def test_producer_crash_before_atomic_publish_exposes_no_partial_batch(tmp_path):
    """Test E: a producer crash during write never exposes partial JSON to consumers."""
    spool_root = tmp_path / "spool"
    batch_id = "batch-" + "d" * 32
    staging = stage_batch(tmp_path, "staging.json", [valid_item("https://example.com/a")])

    def crash_after_fsync(_temp, _final):
        raise RuntimeError("simulated producer crash")

    with pytest.raises(RuntimeError, match="simulated producer crash"):
        spool.enqueue_staged_batch(
            staging,
            spool_root,
            batch_id,
            before_publish_hook=crash_after_fsync,
        )

    assert staging.exists(), "source staging must remain recoverable after failed enqueue"
    assert list((spool_root / "inbox").glob("batch-*.json")) == []
    assert list((spool_root / "inbox").glob(".*.tmp")) == []
    assert spool.claim_next_batch(spool_root) is None


def test_same_batch_replay_is_idempotent_at_spool_and_database(monkeypatch, tmp_path):
    """Test F: replay converges through immutable batch identity + DB source_url idempotency."""
    spool_root = tmp_path / "spool"
    batch_id = "batch-" + "e" * 32
    item_a = valid_item("https://example.com/a")
    payload = [item_a]

    first_stage = stage_batch(tmp_path, "first.json", payload)
    first_path = spool.enqueue_staged_batch(first_stage, spool_root, batch_id)
    assert first_path.exists()

    # Replay while still queued is a no-op, not an overwrite or second queue entry.
    replay_queued = stage_batch(tmp_path, "replay-queued.json", payload)
    assert spool.enqueue_staged_batch(replay_queued, spool_root, batch_id) == first_path
    assert len(list((spool_root / "inbox").glob("batch-*.json"))) == 1

    claimed = spool.claim_next_batch(spool_root)
    first_client = FakeClient([[{"id": 1}]])
    monkeypatch.setattr(publisher, "create_client", lambda *_: first_client)
    assert publisher.run_locked_publisher(
        claimed,
        tmp_path / "retry.json",
        tmp_path / "rejected.json",
        "https://example.supabase.co",
        "test-key",
    ) == 0

    # Crash/replay after acknowledgement may enqueue the immutable batch again. The
    # database UNIQUE/upsert contract converges it to a duplicate no-op.
    replay_after = stage_batch(tmp_path, "replay-after.json", payload)
    spool.enqueue_staged_batch(replay_after, spool_root, batch_id)
    replay_claim = spool.claim_next_batch(spool_root)
    duplicate_client = FakeClient([[]])
    monkeypatch.setattr(publisher, "create_client", lambda *_: duplicate_client)
    assert publisher.run_locked_publisher(
        replay_claim,
        tmp_path / "retry.json",
        tmp_path / "rejected.json",
        "https://example.supabase.co",
        "test-key",
    ) == 0
    assert duplicate_client.query.items == [item_a]


def test_new_batch_survives_while_previous_batch_transitions_to_retry(monkeypatch, tmp_path):
    """Forced Test G: retained A stays durable while fresh B remains independently processable."""
    spool_root = tmp_path / "spool"
    batch_a = "batch-" + "f" * 32
    batch_b = "batch-" + "0" * 32
    item_a = valid_item("https://example.com/a", "A")
    item_b = valid_item("https://example.com/b", "B")

    spool.enqueue_staged_batch(stage_batch(tmp_path, "a.json", [item_a]), spool_root, batch_a)
    claimed_a = spool.claim_next_batch(spool_root)
    retry = tmp_path / "retry.json"
    rejected = tmp_path / "rejected.json"

    consumer_entered = threading.Event()
    allow_failure = threading.Event()
    request = httpx.Request("POST", "https://example.supabase.co")

    def first_network_failure():
        consumer_entered.set()
        assert allow_failure.wait(timeout=5)
        return httpx.ConnectError("offline", request=request)

    client_a = FakeClient([
        first_network_failure,
        httpx.ConnectError("offline", request=request),
        httpx.ConnectError("offline", request=request),
    ])
    monkeypatch.setattr(publisher, "RETRY_BACKOFF_SECONDS", 0)
    monkeypatch.setattr(publisher, "create_client", lambda *_: client_a)
    result = {}

    thread = threading.Thread(
        target=lambda: result.setdefault(
            "exit",
            publisher.run_locked_publisher(
                claimed_a,
                retry,
                rejected,
                "https://example.supabase.co",
                "test-key",
            ),
        ),
        daemon=True,
    )
    thread.start()
    assert consumer_entered.wait(timeout=5)

    spool.enqueue_staged_batch(stage_batch(tmp_path, "b.json", [item_b]), spool_root, batch_b)
    inbox_b = spool_root / "inbox" / f"{batch_b}.json"
    assert inbox_b.exists()
    allow_failure.set()
    thread.join(timeout=5)
    assert result["exit"] == 1

    retained = json.loads(retry.read_text(encoding="utf-8"))
    assert len(retained) == 1
    assert publisher.validate_item(retained[0]) == item_a
    retry_state = retained[0][publisher.RETRY_METADATA_KEY]
    assert retry_state["cycles"] == 1
    assert retry_state["next_attempt_at"] > retry_state["first_failed_at"]
    assert inbox_b.exists()

    # Immediate scheduler-style processing must defer A without consuming provider
    # budget while still publishing fresh B. A remains durable for its next due cycle.
    claimed_b = spool.claim_next_batch(spool_root)
    client_b = FakeClient([[{"id": 2}]])
    monkeypatch.setattr(publisher, "create_client", lambda *_: client_b)
    assert publisher.run_locked_publisher(
        claimed_b,
        retry,
        rejected,
        "https://example.supabase.co",
        "test-key",
        allow_retained_retry_success=True,
    ) == 0
    assert [entry["source_url"] for entry in client_b.query.items] == [
        "https://example.com/b",
    ]
    retained_after_b = json.loads(retry.read_text(encoding="utf-8"))
    assert retained_after_b == retained
    assert not claimed_b.exists()


def test_control_case_proves_legacy_mutable_inbound_can_delete_unread_b(tmp_path):
    """Test-the-test control for Race A, with explicit sequencing and no timing luck."""
    inbound = tmp_path / "legacy-inbound.json"
    item_a = valid_item("https://example.com/a")
    item_b = valid_item("https://example.com/b")
    inbound.write_text(json.dumps([item_a]), encoding="utf-8")

    # Consumer snapshots A.
    snapshot = json.loads(inbound.read_text(encoding="utf-8"))
    assert snapshot == [item_a]

    # Producer atomically replaces mutable inbound with B after the snapshot.
    publisher.atomic_write_json(inbound, [item_b])
    assert json.loads(inbound.read_text(encoding="utf-8")) == [item_b]

    # Legacy consumer cleanup unlinks by pathname, silently deleting B.
    inbound.unlink()
    assert not inbound.exists()
