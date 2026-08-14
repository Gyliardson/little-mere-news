import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "main.py"
spec = importlib.util.spec_from_file_location("lmn_publisher", MODULE_PATH)
publisher = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(publisher)


def valid_item(**overrides):
    item = {
        "category": "AI",
        "source_name": "Example",
        "source_url": "https://example.com/article-1",
        "title_en": "Title",
        "title_pt": "Titulo",
        "summary_en": "Summary",
        "summary_pt": "Resumo",
    }
    item.update(overrides)
    return item


class FakeQuery:
    def __init__(self, outcomes):
        self.outcomes = outcomes
        self.kwargs = None
        self.items = []

    def upsert(self, item, **kwargs):
        self.kwargs = kwargs
        self.items.append(item)
        return self

    def execute(self):
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(data=outcome)


class FakeClient:
    def __init__(self, outcomes):
        self.query = FakeQuery(list(outcomes))

    def table(self, name):
        assert name == "news"
        return self.query


def transient_failures(count=3):
    request = httpx.Request("POST", "https://example.supabase.co")
    return [httpx.ConnectError("offline", request=request) for _ in range(count)]


def configure_paths(monkeypatch, tmp_path):
    input_file = tmp_path / "handoff" / "inbound.json"
    retry_file = tmp_path / "retry" / "retry.json"
    rejected_file = tmp_path / "quarantine" / "rejected.json"
    input_file.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-server-key")
    monkeypatch.setenv("LMN_INPUT_FILE", str(input_file))
    monkeypatch.setenv("LMN_RETRY_FILE", str(retry_file))
    monkeypatch.setenv("LMN_REJECTED_FILE", str(rejected_file))
    monkeypatch.setattr(publisher, "RETRY_BACKOFF_SECONDS", 0)
    return input_file, retry_file, rejected_file


def test_queue_paths_preserve_defaults_and_accept_portable_overrides(tmp_path):
    assert publisher.get_queue_paths({}) == (
        Path("/home/lmnadmin/news_to_publish.inbound.json"),
        Path("/home/lmnadmin/news_to_publish.retry.json"),
        Path("/home/lmnadmin/news_to_publish.rejected.json"),
    )
    assert publisher.get_queue_paths(
        {
            "LMN_INPUT_FILE": str(tmp_path / "in.json"),
            "LMN_RETRY_FILE": str(tmp_path / "retry.json"),
            "LMN_REJECTED_FILE": str(tmp_path / "rejected.json"),
        }
    ) == (tmp_path / "in.json", tmp_path / "retry.json", tmp_path / "rejected.json")


@pytest.mark.parametrize("same_pair", [("input", "retry"), ("input", "rejected"), ("retry", "rejected")])
def test_queue_paths_reject_shared_ownership_paths(tmp_path, same_pair):
    shared = tmp_path / "queue.json"
    values = {
        "input": str(tmp_path / "input.json"),
        "retry": str(tmp_path / "retry.json"),
        "rejected": str(tmp_path / "rejected.json"),
    }
    values[same_pair[0]] = str(shared)
    values[same_pair[1]] = str(shared)
    with pytest.raises(ValueError, match="must be different paths"):
        publisher.get_queue_paths(
            {
                "LMN_INPUT_FILE": values["input"],
                "LMN_RETRY_FILE": values["retry"],
                "LMN_REJECTED_FILE": values["rejected"],
            }
        )


def test_queue_paths_reject_empty_and_directory(tmp_path):
    with pytest.raises(ValueError, match="must not be empty"):
        publisher.get_queue_paths({"LMN_REJECTED_FILE": "   "})
    with pytest.raises(ValueError, match="must point to a file"):
        publisher.get_queue_paths({"LMN_INPUT_FILE": str(tmp_path)})


def test_validate_item_and_merge_queue_contracts():
    assert publisher.validate_item(valid_item(title_en="")) is None
    assert publisher.validate_item(valid_item(source_url="javascript:alert(1)")) is None
    assert publisher.validate_item(["not", "object"]) is None

    first = valid_item(source_url="https://example.com/a")
    duplicate = valid_item(source_url="https://example.com/a", title_en="newer")
    second = valid_item(source_url="https://example.com/b")
    invalid = {"bad": "payload"}
    assert publisher.merge_queues([first, invalid], [duplicate, second]) == [first, invalid, second]


