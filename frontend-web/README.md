# Little Mere News — Frontend

This directory contains the Next.js App Router portal and administrative CMS for Little Mere News.

The frontend is only one runtime component of the repository. Content ingestion and publishing are handled by the Python Harvester/Publisher services, while persistent data, authentication and row-level authorization live in Supabase/PostgreSQL.

## Requirements

- Node.js 22 (the version used by GitHub Actions)
- npm
- a Supabase project for real development/production, or the repository-owned HTTP fixture for deterministic browser tests

No Ollama, GPU, Hyper-V VM or live news feed is required to build or test the frontend.

## Environment

Create the local environment file from the checked-in example:

```bash
cp .env.example .env.local
```

The current contract is:

- `NEXT_PUBLIC_SITE_URL` — canonical public origin used by metadata, sitemap and robots. Use the deployed HTTPS origin in production.
- `NEXT_PUBLIC_SUPABASE_URL` — public Supabase project URL.
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` — public Supabase anonymous key.
- `SUPABASE_SERVICE_ROLE_KEY` — server-only privileged key. Never expose this value through a `NEXT_PUBLIC_*` variable, browser code, screenshots or logs.
- `ADMIN_PHANTOM_PATH` — optional administrative URL obscurity. It is not authentication, authorization or a security boundary.

Production administrative access still requires Supabase Auth, server-side membership in `public.admin_users`, and PostgreSQL RLS.

## Install and development

From this directory:

```bash
npm ci
npm run dev
```

The default local origin is `http://localhost:3000`.

## Production build and runtime

The same production boundary exercised by CI is:

```bash
npm ci
npm audit --omit=dev --audit-level=high
npm audit --audit-level=high
npm run lint
npm run typecheck
npm run build
npm run start -- -H 127.0.0.1 -p 3000
```

After startup, application liveness is available at:

```text
GET /api/health
```

A `200` response from `/api/health` means the Next.js process can serve the route. It deliberately does **not** prove that Supabase, Ollama, external feeds, DNS or the Python jobs are ready. Provider/database behavior is validated by their own integration/tests and should be monitored separately in a deployed environment.

## Deterministic browser E2E

Browser tests run the production Next.js server against `e2e/fake-supabase.mjs`, a repository-owned loopback contract double containing synthetic users/news only.

This boundary proves public routing/states, authentication/authorization flows and representative CMS accessibility without production secrets or a live Supabase project.

See [`../docs/testing.md`](../docs/testing.md) for exact local commands and test limitations.

## Database and admin bootstrap

The frontend does not own database migrations. Apply the SQL files in `../supabase/migrations/` in filename order using a trusted database/admin channel.

To grant a real authenticated account CMS privileges, insert that user's UUID into `public.admin_users` through a trusted server/database administrative path. There is intentionally no browser self-enrollment path.

## Deployment boundary

A frontend deployment needs:

1. Node.js-compatible hosting for `next build` / `next start` (or a compatible managed Next.js platform).
2. `NEXT_PUBLIC_SITE_URL` set to the final HTTPS origin.
3. valid Supabase public credentials plus the server-only service-role credential where server code requires it.
4. the database migrations applied before depending on admin/RLS behavior.

The Harvester, Publisher and optional Ollama runtime are independent components and do not need to run inside the frontend host.

See [`../docs/deployment.md`](../docs/deployment.md) for the repository-wide runtime/deployment contract.

## Security and testing

Do not weaken authorization because `ADMIN_PHANTOM_PATH` is difficult to guess. Security is provided by Auth + server authorization + RLS.

Repository-wide deterministic gates live under `.github/workflows/` and include frontend build/type checks, browser E2E/accessibility, PostgreSQL/RLS tests, Python tests, dependency audits, secret scanning and CodeQL.

For the complete architecture and limitations, use the root [`README.md`](../README.md).