# Testing Little Mere News

The repository separates deterministic quality gates from optional live-environment smoke tests.

## Browser E2E

Browser regressions live in `frontend-web/e2e/` and use Playwright's Chromium runtime through Node's built-in test runner.

From `frontend-web/`:

```bash
npm ci
npx playwright install chromium
npm run build
NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:54321 \
NEXT_PUBLIC_SUPABASE_ANON_KEY=local-placeholder \
SUPABASE_SERVICE_ROLE_KEY=local-placeholder \
ADMIN_PHANTOM_PATH=ci-admin \
npm run start -- -H 127.0.0.1 -p 3000
```

In another shell:

```bash
cd frontend-web
E2E_BASE_URL=http://127.0.0.1:3000 npm run test:e2e
```

The deterministic suite intentionally points Supabase at an unavailable loopback endpoint for public error-state coverage. It does not use production credentials, a live Supabase project, Ollama, GPU resources, live feeds, or the Hyper-V topology.

Current browser coverage proves:

- unsupported locale segments fail closed with not-found behavior;
- the public feed renders a user-safe provider failure state instead of leaking backend details;
- the administrative login form exposes programmatic labels and keyboard-reachable controls;
- representative public/login pages satisfy structural accessibility checks for image alternatives, control names, and form labels.

The browser workflow builds and starts the production Next.js server before running the suite. Screenshot/media generation is intentionally separate from behavioral tests.

## Current limitation

The browser suite does not yet emulate a complete authenticated Supabase administrator session. Authorized CMS behavior remains covered by server-side authorization/RLS contract tests but still needs a deterministic browser-level authenticated fixture before the E2E program gate can be considered complete.

## Other deterministic gates

The main CI workflow also validates frontend lint/typecheck/build, Harvester tests, Publisher tests, and the PostgreSQL migration/RLS contract. Critical CI must remain independent from real secrets and external services.
