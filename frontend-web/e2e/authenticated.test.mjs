import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { chromium } from "playwright";

const baseURL = process.env.E2E_BASE_URL ?? "http://127.0.0.1:3000";
const fixtureURL = `http://127.0.0.1:${process.env.FAKE_SUPABASE_PORT ?? 54321}`;
let browser;
let adminStorageState;

async function resetFixture() {
  const response = await fetch(`${fixtureURL}/__test__/reset`, { method: "POST" });
  assert.equal(response.status, 200);
}

async function fixtureState() {
  const response = await fetch(`${fixtureURL}/__test__/state`);
  assert.equal(response.status, 200);
  return response.json();
}

async function signIn(page, email = "admin@example.test", password = "admin-password") {
  await page.goto(`${baseURL}/en/ci-admin/login`, { waitUntil: "domcontentloaded" });
  await page.getByLabel("Corporate Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Authenticate" }).click();
}

async function signInAdmin(page) {
  await signIn(page);
  await page.getByRole("heading", { name: "Overview" }).waitFor();
  assert.equal(page.url(), `${baseURL}/en/ci-admin`);
}

before(async () => {
  browser = await chromium.launch({ headless: true });
  await resetFixture();

  const bootstrap = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await bootstrap.newPage();
  await signInAdmin(page);
  adminStorageState = await bootstrap.storageState();
  await bootstrap.close();
});

after(async () => {
  await browser?.close();
});

async function newAdminContext() {
  assert.ok(adminStorageState, "admin browser storage must be established by the real sign-in boundary");
  return browser.newContext({
    viewport: { width: 1280, height: 800 },
    storageState: adminStorageState,
  });
}

function replayHeaders(request) {
  const headers = { ...request.headers() };
  for (const name of [
    "cookie",
    "content-length",
    "host",
    "connection",
    "sec-fetch-dest",
    "sec-fetch-mode",
    "sec-fetch-site",
  ]) {
    delete headers[name];
  }
  return headers;
}

async function viewerCookieHeader(context) {
  const cookies = await context.cookies(baseURL);
  return cookies.map((cookie) => `${cookie.name}=${cookie.value}`).join("; ");
}

test("authorized administrator reaches the real dashboard boundary", async () => {
  const context = await newAdminContext();
  const page = await context.newPage();
  await page.goto(`${baseURL}/en/ci-admin`, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: "Overview" }).waitFor();

  assert.equal(await page.getByText("Total Processed (Week)").count(), 1);
  assert.equal(await page.getByText("Articles Today").count(), 1);
  assert.equal(await page.getByText("Active Sources").count(), 1);

  await context.close();
});

test("CMS news dialog has accessible semantics and keyboard close", async () => {
  const context = await newAdminContext();
  const page = await context.newPage();
  await page.goto(`${baseURL}/en/ci-admin/news`, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: "News Manager" }).waitFor();

  const trigger = page.getByRole("button", { name: /View: Deterministic AI fixture/ });
  await trigger.click();
  const dialog = page.getByRole("dialog", { name: "News Details" });
  await dialog.waitFor();
  assert.equal(await dialog.count(), 1);

  await page.keyboard.press("Escape");
  assert.equal(await dialog.count(), 0);
  assert.equal(await trigger.evaluate((node) => document.activeElement === node), true);

  await context.close();
});

test("CMS edit dialog exposes labels and preserves field focus", async () => {
  const context = await newAdminContext();
  const page = await context.newPage();
  await page.goto(`${baseURL}/en/ci-admin/news`, { waitUntil: "domcontentloaded" });

  await page.getByRole("button", { name: /Edit: Deterministic AI fixture/ }).click();
  const dialog = page.getByRole("dialog", { name: "Edit News" });
  await dialog.waitFor();

  assert.equal(await dialog.getByLabel("Category").count(), 1);
  const title = dialog.getByLabel("Title (EN)");
  assert.equal(await title.count(), 1);
  assert.equal(await dialog.getByLabel("Title (PT)").count(), 1);
  assert.equal(await dialog.getByLabel("Summary (EN)").count(), 1);
  assert.equal(await dialog.getByLabel("Summary (PT)").count(), 1);

  await title.focus();
  await page.keyboard.type("X");
  assert.equal(await title.evaluate((node) => document.activeElement === node), true);
  assert.match(await title.inputValue(), /^X|X$/);

  await context.close();
});

