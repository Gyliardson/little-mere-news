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

    def upsert(self, item, **kwargs):
        self.kwargs = kwargs
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


def test_queue_paths_preserve_legacy_defaults():
    input_file, rejected_file = publisher.get_queue_paths({})

    assert input_file == Path("/home/lmnadmin/news_to_publish.json")
    assert rejected_file == Path("/home/lmnadmin/news_to_publish.rejected.json")


def test_queue_paths_accept_portable_overrides(tmp_path):
    input_file, rejected_file = publisher.get_queue_paths(
        {
            "LMN_INPUT_FILE": str(tmp_path / "handoff" / "news.json"),
            "LMN_REJECTED_FILE": str(tmp_path / "quarantine" / "rejected.json"),
        }
    )

    assert input_file == tmp_path / "handoff" / "news.json"
    assert rejected_file == tmp_path / "quarantine" / "rejected.json"


def test_queue_paths_reject_same_input_and_rejected_file(tmp_path):
    shared = tmp_path / "queue.json"

    with pytest.raises(ValueError, match="must be different paths"):
        publisher.get_queue_paths(
            {"LMN_INPUT_FILE": str(shared), "LMN_REJECTED_FILE": str(shared)}
        )


def test_validate_item_rejects_missing_fields_and_non_http_url():
    assert publisher.validate_item(valid_item(title_en="")) is None
    assert publisher.validate_item(valid_item(source_url="javascript:alert(1)")) is None
    assert publisher.validate_item(["not", "an", "object"]) is None


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


def test_process_batch_preserves_non_transport_database_failure():
    item = valid_item(source_url="https://example.com/db-failure")
    client = FakeClient([RuntimeError("database rejected write")])

    counts, retry_queue, rejected = publisher.process_batch(client, [item])

    assert counts["permanent_failure"] == 1
    assert retry_queue == [item]
    assert rejected == []


def test_main_custom_paths_preserve_retry_and_rejected_payloads(monkeypatch, tmp_path):
    input_file = tmp_path / "handoff" / "news.json"
    rejected_file = tmp_path / "quarantine" / "rejected.json"
    input_file.parent.mkdir(parents=True)

    failed_item = valid_item(source_url="https://example.com/retry", title_en="Retry")
    input_file.write_text(json.dumps([failed_item, {"bad": "payload"}]), encoding="utf-8")

    request = httpx.Request("POST", "https://example.supabase.co")
    client = FakeClient(
        [httpx.ConnectError("offline", request=request) for _ in range(3)]
    )

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-server-key")
    monkeypatch.setenv("LMN_INPUT_FILE", str(input_file))
    monkeypatch.setenv("LMN_REJECTED_FILE", str(rejected_file))
    monkeypatch.setattr(publisher, "create_client", lambda *_: client)
    monkeypatch.setattr(publisher, "RETRY_BACKOFF_SECONDS", 0)

    assert publisher.main() == 1
    assert json.loads(input_file.read_text(encoding="utf-8")) == [failed_item]
    assert json.loads(rejected_file.read_text(encoding="utf-8")) == [{"bad": "payload"}]


def test_main_custom_path_removes_successfully_published_queue(monkeypatch, tmp_path):
    input_file = tmp_path / "handoff" / "news.json"
    rejected_file = tmp_path / "quarantine" / "rejected.json"
    input_file.parent.mkdir(parents=True)
    input_file.write_text(json.dumps([valid_item()]), encoding="utf-8")

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-server-key")
    monkeypatch.setenv("LMN_INPUT_FILE", str(input_file))
    monkeypatch.setenv("LMN_REJECTED_FILE", str(rejected_file))
    monkeypatch.setattr(publisher, "create_client", lambda *_: FakeClient([[{"id": 1}]]))

    assert publisher.main() == 0
    assert not input_file.exists()
    assert not rejected_file.exists()
