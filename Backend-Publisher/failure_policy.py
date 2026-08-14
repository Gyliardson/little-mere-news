"""Structured failure classification for the Publisher provider boundary.

The policy deliberately avoids parsing exception messages. A failure is retryable only
when its type is a known transient transport failure or structured metadata exposes an
HTTP status that this module explicitly treats as transient.
"""

from __future__ import annotations

from typing import Any

import httpx

RETRYABLE_HTTP_STATUSES = frozenset({408, 429, 500, 502, 503, 504})


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
    """Extract structured HTTP status metadata without inspecting free-form text.

    Supported shapes intentionally cover the Publisher's HTTP/Supabase boundary:
    - ``httpx.HTTPStatusError.response.status_code``;
    - exception ``status_code`` / ``status`` attributes when libraries expose them;
    - PostgREST-style ``code`` when it is actually a three-digit HTTP code.

    PostgreSQL/PostgREST SQLSTATE values such as ``42501`` are five digits and are
    therefore never mistaken for HTTP 425.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        return _coerce_http_status(exc.response.status_code)

    for attribute in ("status_code", "status", "code"):
        status = _coerce_http_status(getattr(exc, attribute, None))
        if status is not None:
            return status

    return None


def is_retryable_publish_exception(exc: Exception) -> bool:
    """Return whether automatic bounded retry is safe for one publication failure."""
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
        return True

    status = provider_http_status(exc)
    return status in RETRYABLE_HTTP_STATUSES
