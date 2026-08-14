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


def test_queue_paths_preserve_safe_defaults():
    input_file, retry_file, rejected_file = publisher.get_queue_paths({})

    assert input_file == Path("/home/lmnadmin/news_to_publish.inbound.json")
    assert retry_file == Path("/home/lmnadmin/news_to_publish.retry.json")
    assert rejected_file == Path("/home/lmnadmin/news_to_publish.rejected.json")


def test_queue_paths_accept_portable_overrides(tmp_path):
    input_file, retry_file, rejected_file = publisher.get_queue_paths(
        {
            "LMN_INPUT_FILE": str(tmp_path / "handoff" / "news.json"),
            "LMN_RETRY_FILE": str(tmp_path / "retry" / "retry.json"),
            "LMN_REJECTED_FILE": str(tmp_path / "quarantine" / "rejected.json"),
        }
    )

    assert input_file == tmp_path / "handoff" / "news.json"
    assert retry_file == tmp_path / "retry" / "retry.json"
    assert rejected_file == tmp_path / "quarantine" / "rejected.json"


@pytest.mark.parametrize("same_pair", [("input", "retry"), ("input", "rejected"), ("retry", "rejected")])
def test_queue_paths_reject_shared_ownership_paths(tmp_path, same_pair):
    shared = tmp_path / "queue.json"
    values = {
        "LMN_INPUT_FILE": str(tmp_path / "input.json"),
        "LMN_RETRY_FILE": str(tmp_path / "retry.json"),
        "LMN_REJECTED_FILE": str(tmp_path / "rejected.json"),
    }
    mapping = {
        "input": "LMN_INPUT_FILE",
        "retry": "LMN_RETRY_FILE",
        "rejected": "LMN_REJECTED_FILE",
    }
    values[mapping[same_pair[0]]] = str(shared)
    values[mapping[same_pair[1]]] = str(shared)

    with pytest.raises(ValueError, match="must be different paths"):
        publisher.get_queue_paths(values)


def test_queue_paths_reject_empty_override():
    with pytest.raises(ValueError, match="LMN_REJECTED_FILE must not be empty"):
        publisher.get_queue_paths({"LMN_REJECTED_FILE": "   "})


def test_queue_paths_reject_existing_directory(tmp_path):
    with pytest.raises(ValueError, match="LMN_INPUT_FILE must point to a file"):
        publisher.get_queue_paths({"LMN_INPUT_FILE": str(tmp_path)})


def test_validate_item_rejects_missing_fields_and_non_http_url():
    assert publisher.validate_item(valid_item(title_en="")) is None
    assert publisher.validate_item(valid_item(source_url="javascript:alert(1)")) is None
    assert publisher.validate_item(["not", "an", "object"]) is None


def test_merge_queues_deduplicates_valid_urls_but_preserves_invalid_payloads():
    first = valid_item(source_url="https://example.com/a")
    duplicate = valid_item(source_url="https://example.com/a", title_en="newer")
    second = valid_item(source_url="https://example.com/b")
    invalid = {"bad": "payload"}

    assert publisher.merge_queues([first, invalid], [duplicate, second]) == [first, invalid, second]


def test_publish_item_uses_source_url_conflict_contract():
    client = FakeClient([[{"id": 1}]])
    assert publisher.publish_item(client, valid_item()) == "published"
    assert client.query.kwargs == {
        "on_conflict": "source_url",
        "ignore_duplicates": True,
    }


def test_publish_item_treats_empty_data_as_duplicate_noop():
    client = FakeClient([[]])
    assert publisher.publish_item(client, valid_item()) == "duplicate"


def test_publish_with_retry_recovers_from_timeout():
    request = httpx.Request("POST", "https://example.supabase.co")
    timeout = httpx.ReadTimeout("timeout", request=request)
    client = FakeClient([timeout, [{"id": 1}]])
    sleeps = []

    assert publisher.publish_with_retry(client, valid_item(), sleep_fn=sleeps.append) == "published"
    assert sleeps == [publisher.RETRY_BACKOFF_SECONDS]


def test_publish_with_retry_keeps_item_after_bounded_network_failure():
    request = httpx.Request("POST", "https://example.supabase.co")
    failures = [httpx.ConnectError("offline", request=request) for _ in range(3)]
    client = FakeClient(failures)

    result = publisher.publish_with_retry(client, valid_item(), sleep_fn=lambda _: None)
    assert result[0] == "retryable_failure"


def test_process_batch_preserves_partial_failures_and_quarantines_invalid():
    request = httpx.Request("POST", "https://example.supabase.co")
    failed_item = valid_item(source_url="https://example.com/retry", title_en="Retry")
    client = FakeClient([
        [{"id": 1}],
        [],
        httpx.ConnectError("offline", request=request),
        httpx.ConnectError("offline", request=request),
        httpx.ConnectError("offline", request=request),
    ])
    items = [
        valid_item(source_url="https://example.com/new"),
        valid_item(source_url="https://example.com/existing"),
        failed_item,
        {"bad": "payload"},
    ]

    counts, retry_queue, rejected = publisher.process_batch(
        client, items, sleep_fn=lambda _: None
    )

    assert counts == {
        "published": 1,
        "duplicate": 1,
        "retryable_failure": 1,
        "permanent_failure": 0,
        "invalid": 1,
    }
    assert retry_queue == [failed_item]
    assert rejected == [{"bad": "payload"}]


