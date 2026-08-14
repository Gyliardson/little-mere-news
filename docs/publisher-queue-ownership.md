# Publisher queue ownership

Little Mere News uses file-backed handoff state for portable and optional Hyper-V batch execution. Queue durability depends on explicit ownership boundaries rather than on atomic replacement alone.

The Publisher owns three distinct paths for one queue set:

- `LMN_INPUT_FILE` — newly transferred inbound work;
- `LMN_RETRY_FILE` — transient failures retained for another run;
- `LMN_REJECTED_FILE` — quarantined invalid/permanent failures requiring operator review.

Before reading or mutating any of these files, the Publisher acquires a non-blocking advisory process lock derived from the configured retry path. With `/tmp/lmn/publisher.retry.json`, for example, the lock is `/tmp/lmn/.publisher.retry.json.lock`.

The lock covers the entire queue lifecycle:

`load inbound/retry → merge → publish → persist retry/quarantine → relinquish inbound`

A second Publisher process targeting the same queue set fails non-zero before reading or changing queue state. The lock is released in guaranteed cleanup when the owning process leaves the critical section. A later sequential run can then acquire the same lock normally.

This worker-level lock is required even when using `Infrastructure/Run-LMN-Batch.ps1`. The PowerShell batch lock remains an outer orchestration guard for the supported Hyper-V path, while the Publisher lock protects direct portable/same-host invocations that do not pass through that orchestrator.

The lock file contains no secret or queue payload. It is coordination state only and may remain on disk between runs; ownership is represented by the operating-system advisory lock, not by the file's mere existence.

Do not run two Publisher instances against overlapping queue paths with different retry files. A queue set should be configured as one coherent ownership unit, and inbound/retry/rejected paths must remain distinct as enforced by the worker.
