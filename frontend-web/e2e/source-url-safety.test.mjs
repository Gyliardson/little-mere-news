import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { chromium } from "playwright";

const baseURL = process.env.E2E_BASE_URL ?? "http://127.0.0.1:3000";
const fixtureURL = `http://127.0.0.1:${process.env.FAKE_SUPABASE_PORT ?? 54321}`;
const newsId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
let browser;
let adminStorageState;
let adminToken;

async function resetFixture() {
  const response = await fetch(`${fixtureURL}/__test__/reset`, { method: "POST" });
  assert.equal(response.status, 200);
}

async function authenticateFixtureAdmin() {
  const response = await fetch(`${fixtureURL}/auth/v1/token?grant_type=password`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email: "admin@example.test", password: "admin-password" }),
  });
  assert.equal(response.status, 200);
  const payload = await response.json();
  assert.ok(payload.access_token);
  return payload.access_token;
}

async function storeSourceUrl(value) {
  const response = await fetch(`${fixtureURL}/rest/v1/news?id=eq.${newsId}`, {
    method: "PATCH",
    headers: {
      authorization: `Bearer ${adminToken}`,
      apikey: "ci-placeholder-anon-key",
      "content-type": "application/json",
    },
    body: JSON.stringify({ source_url: value }),
  });
  assert.equal(response.status, 200);
}

async function signInAdmin(page) {
  await page.goto(`${baseURL}/en/ci-admin/login`, { waitUntil: "domcontentloaded" });
  await page.getByLabel("Corporate Email").fill("admin@example.test");
  await page.getByLabel("Password").fill("admin-password");
  await page.getByRole("button", { name: "Authenticate" }).click();
  await page.getByRole("heading", { name: "Overview" }).waitFor();
}

before(async () => {
  browser = await chromium.launch({ headless: true });
  await resetFixture();
  adminToken = await authenticateFixtureAdmin();

  const bootstrap = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await bootstrap.newPage();
  await signInAdmin(page);
  adminStorageState = await bootstrap.storageState();
  await bootstrap.close();
});

after(async () => {
  await browser?.close();
});

test("CMS fails closed for unsafe stored source URLs", async () => {
  const unsafeValues = [
    "javascript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "/relative/source",
    "not a url",
  ];

  for (const value of unsafeValues) {
    await resetFixture();
    await storeSourceUrl(value);

    const context = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      storageState: adminStorageState,
    });
    const page = await context.newPage();
    await page.goto(`${baseURL}/en/ci-admin/news`, { waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: /View: Deterministic AI fixture/ }).click();

    const dialog = page.getByRole("dialog", { name: "News Details" });
    await dialog.waitFor();
    assert.equal(await dialog.getByRole("link", { name: "Original Link" }).count(), 0);
    assert.equal(await dialog.getByText("Source URL is not navigable").count(), 1);
    assert.equal(await dialog.locator('a[href^="javascript:"]').count(), 0);
    assert.equal(await dialog.locator('a[href^="data:"]').count(), 0);

    await context.close();
  }
});

test("CMS keeps valid HTTP(S) source links navigable with safe new-tab rel", async () => {
  await resetFixture();
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    storageState: adminStorageState,
  });
  const page = await context.newPage();
  await page.goto(`${baseURL}/en/ci-admin/news`, { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: /View: Deterministic AI fixture/ }).click();

  const link = page.getByRole("dialog", { name: "News Details" }).getByRole("link", { name: "Original Link" });
  assert.equal(await link.count(), 1);
  assert.equal(await link.getAttribute("href"), "https://example.test/articles/fixture-ai");
  const rel = (await link.getAttribute("rel")) ?? "";
  assert.ok(rel.includes("noopener"));
  assert.ok(rel.includes("noreferrer"));

  await context.close();
});
