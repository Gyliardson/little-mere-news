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

A production/local worker needs its Python dependencies plus the runtime configuration used by that service. Critical CI does not require live feeds, Ollama or GPU resources; deterministic fixtures cover the important failure modes.

External sources are mutable and untrusted. A deployed Harvester should be treated as a job/worker with observable failures, bounded network behavior and retry policy rather than as part of frontend process health.

### Publisher

`Backend-Publisher/` consumes validated queue items and persists them to Supabase/PostgreSQL with retry/idempotency behavior.

Its Supabase credential is privileged server/job configuration and must never enter browser bundles, public environment variables or logs.

The Publisher can run independently from the frontend host. Its ability to reach the database is a separate operational concern from `/api/health`.

### Optional Ollama/local AI

Ollama is optional runtime infrastructure used behind the Harvester AI-provider boundary. Critical CI and clean-room browser/database gates do not depend on a real model, GPU or stochastic model output.

A deployment without Ollama can still build/test the repository; live ingestion that requires AI processing must provide the configured provider or handle its documented unavailable/fallback behavior.

### Optional Hyper-V topology

`Infrastructure/` preserves the original Windows/Hyper-V orchestration as one supported local deployment topology. It is optional and must not be treated as the only way to develop, test or host the project.

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

## Production smoke verification

Deterministic CI cannot prove DNS, hosted Supabase networking, production secrets, real external feed availability or local Ollama availability. After deploying an environment, perform a bounded smoke check appropriate to that environment:

- frontend origin resolves over HTTPS;
- `/api/health` returns `200`;
- public news read path can reach the intended Supabase project;
- an ordinary authenticated user cannot enter the CMS;
- an intended administrator can authenticate and reach the CMS;
- database RLS remains enabled and migrations match the repository;
- Publisher can perform a controlled idempotent persistence check without exposing credentials;
- Harvester/provider connectivity is checked separately if live ingestion is enabled.

Do not put production secrets or personal data into CI fixtures or screenshots to obtain this evidence.

## What is intentionally manual

The repository does not automatically provision or mutate a production Supabase project from pull-request CI. Creating the hosted project, configuring production secrets, creating a real administrator account and applying reviewed production migrations are external deployment actions.

Likewise, provisioning Hyper-V hosts, GPU drivers or local Ollama models is optional environment-specific work and is not a certification dependency for deterministic repository quality gates.

## Residual operational risks

- external feeds can change or disappear;
- upstream vulnerability databases may lag undisclosed issues;
- a liveness endpoint cannot replace provider-specific monitoring;
- production data can expose migration conflicts absent from an empty disposable database;
- optional local infrastructure depends on host/network configuration outside the repository.
