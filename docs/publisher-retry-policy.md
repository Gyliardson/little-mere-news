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
- an explicitly exposed HTTP status of `408`, `429`, `500`, `502`, `503`, or `504`.

HTTP status metadata may come from `httpx.HTTPStatusError.response.status_code`, a provider exception `status_code`/`status` attribute, or a PostgREST-style `code` only when that value is unambiguously a three-digit HTTP status.

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

PostgreSQL/PostgREST SQLSTATE values are **not** HTTP statuses. For example, RLS SQLSTATE `42501` is five digits and is never interpreted as HTTP `425`. Similarly, ordinary `400`, `401`, `403`, `404`, `409`, `422`, `501`, and other unlisted HTTP responses are not retried by default.

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

`Backend-Publisher/tests/test_provider_failure_policy.py` separately covers the structured transient/permanent provider classification boundary. The provider-shape fidelity gap tracked in #50 remains a separate issue from this cross-run lifetime/orchestration policy.
