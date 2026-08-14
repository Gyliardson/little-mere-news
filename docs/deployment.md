# Deployment and clean-room runtime contract

Little Mere News is a hybrid system. The Next.js portal, Supabase/PostgreSQL, Python jobs and optional local AI/Hyper-V infrastructure are separate runtime boundaries. Critical CI deliberately does not require production credentials, live feeds, GPU, Ollama or the original home-lab topology.

## Component map

### Next.js portal/CMS

The frontend is a normal production Next.js application.

Required configuration is documented in `frontend-web/.env.example`. Important variables include:

- `NEXT_PUBLIC_SITE_URL`;
- `NEXT_PUBLIC_SUPABASE_URL`;
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`;
- `SUPABASE_SERVICE_ROLE_KEY` only for trusted server-side code that needs it;
- `ADMIN_PHANTOM_PATH`, which is URL obscurity only and **not** authentication or authorization.

Clean build/start:

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

`GET /api/health` proves Next.js process liveness only. It is not a readiness assertion for Supabase, Python jobs, Ollama or external feeds.

### Supabase/PostgreSQL

Versioned database state is under `supabase/migrations/`. For a new environment:

1. provision compatible PostgreSQL/Supabase;
2. apply migrations in filename order;
3. run/verify the RLS contract;
4. create the intended Supabase Auth account through a trusted path;
5. add that authenticated UUID to `public.admin_users` through a trusted server/database administrative channel.

There is no browser self-enrollment path for administrator membership. Production migrations must be reviewed against existing production data before application.

### Harvester

`Backend-Harvester/` loads configured external feeds, normalizes untrusted content and optionally invokes the local AI provider boundary.

Important runtime variables:

- `LMN_FEEDS_FILE` — feed configuration path;
- `LMN_OUTPUT_FILE` — **Harvester-owned mutable pending pathname**;
- `OLLAMA_API_URL` — optional provider endpoint;
- `OLLAMA_MODEL` — provider model identifier.

The Harvester merges new validated articles with existing pending work under an advisory file lock and atomically replaces the pending file only while it still owns that pending pathname. Malformed existing pending state fails closed.

The Hyper-V launcher does **not** snapshot this mutable file and later delete it. `Backend-Harvester/queue_claim.py` participates in the same pending lock and atomically renames the current pending file into an immutable `.lmn-harvester-claims/batch-<uuid>.json` claim. New Harvester writes then create/merge a fresh pending file. Acknowledgement removes only the exact old claim.

If a launcher dies after claim, the next claim operation recovers the pre-existing claim before creating another one.

### Publisher

`Backend-Publisher/main.py` validates articles and persists them to Supabase/PostgreSQL. Runtime credentials remain server-side:

- `SUPABASE_URL`;
- `SUPABASE_KEY`;
- `LMN_INPUT_FILE` — the **exact input file already claimed for this Publisher invocation**;
- `LMN_RETRY_FILE` — Publisher-owned retained transient failures;
- `LMN_REJECTED_FILE` — Publisher-owned quarantine.

`LMN_INPUT_FILE`, retry and quarantine paths must be distinct. `main.py` removes only the exact `LMN_INPUT_FILE` it was given after persisting its next retry/quarantine state.

Concurrent/overlapping producers must therefore **not** repeatedly replace a shared `LMN_INPUT_FILE`. The repository-provided concurrent boundary is `Backend-Publisher/spool.py`.

#### Immutable Publisher spool

The Hyper-V path uses a spool with:

- `inbox/batch-<uuid>.json` — complete immutable queued batches;
- `processing/batch-<uuid>.json` — the exact batch atomically claimed by the consumer.

Producer flow:

`unique staging file → validate JSON → fsync temp → atomic non-overwriting inbox publish`

Consumer flow:

`existing processing recovery OR inbox → atomic rename → processing → Publisher main.py`

A producer can enqueue B while A is processing. A's cleanup targets `processing/A` and cannot remove `inbox/B`.

A crash during staging/write does not expose a partial final inbox batch. A crash after `inbox → processing` leaves processing state discoverable and recoverable. Replaying an identical batch id while it is still present is idempotent; replay after an ambiguous database write converges through the database `UNIQUE (source_url)`/upsert contract.

`LMN_RETRY_FILE` remains separate from spool batch files. Current retry classification is intentionally narrow until the dedicated retry-taxonomy work is complete; do not interpret this document as claiming that every provider-side transient HTTP condition is already classified optimally.

### Durable handoff lifecycle

The supported Hyper-V lifecycle is:

`CREATED → Harvester pending → Harvester CLAIMED → Publisher QUEUED → Publisher CLAIMED/PROCESSING → PUBLISHED or RETRY/QUARANTINED`

Cleanup is identity-specific. A valid batch must not transition to silent disappearance merely because newer work arrived at a formerly shared pathname.

Crash/restart semantics:

- before Harvester claim: pending remains pending;
- after Harvester claim: immutable claim is recovered first;
- during SCP to Publisher staging: Harvester claim remains and staging is not consumer-visible;
- during Publisher spool publication: incomplete dot-temp state is ignored and the source claim remains replayable;
- after Publisher enqueue but before Harvester acknowledgement: the exact batch id is replayed safely;
- after Publisher processing claim: processing file is recovered before new inbox work;
- after successful DB write but before processing-file cleanup: replay converges via `source_url` idempotency.

See [`publisher-queue-ownership.md`](publisher-queue-ownership.md) for the detailed invariants and deterministic interleaving tests.

## Optional Hyper-V topology

`Infrastructure/Run-LMN-Batch.ps1` preserves the Windows/Hyper-V deployment option while enforcing the queue ownership protocol.

### Host-global launcher serialization

The launcher uses `Infrastructure/Lmn-HostLock.ps1`. Its lock key is derived from the shared VM/IP resource identities and, by default, is stored below Windows `CommonApplicationData` (`ProgramData`) rather than below the repository checkout.

Two clones/worktrees on the **same Windows host** targeting the same LMN VM/IP resources therefore contend for the same operating-system exclusive file lock. The correctness tests start two independent `pwsh` processes from different checkout directories and force this contention.

The host-global lock is an outer orchestration guard. Queue safety does not rely on it alone: Harvester claim and Publisher spool ownership remain explicit and recoverable on the remote VMs.

This does not claim cross-host distributed locking. If multiple physical Windows hosts are ever allowed to control the same VM/storage resources, that topology needs a shared/remote coordination boundary rather than assuming the single-host ProgramData lock is global across machines.

### SSH host identity

The launcher uses strict host-key verification, batch mode and an explicit `known_hosts` file. VM host keys must be enrolled only after fingerprint verification through a trusted channel. Unknown/changed host keys fail closed.

### Publisher secrets

The launcher does not interpolate `SUPABASE_URL` or `SUPABASE_KEY` from the Windows host command line. Provision them on the trusted Publisher VM in:

`/home/lmnadmin/.config/lmn/publisher.env`

Use owner-only permissions. A representative setup is:

```bash
mkdir -p /home/lmnadmin/.config/lmn
chmod 700 /home/lmnadmin/.config/lmn
chmod 600 /home/lmnadmin/.config/lmn/publisher.env
```

The environment file itself contains deployment-specific values and must never be committed. The launcher verifies that it is readable and that the required variables exist without printing secret values.

### Worker transfer and dependency bootstrap

The launcher transfers repository worker code and ownership helpers at execution time. Worker Python dependency manifests remain canonical under each service's `requirements*.txt` files.

The optional VM setup scripts are deployment conveniences, **not currently evidence by themselves of fully reproducible/supply-chain-pinned bootstrap**. Until the dedicated bootstrap remediation is integrated, operators should treat the canonical requirements files and reviewed repository revision as the dependency contract and review any external Ollama installation/model acquisition separately.

## Deterministic ownership proof

The CI Publisher/Harvester suites force the critical interleavings with barriers/events rather than hoping a scheduler triggers a race:

1. Publisher consumer claims/reads A, pauses, producer enqueues B, then A finishes — B remains processable.
2. launcher claims Harvester A, a later Harvester persists B, then A is acknowledged — B remains pending.
3. two `pwsh` launcher processes from different checkout directories target the same resource identities — the second cannot acquire the host-global lock while the first holds it.
4. consumer/launcher crash after claim — exact claimed state is recovered.
5. producer crash before atomic inbox publication — no partial final batch is consumer-visible.
6. same batch replay — spool/database idempotency converges without a duplicate publication.
7. B arrives while A transitions into retry state — retry A and queued B both survive and are consumed on the next safe pass.

Control cases execute the old vulnerable orderings (`snapshot A → write B → unlink shared pathname`) and demonstrate deterministic data loss. This is evidence that the regression harness crosses the original ownership boundary rather than merely testing happy-path helpers.

## Clean-room verification

From a fresh clone, the expected deterministic verification chain is:

1. install frontend dependencies with `npm ci`;
2. run npm audits, lint, typecheck and production build;
3. install each Python service from its checked-in test requirements and run its deterministic tests;
4. start disposable PostgreSQL, apply migrations and execute `supabase/tests/rls_contract.sql`;
5. start the repository fake-Supabase fixture plus production Next.js server;
6. verify `/api/health` as process liveness;
7. run Browser E2E/accessibility;
8. run Security and CodeQL workflows.

Critical CI uses synthetic/local fixtures and must not contain production secrets.

## Production smoke verification

A deployment smoke should verify, as applicable:

- frontend origin resolves over HTTPS and `/api/health` returns `200`;
- public reads reach the intended Supabase project;
- ordinary authenticated users cannot enter CMS and intended admins can;
- RLS remains enabled and migrations match the reviewed repository state;
- Harvester provider/feed connectivity is checked separately when enabled;
- a controlled Harvester pending → claim → Publisher inbox → processing handoff preserves newer pending/inbox work;
- an intentionally interrupted claimed batch is recoverable after restart;
- retained retry state survives a later inbound batch;
- quarantine remains durable and requires operator review;
- Hyper-V deployments reject untrusted SSH host keys and load Publisher secrets only from the trusted Publisher-side environment file.

## What remains intentionally external/manual

Pull-request CI does not provision or mutate production Supabase, VM host identities, SSH credentials, Hyper-V hosts, GPU drivers or local model runtimes. These require environment-specific operator actions.

The optional local AI runtime is not part of the critical CI guarantee. External installer/model supply-chain properties must be documented honestly and are reviewed separately from deterministic application correctness.

## Residual operational risks

- external feeds can change or disappear;
- advisory/vulnerability databases can lag undisclosed issues;
- production data can expose migration conflicts absent from disposable test data;
- queue durability assumes the filesystem honors the atomic same-filesystem rename/link primitives used by the claim/spool helpers;
- the ProgramData launcher lock serializes one Windows host, not multiple physical hosts;
- quarantined Publisher items require operator review;
- optional VM/Ollama provisioning has supply-chain/reproducibility limits until its dedicated remediation is completed;
- hosted Supabase/network/provider health still needs environment-specific monitoring beyond process liveness.
