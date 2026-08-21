# Batch queue ownership

Little Mere News uses file-backed handoff state. Durability is based on **identity + atomic ownership transfer**, not on atomic replacement of one global queue filename.

The supported Hyper-V path has these states:

`Harvester pending → Harvester claimed batch → Publisher inbox batch → Publisher processing batch → published / retry / quarantine`

For every valid batch, the important invariant is that cleanup targets only the exact object previously claimed. A newer batch must never share that pathname.

## Harvester pending and claim

The Harvester may merge newly collected articles into `LMN_OUTPUT_FILE` under its advisory pending lock. The launcher does **not** copy that mutable file and later run `rm` against it.

`Backend-Harvester/queue_claim.py` participates in the same pending lock and atomically renames the current pending file into an immutable `.lmn-harvester-claims/batch-<uuid>.json` claim. Once that rename succeeds:

- the launcher owns that exact claim;
- a concurrent/later Harvester writes a fresh `LMN_OUTPUT_FILE`;
- acknowledging the old claim deletes only the old claim pathname, never newer pending work;
- if the launcher crashes before acknowledgement, the next `claim` returns the existing claim first for recovery.

This is the boundary that prevents a stale launcher snapshot from deleting articles harvested after that snapshot.

## Publisher immutable spool

`Backend-Publisher/spool.py` owns a spool root with two active directories:

- `inbox/` — complete immutable producer-owned batches waiting to be claimed;
- `processing/` — the exact batch currently/recently claimed by the consumer.

A producer first transfers into a unique staging pathname. `spool.py enqueue` validates complete JSON, fsyncs a same-directory temporary file, then atomically publishes the final `inbox/batch-<uuid>.json` **without overwriting an existing batch id**. Temporary dot-files are not consumer-visible. Replaying the same batch id with identical bytes is idempotent; the same id with different bytes fails closed.

The consumer atomically renames one inbox file into `processing/` and passes that exact processing pathname to `Backend-Publisher/main.py` as `LMN_INPUT_FILE`. Publisher cleanup therefore unlinks only the processing file it actually read. A producer may enqueue batch B while batch A is processing and A's cleanup cannot delete B.

If a process dies after the inbox→processing claim but before completion, the next `claim-next` returns the existing processing file before claiming new inbox work. Database `UNIQUE (source_url)` plus idempotent upsert handles replay after an ambiguous successful database write.

`LMN_RETRY_FILE` remains a distinct Publisher-owned active queue for transient failures, and `LMN_REJECTED_FILE` remains durable quarantine for invalid/permanent failures. Publisher's process lock still serializes Publisher instances that share retry/quarantine state; it is complementary to immutable producer/consumer batch identity rather than a substitute for it.

## Host-global launcher ownership

`Infrastructure/Run-LMN-Batch.ps1` uses `Infrastructure/Lmn-HostLock.ps1` to derive a lock from the shared VM/IP resource identities. By default the lock lives below Windows `CommonApplicationData` (`ProgramData`), outside every repository checkout.

Consequently two clones/worktrees on the same Windows host that target the same LMN Hyper-V resources contend for the same operating-system file lock. A repository-relative `$ProjectRoot/lmn-batch.lock` is intentionally forbidden by regression tests.

This host-global lock serializes the supported single-host Hyper-V orchestrator. The remote Harvester claim and Publisher spool protocols remain independently crash-safe so queue correctness does not depend solely on favorable launcher timing.

## Crash/replay semantics

- **Crash before Harvester claim:** pending remains pending.
- **Crash after Harvester claim:** immutable claim remains and is returned first on restart.
- **Crash during SCP to Publisher staging:** Harvester claim remains; partial staging is not inbox work.
- **Crash while publishing an inbox file:** no final batch becomes visible until the atomic non-overwriting publish step.
- **Crash after Publisher enqueue but before Harvester acknowledgement:** the Harvester claim replays the same batch id; identical queued content is a no-op, and a post-publication replay converges through database idempotency.
- **Crash after Publisher inbox→processing claim:** processing batch remains and is recovered before new inbox work.
- **Crash after a database write but before processing-file cleanup:** replay is safe through `source_url` uniqueness/idempotent upsert.

## What is actually proven

Deterministic tests force the critical interleavings rather than waiting for scheduler luck:

1. consumer processes A while producer enqueues B; B remains processable;
2. launcher claims A, Harvester persists B, launcher acknowledges A; B remains pending;
3. two checkout locations targeting the same resource identities cannot acquire overlapping host locks;
4. claimed work survives simulated crash/restart;
5. producer failure before atomic inbox publication exposes no partial JSON batch;
6. same-batch replay converges without duplicate publication;
7. B remains queued while A transitions into retry state, and the next pass processes retained A + B.

Control-case tests also execute the old mutable-path sequences and deterministically demonstrate that `replace B → unlink pathname` and `snapshot A → persist B → unlink pending` can lose B. This verifies that the regression harness crosses the original vulnerable boundary.

## Portable deployments

Do not model a concurrent producer/consumer topology by repeatedly replacing one `LMN_INPUT_FILE`. If producer and Publisher can overlap, use the repository spool helper (or an equivalent protocol with immutable batch identity and atomic claim), and invoke Publisher only on the exact claimed processing file.

A deployment may use different filesystem locations, but it must preserve the same ownership properties. Atomic file replacement alone is not sufficient evidence of durable queue ownership.
