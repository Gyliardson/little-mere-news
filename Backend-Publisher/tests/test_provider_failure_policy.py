import importlib.util
from pathlib import Path
from types import SimpleNamespace

import httpx
from postgrest.exceptions import APIError

ROOT = Path(__file__).resolve().parents[1]

policy_spec = importlib.util.spec_from_file_location(
    "lmn_publisher_failure_policy", ROOT / "failure_policy.py"
)
policy = importlib.util.module_from_spec(policy_spec)
assert policy_spec.loader is not None
policy_spec.loader.exec_module(policy)

publisher_spec = importlib.util.spec_from_file_location("lmn_publisher_retry", ROOT / "main.py")
publisher = importlib.util.module_from_spec(publisher_spec)
assert publisher_spec.loader is not None
publisher_spec.loader.exec_module(publisher)


def valid_item():
    return {
        "category": "AI",
        "source_name": "Example",
        "source_url": "https://example.com/article",
        "title_en": "Title",
        "title_pt": "Titulo",
        "summary_en": "Summary",
        "summary_pt": "Resumo",
    }


class FakeQuery:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)

    def upsert(self, _item, **_kwargs):
        return self

    def execute(self):
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(data=outcome)


class FakeClient:
    def __init__(self, outcomes):
        self.query = FakeQuery(outcomes)

    def table(self, name):
        assert name == "news"
        return self.query


def http_status_error(status):
    request = httpx.Request("POST", "https://example.supabase.co/rest/v1/news")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError("provider response failed", request=request, response=response)


def test_structured_retryable_http_statuses_are_explicit_and_bounded():
    for status in (408, 429, 500, 502, 503, 504):
        assert policy.is_retryable_publish_exception(http_status_error(status)) is True

    for status in (400, 401, 403, 404, 409, 422, 501):
        assert policy.is_retryable_publish_exception(http_status_error(status)) is False


def test_postgrest_numeric_http_code_is_classified_without_message_parsing():
    transient = APIError(
        {
            "code": 503,
            "details": None,
            "hint": None,
            "message": "arbitrary provider text that policy must not parse",
        }
    )

    assert policy.provider_http_status(transient) == 503
    assert policy.is_retryable_publish_exception(transient) is True


def test_postgrest_sqlstate_auth_failure_is_not_mistaken_for_http_status():
    rls_error = APIError(
        {
            "code": "42501",
            "details": None,
            "hint": None,
            "message": "new row violates row-level security policy",
        }
    )

    assert policy.provider_http_status(rls_error) is None
    assert policy.is_retryable_publish_exception(rls_error) is False


def test_publish_with_retry_recovers_after_throttling_status():
    client = FakeClient([http_status_error(429), [{"id": 1}]])
    sleeps = []

    result = publisher.publish_with_retry(client, valid_item(), sleep_fn=sleeps.append)

    assert result == "published"
    assert sleeps == [publisher.RETRY_BACKOFF_SECONDS]


def test_publish_with_retry_retains_server_failure_after_max_attempts():
    client = FakeClient([http_status_error(503) for _ in range(publisher.MAX_ATTEMPTS)])
    sleeps = []

    result = publisher.publish_with_retry(client, valid_item(), sleep_fn=sleeps.append)

    assert result[0] == "retryable_failure"
    assert len(sleeps) == publisher.MAX_ATTEMPTS - 1


def test_publish_with_retry_quarantines_structured_auth_failure_immediately():
    auth_error = APIError(
        {
            "code": "42501",
            "details": None,
            "hint": None,
            "message": "authorization denied",
        }
    )
    client = FakeClient([auth_error])
    sleeps = []

    result = publisher.publish_with_retry(client, valid_item(), sleep_fn=sleeps.append)

    assert result[0] == "permanent_failure"
    assert sleeps == []