def test_publish_item_uses_source_url_conflict_contract_and_duplicate_noop():
    client = FakeClient([[{"id": 1}], []])
    assert publisher.publish_item(client, valid_item()) == "published"
    assert client.query.kwargs == {"on_conflict": "source_url", "ignore_duplicates": True}
    assert publisher.publish_item(client, valid_item()) == "duplicate"


def test_publish_with_retry_keeps_existing_in_process_bound():
    request = httpx.Request("POST", "https://example.supabase.co")
    client = FakeClient([httpx.ReadTimeout("timeout", request=request), [{"id": 1}]])
    sleeps = []
    assert publisher.publish_with_retry(client, valid_item(), sleep_fn=sleeps.append) == "published"
    assert sleeps == [publisher.RETRY_BACKOFF_SECONDS]

    failed = FakeClient(transient_failures())
    assert publisher.publish_with_retry(failed, valid_item(), sleep_fn=lambda _: None)[0] == "retryable_failure"
    assert len(failed.query.items) == publisher.MAX_ATTEMPTS


def test_process_batch_handles_independent_success_retry_permanent_and_invalid():
    retry_item = valid_item(source_url="https://example.com/retry")
    permanent = valid_item(source_url="https://example.com/permanent")
    client = FakeClient(
        [
            [{"id": 1}],
            *transient_failures(),
            RuntimeError("schema mismatch"),
        ]
    )
    counts, retry_queue, rejected = publisher.process_batch(
        client,
        [valid_item(source_url="https://example.com/new"), retry_item, permanent, {"bad": "payload"}],
        sleep_fn=lambda _: None,
        now_fn=lambda: 1000.0,
    )
    assert counts["published"] == 1
    assert counts["retryable_failure"] == 1
    assert counts["permanent_failure"] == 1
    assert counts["invalid"] == 1
    assert retry_queue[0]["source_url"] == retry_item["source_url"]
    metadata = retry_queue[0][publisher.RETRY_METADATA_KEY]
    assert metadata == {"cycles": 1, "first_failed_at": 1000.0, "next_attempt_at": 1300.0}
    assert rejected == [permanent, {"bad": "payload"}]


def test_retry_metadata_is_fail_closed_when_corrupt():
    raw = {**valid_item(), publisher.RETRY_METADATA_KEY: {"cycles": "forever"}}
    counts, retry_queue, rejected = publisher.process_batch(
        FakeClient([]), [raw], now_fn=lambda: 1000.0
    )
    assert counts["invalid"] == 1
    assert retry_queue == []
    assert rejected == [valid_item()]


def test_deferred_retry_does_not_call_provider_or_block_other_item():
    retained = publisher.with_retry_metadata(
        valid_item(source_url="https://example.com/a"),
        {"cycles": 2, "first_failed_at": 100.0, "next_attempt_at": 2000.0},
    )
    fresh = valid_item(source_url="https://example.com/b")
    client = FakeClient([[{"id": 2}]])
    counts, retry_queue, rejected = publisher.process_batch(
        client, [retained, fresh], now_fn=lambda: 1000.0
    )
    assert counts["deferred"] == 1
    assert counts["published"] == 1
    assert [item["source_url"] for item in client.query.items] == [fresh["source_url"]]
    assert retry_queue == [retained]
    assert rejected == []


def test_retry_lifetime_exhaustion_is_durable_and_quarantined():
    item = publisher.with_retry_metadata(
        valid_item(source_url="https://example.com/a"),
        {
            "cycles": publisher.MAX_RETRY_CYCLES - 1,
            "first_failed_at": 100.0,
            "next_attempt_at": 0.0,
        },
    )
    counts, retry_queue, rejected = publisher.process_batch(
        FakeClient(transient_failures()), [item], sleep_fn=lambda _: None, now_fn=lambda: 1000.0
    )
    assert counts["retry_exhausted"] == 1
    assert retry_queue == []
    assert rejected[0][publisher.RETRY_METADATA_KEY]["cycles"] == publisher.MAX_RETRY_CYCLES


