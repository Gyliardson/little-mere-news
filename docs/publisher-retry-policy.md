# Publisher retry policy

The Publisher treats a failed Supabase/PostgREST write as **retryable only when structured evidence identifies a transient condition**. It never searches exception messages for words such as `timeout`, `rate limit`, `temporary`, or `server error`.

## Automatically retried

Each item receives at most `MAX_ATTEMPTS` attempts with the existing bounded linear backoff. The following failures are retryable:

- `httpx.TimeoutException`;
- `httpx.NetworkError` (including connection/protocol failures represented by that hierarchy);
- an explicitly exposed HTTP status of `408`, `429`, `500`, `502`, `503`, or `504`.

HTTP status metadata may come from `httpx.HTTPStatusError.response.status_code`, a provider exception `status_code`/`status` attribute, or a PostgREST-style `code` only when that value is unambiguously a three-digit HTTP status.

If all attempts fail, the validated article remains in the durable Publisher retry queue. The run exits non-zero as before, so orchestration cannot report a partial publication as successful.

## Not automatically retried

Other failures are permanent for automatic processing and go to quarantine for operator review. This includes validation/schema failures and authorization/RLS failures unless a future provider contract supplies separate structured evidence that makes a retry safe.

PostgreSQL/PostgREST SQLSTATE values are **not** HTTP statuses. For example, RLS SQLSTATE `42501` is five digits and is never interpreted as HTTP `425`. Similarly, ordinary `400`, `401`, `403`, `404`, `409`, `422`, `501`, and other unlisted HTTP responses are not retried by default.

This is intentionally conservative: false-positive retries of auth/schema defects create noisy loops and delay diagnosis, whereas known transient network/throttling/server conditions are safe to retry within a small bound.

## Deterministic verification

`Backend-Publisher/tests/test_provider_failure_policy.py` covers:

- transient HTTP status classification;
- permanent client/auth status classification;
- actual PostgREST `APIError` shape with numeric HTTP-like `code`;
- actual PostgREST `APIError` shape with SQLSTATE `42501`;
- successful recovery after one `429`;
- retained retry state after bounded `503` exhaustion;
- immediate permanent classification for structured authorization failure.

The existing Publisher suite continues to prove transport retries, durable retry/quarantine persistence, idempotent publication, cross-run retention, and queue ownership. No test requires live Supabase or network access.
