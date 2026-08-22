# Testing Little Mere News

The repository separates deterministic quality gates from optional live-environment smoke tests.

## Browser E2E

Browser regressions live in `frontend-web/e2e/` and use Playwright's Chromium runtime through Node's built-in test runner.

From `frontend-web/`, install and build first:

```bash
npm ci
npx playwright install chromium
npm run build
```

Start the repository-owned Supabase HTTP fixture:

```bash
E2E_BASE_URL=http://127.0.0.1:3000 node e2e/fake-supabase.mjs
```

In another shell, start the production Next.js server against that fixture:

```bash
NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:54321 \
NEXT_PUBLIC_SUPABASE_ANON_KEY=local-placeholder \
SUPABASE_SERVICE_ROLE_KEY=local-placeholder \
ADMIN_PHANTOM_PATH=ci-admin \
npm run start -- -H 127.0.0.1 -p 3000
```

Then run the browser suite:

```bash
E2E_BASE_URL=http://127.0.0.1:3000 npm run test:e2e
```

The fixture contains synthetic administrator, ordinary authenticated-user, and news records. It implements only the Supabase Auth/PostgREST contract surface required by the browser tests. It is not a production Supabase emulator and must never be used as a security bypass or deployment dependency.

Current browser coverage proves:

- unsupported locale segments fail closed with not-found behavior;
- the public feed renders a user-safe provider failure state instead of leaking backend details;
- an existing article detail renders through the real route and a missing article returns not-found behavior;
- the administrative login form exposes programmatic labels and keyboard-reachable controls;
- a request without a session is returned to the login boundary;
- an authenticated ordinary user is denied administrative route access;
- a synthetic administrator passes the real browser sign-in, SSR session, server authorization, and `admin_users` membership path before reaching the dashboard;
- CMS news dialogs expose dialog semantics, keyboard dismissal/focus restoration, accessible icon-button names, and programmatically associated edit labels;
- administrator update and delete operations cross the real Next.js Server Action boundary and reach the deterministic Supabase mutation surface;
- a captured real administrator update Server Action, replayed with an ordinary user's authenticated browser cookie, returns `Forbidden` and does not reach the Supabase mutation surface;
- stored article source URLs are revalidated at both public and CMS presentation boundaries: valid absolute HTTP(S) links remain navigable with `noopener noreferrer`, while `javascript:`, `data:`, relative and malformed stored values render as non-clickable CMS status text;
- representative public, article, and login pages are checked for document language, main landmark count, image alternatives, accessible button/link names, form labels, duplicate IDs, empty/skipped heading structure, positive `tabindex`, and keyboard reachability of representative primary controls.

The browser workflow starts the deterministic Supabase fixture before the production build so database-backed App Router work cannot accidentally depend on a missing provider, then starts the built Next.js server and runs the suite. It uses no production credentials, live Supabase project, Ollama, GPU resources, live feeds, or Hyper-V topology. On failure, it uploads Next.js/fake-Supabase logs and a diagnostic browser screenshot for a short retention period.

## Accessibility scope

The browser accessibility regressions are a **representative deterministic structural and keyboard gate**, not a claim of automated WCAG conformance and not a replacement for a full axe/screen-reader/manual audit. They intentionally exercise stable properties that can be proved without adding a heavyweight browser matrix: semantic landmarks, names/labels, IDs, heading structure, tab-order anti-patterns, and keyboard reachability on representative public/admin pages.

The following still require manual or specialized review when a visual release is approved:

- actual color-contrast measurements across all theme/state combinations;
- screen-reader announcement quality and reading order beyond DOM semantics;
- zoom/reflow behavior across the full supported viewport range;
- focus visibility styling in every interactive state;
- motion/reduced-motion behavior and other assistive-technology-specific interactions.

A green browser gate must therefore be cited only for the checks it executes, not as blanket accessibility certification.

## Security gates

Security checks are explicit and independently reviewable across the main CI, Security, and CodeQL workflows.

- the main CI performs blocking `npm audit` checks for both production dependencies and the complete frontend dependency tree before lint, typecheck, and production build;
- `pip-audit` checks both production Python requirement sets and fails the Security workflow when an actionable dependency vulnerability is reported;
- Gitleaks scans the full committed Git history with findings redacted. The workflow pins the scanner version and verifies the downloaded release archive checksum before execution;
- CodeQL analyzes JavaScript/TypeScript and Python using a commit-pinned GitHub action and least-privilege workflow permissions. SARIF upload uses only the `security-events: write` permission required by CodeQL.

The checked-in frontend package manifests are the audited dependency state; remediation candidates are not treated as a security claim until committed. Dependency scans still rely on upstream advisory data, so a clean run is evidence for the current advisory set rather than proof that no undisclosed vulnerability exists.

## Test boundaries

The local Supabase fixture is deliberately a contract double rather than a substitute for PostgreSQL/RLS integration tests. Database authorization and uniqueness remain exercised independently by `supabase/tests/rls_contract.sql` against disposable PostgreSQL. That contract explicitly verifies ordinary authenticated users cannot insert, update, delete, or self-enroll as administrators, while an authenticated durable admin can mutate news.

Likewise, deterministic browser success does not prove production networking, DNS, third-party availability, a particular hosted Supabase deployment, or full assistive-technology compatibility. Those remain deployment/manual-smoke concerns and should not introduce real secrets into pull-request CI.

## Other deterministic gates

The main CI workflow also validates frontend lint/typecheck/build, Harvester tests, Publisher tests, and the PostgreSQL migration/RLS contract. Critical CI must remain independent from real secrets and external services.