test("admin update crosses Server Action and ordinary user cannot replay the mutation", async () => {
  await resetFixture();
  const adminContext = await newAdminContext();
  const adminPage = await adminContext.newPage();
  await adminPage.goto(`${baseURL}/en/ci-admin/news`, { waitUntil: "domcontentloaded" });

  await adminPage.getByRole("button", { name: /Edit: Deterministic AI fixture/ }).click();
  const dialog = adminPage.getByRole("dialog", { name: "Edit News" });
  const title = dialog.getByLabel("Title (EN)");
  await title.fill("Updated through Server Action");

  const actionRequestPromise = adminPage.waitForRequest(
    (request) => request.method() === "POST" && Boolean(request.headers()["next-action"]),
  );
  await dialog.getByRole("button", { name: "Save Changes" }).click();
  const actionRequest = await actionRequestPromise;
  await adminPage.getByRole("status").filter({ hasText: "News updated successfully." }).waitFor();

  const stateAfterAdmin = await fixtureState();
  assert.deepEqual(
    stateAfterAdmin.mutationEvents.map(({ method, id }) => ({ method, id })),
    [{ method: "PATCH", id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa" }],
  );
  assert.equal(stateAfterAdmin.news[0].title_en, "Updated through Server Action");

  const captured = {
    url: actionRequest.url(),
    headers: replayHeaders(actionRequest),
    body: actionRequest.postData(),
  };
  assert.ok(captured.headers["next-action"], "real Next.js Server Action header must be captured");
  assert.ok(captured.body, "real Next.js Server Action body must be captured");
  await adminContext.close();

  const viewerContext = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const viewerPage = await viewerContext.newPage();
  await signIn(viewerPage, "viewer@example.test", "viewer-password");

  // The login page already contains the Restricted Access heading before submit.
  // Waiting on that heading alone can race cookie persistence and produce an
  // unauthenticated replay. Require the protected-route authorization redirect first.
  await viewerPage.waitForURL(`${baseURL}/en/ci-admin/login?error=forbidden`);
  const viewerCookie = await viewerCookieHeader(viewerContext);
  assert.ok(viewerCookie, "viewer auth cookie must be persisted before replaying the Server Action");

  const headers = {
    ...captured.headers,
    cookie: viewerCookie,
    origin: baseURL,
    referer: `${baseURL}/en/ci-admin/news`,
  };
  const replay = await fetch(captured.url, {
    method: "POST",
    headers,
    body: captured.body,
  });
  const replayBody = await replay.text();
  assert.equal(replay.status, 200);
  assert.match(replayBody, /Forbidden/);

  const stateAfterViewer = await fixtureState();
  assert.equal(stateAfterViewer.mutationEvents.length, 1);
  assert.equal(stateAfterViewer.news[0].title_en, "Updated through Server Action");
  await viewerContext.close();
});

test("authorized administrator can delete through the real CMS mutation boundary", async () => {
  await resetFixture();
  const context = await newAdminContext();
  const page = await context.newPage();
  await page.goto(`${baseURL}/en/ci-admin/news`, { waitUntil: "domcontentloaded" });

  await page
    .getByRole("button", { name: /Delete: Deterministic development fixture/ })
    .click();
  const dialog = page.getByRole("dialog", { name: "Confirm Deletion" });
  await dialog.getByRole("button", { name: "Yes, Delete" }).click();
  await page.getByRole("status").filter({ hasText: "News deleted successfully." }).waitFor();

  const state = await fixtureState();
  assert.deepEqual(
    state.mutationEvents.map(({ method, id }) => ({ method, id })),
    [{ method: "DELETE", id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb" }],
  );
  assert.equal(
    state.news.some((item) => item.id === "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
    false,
  );

  await context.close();
});
