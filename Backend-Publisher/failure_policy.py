"""Structured failure classification for the Publisher provider boundary.

The policy deliberately avoids parsing exception messages. A failure is retryable only
when its type is a known transient transport failure or structured provider metadata
identifies an explicitly transient condition.
"""

from __future__ import annotations

from typing import Any

import httpx

RETRYABLE_HTTP_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
# postgrest-py APIError preserves the JSON body `code`, not necessarily the HTTP
# response status. PGRST003 is specifically the documented 504 pool-acquisition
# timeout. Keep this allowlist narrow: other PGRST 5xx mappings can represent
# configuration/schema/internal failures that should remain fail-closed.
RETRYABLE_POSTGREST_CODES = frozenset({"PGRST003"})


def _coerce_http_status(value: Any) -> int | None:
    """Accept only unambiguous three-digit HTTP status metadata."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if 100 <= value <= 599 else None
    if isinstance(value, str) and len(value) == 3 and value.isdigit():
        status = int(value)
        return status if 100 <= status <= 599 else None
    return None


def provider_http_status(exc: Exception) -> int | None:
    """Extract structured HTTP status metadata without inspecting free-form text."""
    if isinstance(exc, httpx.HTTPStatusError):
        return _coerce_http_status(exc.response.status_code)

    for attribute in ("status_code", "status", "code"):
        status = _coerce_http_status(getattr(exc, attribute, None))
        if status is not None:
            return status

    return None


def provider_error_code(exc: Exception) -> str | None:
    """Extract an explicit provider body code without interpreting its message."""
    value = getattr(exc, "code", None)
    return value if isinstance(value, str) and value else None


def is_retryable_publish_exception(exc: Exception) -> bool:
    """Return whether automatic bounded retry is safe for one publication failure."""
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
        return True

    if provider_error_code(exc) in RETRYABLE_POSTGREST_CODES:
        return True

    status = provider_http_status(exc)
    return status in RETRYABLE_HTTP_STATUSES
