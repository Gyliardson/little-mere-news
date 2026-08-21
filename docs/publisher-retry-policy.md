# Publisher retry policy

The Publisher treats a failed Supabase/PostgREST write as **retryable only when structured evidence identifies a transient condition**. It never searches exception messages for words such as `timeout`, `rate limit`, `temporary`, or `server error`.

## Two bounded retry layers

A transient item is bounded at two separate layers:

1. **In-process attempts** — one eligible processing cycle receives at most `MAX_ATTEMPTS = 3` attempts with the existing short linear backoff.
2. **Cross-run lifetime** — after one in-process cycle is exhausted, the retry file stores `_lmn_retry` metadata containing the durable `cycles`, `first_failed_at`, and `next_attempt_at` values. A later process does not receive a fresh lifetime budget merely because it restarted.

The cross-run policy permits at most `MAX_RETRY_CYCLES = 8` failed processing cycles. Between cycles it uses a bounded exponential schedule beginning at 5 minutes and capped at 60 minutes. This schedule is the repository's bounded equivalent for cross-run throttling, including 429 responses when the provider exception does not expose a trustworthy `Retry-After` value through the current client boundary.

A retained item whose `next_attempt_at` is still in the future is persisted unchanged and is **not sent to Supabase** during that invocation. When the lifetime cycle limit is reached, the item leaves active retry state and is moved to the rejected/quarantine queue for explicit operator review.

Legacy retry items without `_lmn_retry` metadata are treated as cycle zero and migrate to the durable format after their next transient failure. Malformed retry metadata fails closed to quarantine rather than silently resetting the budget.

## Automatically retried

The following failures are eligible for the bounded retry policy:

- `httpx.TimeoutException`;
- `httpx.NetworkError` (including connection/protocol failures represented by that hierarchy);
- an explicitly exposed HTTP status of `408`, `429`, `500`, `502`, `503`, or `504`;
- PostgREST body code `PGRST003`, which PostgREST documents as the HTTP 504 timeout while waiting for a database-pool connection.

HTTP status metadata may come from `httpx.HTTPStatusError.response.status_code` or provider `status_code`/`status` attributes. A generic exception `.code` is **not** accepted as HTTP status evidence merely because it contains a three-digit number.

The pinned PostgREST client has one narrower compatibility shape for malformed/nonconforming error responses: its `generate_default_error_message()` fallback constructs `postgrest.exceptions.APIError` with the original `response.status_code` stored as an **integer** `.code`. The policy recognizes only that concrete integer-`APIError.code` fallback as HTTP status metadata. It does not extend that rule to arbitrary providers or string body codes.

`postgrest-py` valid-JSON errors are different: `APIError` preserves the PostgREST response body's `code`, while the original HTTP status is not necessarily retained on the exception. Those body codes remain provider error metadata. In particular, string values such as `"503"` or `"504"` are not promoted to transport status solely because they look numeric.

The retry policy therefore has a narrow body-code allowlist. `PGRST003` is allowed because its semantics are explicitly transient; the policy does not infer that every PostgREST error mapped to HTTP 5xx is safe to retry. Unknown body codes, including numeric-looking strings, fail closed.

For example, `PGRST000` can represent an incorrect database URI/configuration even though PostgREST maps it to HTTP 503. It remains fail-closed unless the provider boundary later supplies stronger structured evidence.

## Scheduler liveness and head-of-line behavior

Durably retained transient work is no longer represented as an orchestration-fatal exit by itself. The retry queue is already durable and paced, so Publisher returns success when the only incomplete work is retained/deferred transient state. This allows the supported batch launcher to continue into Harvester collection and durably represent independent new feed work instead of suppressing collection until old retry state clears.

When a later Publisher invocation sees both retained retry A and fresh inbound B:

- A is skipped if its durable `next_attempt_at` has not arrived;
- B is still processed independently;
- A remains durable for a future eligible cycle;
- one transient item therefore cannot create unbounded head-of-line starvation for unrelated Publisher inbox batches.

This liveness rule is important because Harvester only considers feed entries inside its freshness window. Retained downstream work must not prevent unrelated upstream news from becoming durable before that window expires.

## Not automatically retried

Other failures are permanent for automatic processing and go to quarantine for operator review. This includes validation/schema failures and authorization/RLS failures unless a future provider contract supplies separate structured evidence that makes a retry safe.

PostgreSQL SQLSTATE values are **not** HTTP statuses. For example, RLS SQLSTATE `42501` is five digits and is never interpreted as HTTP `425`. PostgREST body codes such as `PGRST000` and `PGRSTX00` are likewise not retried merely because PostgREST maps them to 5xx. Ordinary `400`, `401`, `403`, `404`, `409`, `422`, `501`, and other unlisted HTTP responses remain non-retryable by default.

Free-form `message`, `details`, and `hint` fields never drive retry classification, even when they contain text such as `timeout`, `temporary`, `server error`, `503`, or `504`. Exception strings are not scanned for numeric statuses or retry keywords.

Quarantine remains fail-closed and causes a non-zero Publisher exit so orchestration/operator state cannot silently ignore auth/schema/validation defects.

## Deterministic verification

`Backend-Publisher/tests/test_publisher.py` proves, without live Supabase or network access:

- the existing three-attempt in-process bound;
- durable retry metadata creation;
- deterministic cross-run pacing;
- no provider call before `next_attempt_at`;
- lifetime exhaustion into quarantine instead of budget reset;
- corrupt retry metadata failing closed;
- retained transient A not blocking fresh independent B across simulated scheduler invocations;
- permanent/auth/schema-style failures remaining quarantine-signaled;
- queue ownership, idempotent publication, and atomic retry persistence contracts.

`Backend-Publisher/tests/test_provider_failure_policy.py` separately exercises the installed `postgrest.exceptions.APIError` shape, proves `PGRST003` remains retryable despite the absent HTTP-status attribute, proves string body codes such as `"503"`/`"504"` do not become HTTP status, covers the concrete malformed-response integer-status fallback, and proves free-form error text plus RLS/configuration/internal body codes remain fail-closed. No live Supabase service is required for these provider-shape regressions.
