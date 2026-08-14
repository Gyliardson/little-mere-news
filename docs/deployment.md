# Deployment and clean-room runtime contract

Little Mere News is a hybrid system. The frontend, PostgreSQL/Supabase database, Python jobs and optional local AI runtime are separate components with different deployment boundaries.

## Component map

### Next.js portal/CMS

Runs as a normal production Next.js application.

Required runtime configuration:

- `NEXT_PUBLIC_SITE_URL`
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY` as a server-only secret where privileged server code requires it
- `ADMIN_PHANTOM_PATH` as optional URL obscurity only

Build/start contract:

```bash
cd frontend-web
npm ci
npm audit --omit=dev --audit-level=high
npm audit --audit-level=high
npm run lint
npm run typecheck
npm run build
npm run start -- -H 0.0.0.0 -p 3000
```

`GET /api/health` is a liveness check for the Next.js application process. It is intentionally not a readiness claim for Supabase, the Python services, Ollama or external sources.

### Supabase/PostgreSQL

Database state is versioned under `supabase/migrations/`.

For a new environment:

1. provision a compatible PostgreSQL/Supabase database;
2. apply migrations in filename order;
3. verify the RLS/security contract;
4. create the intended Supabase Auth user through the normal trusted authentication/admin path;
5. add that authenticated UUID to `public.admin_users` through a trusted server/database administrative channel.

Do not expose a browser self-enrollment path for administrator membership.

Production migrations should always be reviewed against existing data before being applied. The uniqueness contract for `news.source_url` intentionally does not delete conflicting production data silently.

### Harvester

`Backend-Harvester/` consumes configured external feeds, normalizes source data and optionally calls the configured local AI provider boundary.

Runtime configuration used by the worker includes:

- `LMN_FEEDS_FILE` — feed configuration JSON path; default `/home/lmnadmin/feeds.json`;
- `LMN_OUTPUT_FILE` — Harvester-owned pending handoff file; default `/home/lmnadmin/news_to_publish.json`;
- `OLLAMA_API_URL` — optional local/provider endpoint;
- `OLLAMA_MODEL` — provider model name.

The Harvester output is **pending/untransferred state**, not a disposable scratch file. A new run merges validated articles with any previous untransferred batch under an advisory file lock and deduplicates by `source_url`. If existing pending state is malformed, the worker fails non-zero rather than replacing it. This makes an interrupted transfer recoverable and prevents a later harvest from silently discarding the previous batch.

A portable host should set explicit paths/endpoints appropriate to that environment instead of relying on the original `/home/lmnadmin` or private-network defaults. Critical CI does not require live feeds, Ollama or GPU resources; deterministic fixtures cover the important failure modes.

External sources are mutable and untrusted. A deployed Harvester should be treated as a job/worker with observable failures, bounded network behavior and retry policy rather than as part of frontend process health.

### Publisher

`Backend-Publisher/` consumes validated inbound items and persists them to Supabase/PostgreSQL with idempotency and bounded retry behavior.

Runtime configuration:

- `SUPABASE_URL` — Supabase project/API URL for the server-side job;
- `SUPABASE_KEY` — privileged server/job credential; never expose it to browser code, public environment variables or logs;
- `LMN_INPUT_FILE` — new inbound batch owned by the transfer/orchestration boundary; default `/home/lmnadmin/news_to_publish.inbound.json`;
- `LMN_RETRY_FILE` — Publisher-owned retained **transient** failures; default `/home/lmnadmin/news_to_publish.retry.json`;
- `LMN_REJECTED_FILE` — durable quarantine for invalid payloads and non-transient/permanent publication failures; default `/home/lmnadmin/news_to_publish.rejected.json`.

These three Publisher paths must be distinct. The Publisher rejects a configuration that aliases inbound, retry and quarantine ownership. In particular, **do not configure the Harvester output and Publisher retry file to the same path**.

At the beginning of a publish run, retained retry work and the new inbound batch are merged deterministically by `source_url`. Network/time-out failures receive the bounded retry policy and remain in `LMN_RETRY_FILE` only when they are still retryable after those attempts. Invalid payloads and non-transport failures are moved to `LMN_REJECTED_FILE` rather than being retried indefinitely. Exception details are logged only by type; the quarantine persists the payload, not raw exception text that could contain sensitive provider details.

The Publisher persists its next retry state and rejected state before relinquishing the inbound file. If the process crashes after a successful database write but before relinquishing inbound state, the database `UNIQUE (source_url)` / idempotent upsert contract makes the replay a safe duplicate no-op rather than data loss.

A Publisher run exits non-zero when it creates new retryable or quarantine work, or when queue/result state cannot be handled safely. This makes partial failure visible to orchestration. Quarantined items are not active input: a later run with no inbound/retry work succeeds without repeatedly submitting permanent failures. Automation must not report the original partially unsuccessful run as green merely because its rejected state was persisted safely.

### Durable handoff ownership

The file handoff intentionally separates four ownership states:

1. **Harvester pending** — `LMN_OUTPUT_FILE`, which survives until transfer is confirmed.
2. **Publisher inbound** — `LMN_INPUT_FILE`, a newly transferred batch.
3. **Publisher retry** — `LMN_RETRY_FILE`, transient failures retained independently across future inbound batches.
4. **Publisher rejected** — `LMN_REJECTED_FILE`, quarantine for invalid or permanent failures that must not be retried automatically.

For a same-host deployment, use four distinct files in one directory, for example:

```bash
export LMN_OUTPUT_FILE=/tmp/lmn/harvester.pending.json
export LMN_INPUT_FILE=/tmp/lmn/publisher.inbound.json
export LMN_RETRY_FILE=/tmp/lmn/publisher.retry.json
export LMN_REJECTED_FILE=/tmp/lmn/publisher.rejected.json
```

A same-path `LMN_OUTPUT_FILE == LMN_INPUT_FILE` configuration is no longer the recommended portable contract because it makes overlapping worker ownership ambiguous. The safe topology uses a transfer/claim step between Harvester pending and Publisher inbound. The Hyper-V orchestrator implements that ownership transfer explicitly.

### Optional Ollama/local AI

Ollama is optional runtime infrastructure used behind the Harvester AI-provider boundary. Critical CI and clean-room browser/database gates do not depend on a real model, GPU or stochastic model output.

A deployment without Ollama can still build/test the repository; live ingestion that requires AI processing must provide the configured provider or handle its documented unavailable/fallback behavior.

### Optional Hyper-V topology

`Infrastructure/Run-LMN-Batch.ps1` preserves the original Windows/Hyper-V topology while enforcing the durable ownership protocol and a strict SSH trust boundary.

#### SSH host identity

The orchestrator uses `StrictHostKeyChecking=yes`, `BatchMode=yes` and an explicit `known_hosts` file. By default it uses the current account's standard `~/.ssh/known_hosts`; set `LMN_KNOWN_HOSTS_FILE` to an alternate file when the batch host uses a dedicated trust store. The file must already exist before a batch starts.

Enroll the Harvester (`10.0.100.10`) and Publisher (`10.0.100.30`) host keys only after comparing their fingerprints through a trusted channel, such as the VM console or a separately authenticated administrative path. `ssh-keyscan` can collect candidate public host keys, but **do not treat `ssh-keyscan` output obtained over the same untrusted network as proof of server identity**. One safe workflow is to collect candidate keys, inspect their fingerprints with `ssh-keygen -lf`, compare those fingerprints with the VM console, and only then append the verified keys to the configured `known_hosts` file.

Because `BatchMode=yes` disables interactive password/host-key prompts, the orchestration account must also have non-interactive SSH authentication configured beforehand. Unknown or changed host keys fail closed rather than being silently accepted.

#### Publisher secret provisioning

The Hyper-V orchestrator no longer reads or sends `SUPABASE_URL` / `SUPABASE_KEY` from the Windows host command line. Provision these values directly on the trusted Publisher VM in the shell-compatible file:

`/home/lmnadmin/.config/lmn/publisher.env`

For example, from a trusted Publisher console/admin session, create the directory/file without placing real values in shell history where possible, then enforce owner-only permissions:

```bash
mkdir -p /home/lmnadmin/.config/lmn
chmod 700 /home/lmnadmin/.config/lmn
chmod 600 /home/lmnadmin/.config/lmn/publisher.env
```

The file must define non-empty `SUPABASE_URL` and `SUPABASE_KEY` values. It is an external deployment secret and must never be committed. The orchestrator verifies that the file is readable and that both variables exist after sourcing it, but does not echo their values. Queue-path variables remain non-secret orchestration arguments.

The orchestrator then enforces the operational contract:

- every SSH/SCP boundary uses the verified host-key trust store;
- the Publisher credential remains server-side on the Publisher VM instead of being interpolated into SSH command arguments;
- a failed Harvester exits the batch without deleting pending state;
- the Harvester source file is deleted only after Publisher inbound transfer succeeds;
- Publisher inbound never overwrites Publisher retry state;
- Publisher non-zero exit is propagated instead of printing a false success;
- VM shutdown after a Publisher failure is allowed because any active retry state or newly produced quarantine is already durable on disk.

The Hyper-V topology is optional and must not be treated as the only way to develop, test or host the project.

## Clean-room verification

The repository deliberately composes clean-room proof from focused deterministic gates rather than a single infrastructure-heavy environment.

From a fresh clone, the expected verification chain is:

1. install frontend dependencies with `npm ci`;
2. run dependency audits, lint, typecheck and production build;
3. install each Python service's requirements and run its tests;
4. start disposable PostgreSQL, apply all migrations and execute `supabase/tests/rls_contract.sql`;
5. start the repository-owned fake Supabase HTTP fixture and production Next.js server;
6. verify `/api/health` responds;
7. run deterministic Browser E2E/accessibility tests;
8. run security gates (Python audits, Gitleaks and CodeQL through GitHub Actions).

The GitHub Actions workflows implement these boundaries independently so failures remain attributable and CI never needs production credentials.

For a portable file-handoff smoke test, configure distinct files and explicitly move/copy a completed Harvester pending batch into the Publisher inbound path only after the source batch is durable:

```bash
export LMN_OUTPUT_FILE=/tmp/lmn/harvester.pending.json
export LMN_INPUT_FILE=/tmp/lmn/publisher.inbound.json
export LMN_RETRY_FILE=/tmp/lmn/publisher.retry.json
export LMN_REJECTED_FILE=/tmp/lmn/publisher.rejected.json
```

A correct smoke test must include at least one partial Publisher failure followed by a second inbound batch and prove that retained transient work and the new item remain recoverable. It should also prove that a permanent failure moves to quarantine and is not retried on the following no-work run. Merely proving `process_batch()` in isolation is insufficient for the end-to-end durability claim.

## Production smoke verification

Deterministic CI cannot prove DNS, hosted Supabase networking, production secrets, real external feed availability or local Ollama availability. After deploying an environment, perform a bounded smoke check appropriate to that environment:

- frontend origin resolves over HTTPS;
- `/api/health` returns `200`;
- public news read path can reach the intended Supabase project;
- an ordinary authenticated user cannot enter the CMS;
- an intended administrator can authenticate and reach the CMS;
- database RLS remains enabled and migrations match the repository;
- Publisher can perform a controlled idempotent persistence check without exposing credentials;
- Harvester pending → Publisher inbound ownership transfer preserves any Publisher retry file;
- a retained transient Publisher failure survives a subsequent inbound batch;
- a permanent Publisher failure is quarantined and is not retried automatically;
- Hyper-V deployments reject unknown/changed SSH host keys and load Publisher secrets only from the trusted Publisher-side environment file;
- Harvester/provider connectivity is checked separately if live ingestion is enabled.

Do not put production secrets or personal data into CI fixtures or screenshots to obtain this evidence.

## What is intentionally manual

The repository does not automatically provision or mutate a production Supabase project from pull-request CI. Creating the hosted project, configuring production secrets, creating a real administrator account and applying reviewed production migrations are external deployment actions.

For the optional Hyper-V path, verifying/enrolling VM host-key fingerprints, provisioning non-interactive SSH credentials and creating the Publisher-side `publisher.env` file are explicit manual trust/secret setup steps. They are intentionally not automated from repository CI because CI does not possess production VM identity or credentials.

Likewise, provisioning Hyper-V hosts, GPU drivers or local Ollama models is optional environment-specific work and is not a certification dependency for deterministic repository quality gates.

## Residual operational risks

- external feeds can change or disappear;
- upstream vulnerability databases may lag undisclosed issues;
- a liveness endpoint cannot replace provider-specific monitoring;
- production data can expose migration conflicts absent from an empty disposable database;
- file-based handoff depends on durable local/shared storage and the documented ownership transfer;
- quarantined Publisher items require operator review rather than automatic retry;
- optional local infrastructure depends on correctly provisioned host keys, SSH credentials, VM-local secrets and host/network configuration outside the repository.
