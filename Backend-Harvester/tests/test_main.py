import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

MODULE_PATH = Path(__file__).resolve().parents[1] / "main.py"
spec = importlib.util.spec_from_file_location("lmn_harvester", MODULE_PATH)
harvester = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(harvester)

VALID_AI = {
    "title_en": "English title",
    "title_pt": "Titulo em portugues",
    "summary_en": "English summary",
    "summary_pt": "Resumo em portugues",
}


def rss_time(year=2026, month=8, day=13, hour=8):
    return (year, month, day, hour, 0, 0, 0, 0, 0)


def test_clean_html_removes_markup_and_normalizes_text():
    assert harvester.clean_html("<p>Hello <strong>world</strong></p>") == "Hello world"
    assert harvester.clean_html(None) == ""


def test_parse_date_is_utc_and_rejects_missing_or_invalid_date():
    entry = SimpleNamespace(published_parsed=rss_time())
    assert harvester.parse_date(entry) == datetime(2026, 8, 13, 8, tzinfo=timezone.utc)
    assert harvester.parse_date(SimpleNamespace()) is None
    invalid = SimpleNamespace(published_parsed=(999999, 99, 99, 99, 99, 99, 0, 0, 0))
    assert harvester.parse_date(invalid) is None


def test_source_url_requires_absolute_http_or_https_identity():
    assert harvester.valid_source_url("https://example.com/article")
    assert harvester.valid_source_url("http://example.com/article")
    assert not harvester.valid_source_url("")
    assert not harvester.valid_source_url("/relative")
    assert not harvester.valid_source_url("javascript:alert(1)")
    assert not harvester.valid_source_url(None)


def test_validate_ai_result_accepts_only_required_non_empty_strings():
    assert harvester.validate_ai_result({**VALID_AI, "ignored": "extra"}) == VALID_AI
    for mutation in (
        {**VALID_AI, "title_en": ""},
        {**VALID_AI, "summary_pt": None},
        {key: value for key, value in VALID_AI.items() if key != "title_pt"},
        [VALID_AI],
    ):
        assert harvester.validate_ai_result(mutation) is None


def test_decode_ollama_response_handles_success_and_malformed_payloads():
    assert harvester.decode_ollama_response({"response": json.dumps(VALID_AI)}) == VALID_AI
    assert harvester.decode_ollama_response({"response": "not-json"}) is None
    assert harvester.decode_ollama_response({"response": json.dumps({"title_en": "partial"})}) is None
    assert harvester.decode_ollama_response({}) is None


def test_atomic_write_json_replaces_queue_without_leaving_temp_file(tmp_path):
    target = tmp_path / "queue.json"
    target.write_text('[{"old": true}]', encoding="utf-8")
    harvester.atomic_write_json(target, [{"new": True}])
    assert json.loads(target.read_text(encoding="utf-8")) == [{"new": True}]
    assert not (tmp_path / ".queue.json.tmp").exists()


def test_harvest_isolates_broken_feed_and_rejects_missing_date_and_url():
    good_feed = SimpleNamespace(
        feed=SimpleNamespace(title="Good Source"),
        entries=[
            SimpleNamespace(
                title="Undated",
                summary="ignored",
                link="https://example.com/undated",
                published_parsed=None,
            ),
            SimpleNamespace(
                title="No URL",
                summary="ignored",
                link="",
                published_parsed=rss_time(),
            ),
            SimpleNamespace(
                title="Valid",
                summary="<p>Useful content</p>",
                link="https://example.com/valid",
                published_parsed=rss_time(),
            ),
        ],
    )

    def loader(url):
        if "broken" in url:
            raise RuntimeError("source unavailable")
        return good_feed

    provider = SimpleNamespace(process=lambda text: VALID_AI)
    result = harvester.harvest(
        {"tech": ["https://broken.example/feed", "https://good.example/feed"]},
        provider=provider,
        now=datetime(2026, 8, 13, 9, tzinfo=timezone.utc),
        feed_loader=loader,
    )
    assert result == [
        {
            "category": "tech",
            "source_name": "Good Source",
            "source_url": "https://example.com/valid",
            **VALID_AI,
        }
    ]


def test_harvest_filters_stale_items_deterministically():
    feed = SimpleNamespace(
        feed=SimpleNamespace(title="Source"),
        entries=[
            SimpleNamespace(
                title="Old",
                summary="old",
                link="https://example.com/old",
                published_parsed=rss_time(day=11),
            )
        ],
    )
    provider = SimpleNamespace(process=lambda text: pytest.fail("AI should not run for stale item"))
    result = harvester.harvest(
        {"tech": ["https://example.com/feed"]},
        provider=provider,
        now=datetime(2026, 8, 13, 9, tzinfo=timezone.utc),
        feed_loader=lambda _: feed,
    )
    assert result == []


def test_harvest_requires_timezone_aware_now():
    with pytest.raises(ValueError, match="timezone-aware"):
        harvester.harvest({}, now=datetime(2026, 8, 13, 9))


def test_fetch_feed_retries_transport_failure(monkeypatch):
    calls = []

    class Response:
        content = b"<rss><channel><title>Source</title></channel></rss>"

        def raise_for_status(self):
            return None

    class Session:
        def get(self, url, timeout):
            calls.append((url, timeout))
            if len(calls) < 3:
                raise requests.Timeout("slow source")
            return Response()

    monkeypatch.setattr(harvester.time, "sleep", lambda _: None)
    parsed = harvester.fetch_feed("https://example.com/feed", session=Session())
    assert len(calls) == 3
    assert parsed.feed.title == "Source"


def test_fetch_feed_rejects_malformed_feed_without_live_network(monkeypatch):
    class Response:
        content = b"this is not a feed"

        def raise_for_status(self):
            return None

    class Session:
        def get(self, url, timeout):
            return Response()

    monkeypatch.setattr(harvester.time, "sleep", lambda _: None)
    with pytest.raises(RuntimeError, match="Feed unavailable after retries"):
        harvester.fetch_feed("https://example.com/feed", session=Session())


def test_ollama_provider_retries_timeout_and_validates_output(monkeypatch):
    calls = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"response": json.dumps(VALID_AI)}

    class Session:
        def post(self, url, json, timeout):
            calls.append((url, timeout, json["model"]))
            if len(calls) == 1:
                raise requests.Timeout("model busy")
            return Response()

    monkeypatch.setattr(harvester.time, "sleep", lambda _: None)
    provider = harvester.OllamaProvider(
        url="http://ollama.invalid/api/generate",
        model="test-model",
        session=Session(),
    )
    assert provider.process("article") == VALID_AI
    assert len(calls) == 2
    assert calls[0][1] == harvester.AI_TIMEOUT_SECONDS


def test_ollama_provider_returns_none_for_malformed_output():
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"response": "not-json"}

    class Session:
        def post(self, url, json, timeout):
            return Response()

    provider = harvester.OllamaProvider(session=Session())
    assert provider.process("article") is None
