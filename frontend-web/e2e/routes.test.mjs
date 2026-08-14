import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { chromium } from "playwright";

const baseURL = process.env.E2E_BASE_URL ?? "http://127.0.0.1:3000";
const fixtureURL = `http://127.0.0.1:${process.env.FAKE_SUPABASE_PORT ?? 54321}`;
const existingArticleId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const missingArticleId = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
let browser;

async function fixturePost(path, body) {
  const response = await fetch(`${fixtureURL}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  assert.equal(response.status, 200);
}

before(async () => {
  browser = await chromium.launch({ headless: true });
  await fixturePost("/__test__/reset");
});

after(async () => {
  await fixturePost("/__test__/reset");
  await browser?.close();
});

test("unsupported locale returns not found", async () => {
  const page = await browser.newPage();
  const response = await page.goto(`${baseURL}/fr`, { waitUntil: "domcontentloaded" });
  assert.equal(response?.status(), 404);
  await page.close();
});

test("public feed renders a user-safe provider failure state", async () => {
  await fixturePost("/__test__/news-error", { enabled: true });
  const page = await browser.newPage();
  const response = await page.goto(`${baseURL}/en`, { waitUntil: "domcontentloaded" });
  assert.equal(response?.status(), 200);
  const alert = page.getByRole("alert");
  await alert.waitFor();
  assert.match(await alert.textContent(), /News could not be loaded/);
  assert.doesNotMatch(await alert.textContent(), /E2E_PROVIDER_FAILURE|synthetic provider failure/i);
  await page.close();
  await fixturePost("/__test__/news-error", { enabled: false });
});

test("existing public article renders deterministic content", async () => {
  const page = await browser.newPage();
  const response = await page.goto(`${baseURL}/en/news/${existingArticleId}`, {
    waitUntil: "domcontentloaded",
  });
  assert.equal(response?.status(), 200);
  await page.getByRole("heading", { level: 1, name: "Deterministic AI fixture" }).waitFor();
  assert.equal(await page.getByText("Fixture Wire").count() > 0, true);
  await page.close();
});

test("missing public article returns not found", async () => {
  const page = await browser.newPage();
  const response = await page.goto(`${baseURL}/en/news/${missingArticleId}`, {
    waitUntil: "domcontentloaded",
  });
  assert.equal(response?.status(), 404);
  await page.close();
});

test("dashboard without a session returns to login", async () => {
  const page = await browser.newPage();
  await page.goto(`${baseURL}/en/ci-admin`, { waitUntil: "domcontentloaded" });
  await page.waitForURL(`${baseURL}/en/ci-admin/login`);
  await page.getByRole("heading", { name: "Restricted Access" }).waitFor();
  assert.equal(page.url(), `${baseURL}/en/ci-admin/login`);
  await page.close();
});