def test_process_batch_quarantines_non_transport_database_failure():
    item = valid_item(source_url="https://example.com/db-failure")
    client = FakeClient([RuntimeError("database rejected write")])

    counts, retry_queue, rejected = publisher.process_batch(client, [item])

    assert counts["permanent_failure"] == 1
    assert retry_queue == []
    assert rejected == [item]


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


def test_main_custom_paths_preserve_retry_and_rejected_payloads(monkeypatch, tmp_path):
    input_file, retry_file, rejected_file = configure_paths(monkeypatch, tmp_path)
    failed_item = valid_item(source_url="https://example.com/retry", title_en="Retry")
    input_file.write_text(json.dumps([failed_item, {"bad": "payload"}]), encoding="utf-8")

    request = httpx.Request("POST", "https://example.supabase.co")
    client = FakeClient([httpx.ConnectError("offline", request=request) for _ in range(3)])
    monkeypatch.setattr(publisher, "create_client", lambda *_: client)

    assert publisher.main() == 1
    assert not input_file.exists()
    assert json.loads(retry_file.read_text(encoding="utf-8")) == [failed_item]
    assert json.loads(rejected_file.read_text(encoding="utf-8")) == [{"bad": "payload"}]


def test_main_quarantines_permanent_failure_and_does_not_retry_it_next_run(monkeypatch, tmp_path):
    input_file, retry_file, rejected_file = configure_paths(monkeypatch, tmp_path)
    permanent = valid_item(source_url="https://example.com/permanent", title_en="Permanent")
    input_file.write_text(json.dumps([permanent]), encoding="utf-8")

    first_client = FakeClient([RuntimeError("schema mismatch")])
    monkeypatch.setattr(publisher, "create_client", lambda *_: first_client)

    assert publisher.main() == 1
    assert not input_file.exists()
    assert not retry_file.exists()
    assert json.loads(rejected_file.read_text(encoding="utf-8")) == [permanent]
    assert [item["source_url"] for item in first_client.query.items] == [permanent["source_url"]]

    # Quarantine is not an active input queue. A later no-work run succeeds and does
    # not create a client or reattempt the permanent failure.
    monkeypatch.setattr(
        publisher,
        "create_client",
        lambda *_: pytest.fail("quarantined item must not be reprocessed"),
    )
    assert publisher.main() == 0
    assert json.loads(rejected_file.read_text(encoding="utf-8")) == [permanent]


def test_main_invalid_payload_is_quarantined_and_signaled_once(monkeypatch, tmp_path):
    input_file, retry_file, rejected_file = configure_paths(monkeypatch, tmp_path)
    input_file.write_text(json.dumps([{"bad": "payload"}]), encoding="utf-8")
    monkeypatch.setattr(publisher, "create_client", lambda *_: FakeClient([]))

    assert publisher.main() == 1
    assert not input_file.exists()
    assert not retry_file.exists()
    assert json.loads(rejected_file.read_text(encoding="utf-8")) == [{"bad": "payload"}]

    assert publisher.main() == 0


def test_main_custom_path_removes_successfully_published_queues(monkeypatch, tmp_path):
    input_file, retry_file, rejected_file = configure_paths(monkeypatch, tmp_path)
    input_file.write_text(json.dumps([valid_item()]), encoding="utf-8")
    monkeypatch.setattr(publisher, "create_client", lambda *_: FakeClient([[{"id": 1}]]))

    assert publisher.main() == 0
    assert not input_file.exists()
    assert not retry_file.exists()
    assert not rejected_file.exists()


def test_cross_run_partial_failure_survives_next_inbound_batch(monkeypatch, tmp_path):
    input_file, retry_file, rejected_file = configure_paths(monkeypatch, tmp_path)
    item_a = valid_item(source_url="https://example.com/a", title_en="A")
    item_b = valid_item(source_url="https://example.com/b", title_en="B")
    input_file.write_text(json.dumps([item_a]), encoding="utf-8")

    request = httpx.Request("POST", "https://example.supabase.co")
    first_client = FakeClient([httpx.ConnectError("offline", request=request) for _ in range(3)])
    monkeypatch.setattr(publisher, "create_client", lambda *_: first_client)
    assert publisher.main() == 1
    assert json.loads(retry_file.read_text(encoding="utf-8")) == [item_a]
    assert not input_file.exists()

    # Run N+1 delivers a new inbound batch without touching Publisher-owned retry state.
    input_file.parent.mkdir(parents=True, exist_ok=True)
    publisher.atomic_write_json(input_file, [item_b, item_a])
    second_client = FakeClient([[{"id": 1}], [{"id": 2}]])
    monkeypatch.setattr(publisher, "create_client", lambda *_: second_client)

    assert publisher.main() == 0
    assert [item["source_url"] for item in second_client.query.items] == [
        "https://example.com/a",
        "https://example.com/b",
    ]
    assert not input_file.exists()
    assert not retry_file.exists()
    assert not rejected_file.exists()