def test_main_retains_transient_work_but_returns_success_for_orchestrator_liveness(monkeypatch, tmp_path):
    input_file, retry_file, rejected_file = configure_paths(monkeypatch, tmp_path)
    item = valid_item(source_url="https://example.com/retry")
    input_file.write_text(json.dumps([item]), encoding="utf-8")
    client = FakeClient(transient_failures())
    monkeypatch.setattr(publisher, "create_client", lambda *_: client)

    # Retained transient work is durable and paced. Exit zero is intentional: the
    # launcher may continue to Harvester instead of starving independent collection.
    assert publisher.main() == 0
    assert not input_file.exists()
    retained = json.loads(retry_file.read_text(encoding="utf-8"))
    assert retained[0]["source_url"] == item["source_url"]
    assert retained[0][publisher.RETRY_METADATA_KEY]["cycles"] == 1
    assert not rejected_file.exists()


def test_multi_run_scheduler_liveness_retained_a_cannot_starve_new_b(monkeypatch, tmp_path):
    input_file, retry_file, rejected_file = configure_paths(monkeypatch, tmp_path)
    item_a = valid_item(source_url="https://example.com/a", title_en="A")
    item_b = valid_item(source_url="https://example.com/b", title_en="B")

    # Scheduler run N: A fails all local attempts and is durably retained with pacing.
    input_file.write_text(json.dumps([item_a]), encoding="utf-8")
    first_client = FakeClient(transient_failures())
    monkeypatch.setattr(publisher, "create_client", lambda *_: first_client)
    assert publisher.main() == 0
    retained_a = json.loads(retry_file.read_text(encoding="utf-8"))[0]
    assert retained_a[publisher.RETRY_METADATA_KEY]["cycles"] == 1

    # Scheduler run N+1 preflight: A is not due. The zero exit explicitly allows the
    # launcher to execute Harvester; no provider attempt is spent on A.
    preflight_client = FakeClient([])
    monkeypatch.setattr(publisher, "create_client", lambda *_: preflight_client)
    assert publisher.main() == 0
    assert preflight_client.query.items == []

    # Harvester work B is now represented as a new Publisher inbound/spool claim while
    # A remains retained. Publisher processes B independently; A remains durable.
    input_file.parent.mkdir(parents=True, exist_ok=True)
    publisher.atomic_write_json(input_file, [item_b])
    b_client = FakeClient([[{"id": 2}]])
    monkeypatch.setattr(publisher, "create_client", lambda *_: b_client)
    assert publisher.main() == 0
    assert [item["source_url"] for item in b_client.query.items] == [item_b["source_url"]]
    assert json.loads(retry_file.read_text(encoding="utf-8"))[0]["source_url"] == item_a["source_url"]
    assert not rejected_file.exists()


def test_main_quarantines_permanent_failure_and_signals_operator(monkeypatch, tmp_path):
    input_file, retry_file, rejected_file = configure_paths(monkeypatch, tmp_path)
    permanent = valid_item(source_url="https://example.com/permanent")
    input_file.write_text(json.dumps([permanent]), encoding="utf-8")
    monkeypatch.setattr(publisher, "create_client", lambda *_: FakeClient([RuntimeError("schema mismatch")]))

    assert publisher.main() == 1
    assert not input_file.exists()
    assert not retry_file.exists()
    assert json.loads(rejected_file.read_text(encoding="utf-8")) == [permanent]

    monkeypatch.setattr(
        publisher,
        "create_client",
        lambda *_: pytest.fail("quarantined item must not be reprocessed"),
    )
    assert publisher.main() == 0


def test_main_invalid_payload_is_quarantined_once(monkeypatch, tmp_path):
    input_file, retry_file, rejected_file = configure_paths(monkeypatch, tmp_path)
    input_file.write_text(json.dumps([{"bad": "payload"}]), encoding="utf-8")
    monkeypatch.setattr(publisher, "create_client", lambda *_: FakeClient([]))
    assert publisher.main() == 1
    assert json.loads(rejected_file.read_text(encoding="utf-8")) == [{"bad": "payload"}]
    assert publisher.main() == 0


def test_main_success_removes_owned_queues(monkeypatch, tmp_path):
    input_file, retry_file, rejected_file = configure_paths(monkeypatch, tmp_path)
    input_file.write_text(json.dumps([valid_item()]), encoding="utf-8")
    monkeypatch.setattr(publisher, "create_client", lambda *_: FakeClient([[{"id": 1}]]))
    assert publisher.main() == 0
    assert not input_file.exists()
    assert not retry_file.exists()
    assert not rejected_file.exists()
