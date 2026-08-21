import importlib.util
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from postgrest.exceptions import APIError, generate_default_error_message

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
        self.execute_calls = 0

    def upsert(self, _item, **_kwargs):
        return self

    def execute(self):
        self.execute_calls += 1
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


class AmbiguousCodeError(Exception):
    def __init__(self, code):
        super().__init__("ambiguous provider failure")
        self.code = code


def http_status_error(status):
    request = httpx.Request("POST", "https://example.supabase.co/rest/v1/news")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError("provider response failed", request=request, response=response)


def api_error(
    code,
    message="provider body message must not drive classification",
    details=None,
    hint=None,
):
    return APIError(
        {
            "code": code,
            "details": details,
            "hint": hint,
            "message": message,
        }
    )


def malformed_response_api_error(status):
    response = httpx.Response(status, content=b"<html>upstream failure</html>")
    return APIError(generate_default_error_message(response))


def test_structured_retryable_http_statuses_are_explicit_and_bounded():
    for status in (408, 429, 500, 502, 503, 504):
        assert policy.is_retryable_publish_exception(http_status_error(status)) is True

    for status in (400, 401, 403, 404, 409, 422, 501):
        assert policy.is_retryable_publish_exception(http_status_error(status)) is False


def test_postgrest_apierror_preserves_body_code_not_http_status():
    transient = api_error("PGRST003", "Timed out acquiring connection from connection pool.")

    # This is the actual valid-JSON shape raised by postgrest-py: the body code is
    # available on APIError, while the original HTTP 504 is not exposed here.
    assert transient.code == "PGRST003"
    assert policy.provider_http_status(transient) is None
    assert policy.provider_error_code(transient) == "PGRST003"
    assert policy.is_retryable_publish_exception(transient) is True


@pytest.mark.parametrize("code", ["503", "504"])
def test_numeric_looking_postgrest_body_code_is_not_http_status_or_retryable(code):
    exc = api_error(
        code,
        message="timeout temporary server error 503 504",
        details="temporary 504 timeout while server error 503",
        hint="retry after timeout 503 504",
    )

    assert exc.code == code
    assert policy.provider_error_code(exc) == code
    assert policy.provider_http_status(exc) is None
    assert policy.is_retryable_publish_exception(exc) is False


def test_postgrest_free_form_fields_never_change_unknown_body_code_classification():
    exc = api_error(
        "PGRSTX00",
        message="timeout temporary server error 503 504",
        details="503 timeout; 504 temporary server error",
        hint="temporary retry 503 504 timeout",
    )

    assert policy.provider_http_status(exc) is None
    assert policy.provider_error_code(exc) == "PGRSTX00"
    assert policy.is_retryable_publish_exception(exc) is False


def test_generic_numeric_looking_code_is_not_transport_status():
    exc = AmbiguousCodeError("503")

    assert policy.provider_error_code(exc) == "503"
    assert policy.provider_http_status(exc) is None
    assert policy.is_retryable_publish_exception(exc) is False


@pytest.mark.parametrize("status", [503, 504])
def test_postgrest_malformed_response_integer_code_preserves_real_http_status(status):
    exc = malformed_response_api_error(status)

    # postgrest-py generate_default_error_message() uses the response status as an
    # integer APIError.code when its normal JSON error model cannot be validated.
    assert exc.code == status
    assert policy.provider_error_code(exc) is None
    assert policy.provider_http_status(exc) == status
    assert policy.is_retryable_publish_exception(exc) is True


def test_postgrest_pool_timeout_retries_and_can_recover():
    client = FakeClient([api_error("PGRST003"), [{"id": 1}]])
    sleeps = []

    result = publisher.publish_with_retry(client, valid_item(), sleep_fn=sleeps.append)

    assert result == "published"
    assert client.query.execute_calls == 2
    assert sleeps == [publisher.RETRY_BACKOFF_SECONDS]


def test_numeric_looking_postgrest_body_code_is_permanent_without_retry_loop():
    client = FakeClient(
        [
            api_error(
                "503",
                message="timeout temporary server error 503 504",
                details="temporary 504",
                hint="retry 503",
            )
        ]
    )
    sleeps = []

    result = publisher.publish_with_retry(client, valid_item(), sleep_fn=sleeps.append)

    assert result[0] == "permanent_failure"
    assert client.query.execute_calls == 1
    assert sleeps == []


def test_other_postgrest_5xx_body_codes_remain_fail_closed_without_explicit_policy():
    # PGRST000 maps to 503 but can mean an incorrect db-uri/configuration. Do not
    # infer retryability from a generic 5xx mapping when postgrest-py dropped the
    # HTTP status and only retained the provider body code.
    configuration_error = api_error("PGRST000")
    internal_error = api_error("PGRSTX00")

    assert policy.is_retryable_publish_exception(configuration_error) is False
    assert policy.is_retryable_publish_exception(internal_error) is False


def test_postgrest_sqlstate_auth_failure_is_not_mistaken_for_http_status():
    rls_error = api_error("42501", "new row violates row-level security policy")

    assert policy.provider_http_status(rls_error) is None
    assert policy.provider_error_code(rls_error) == "42501"
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
    client = FakeClient([api_error("42501", "authorization denied")])
    sleeps = []

    result = publisher.publish_with_retry(client, valid_item(), sleep_fn=sleeps.append)

    assert result[0] == "permanent_failure"
    assert sleeps == []
