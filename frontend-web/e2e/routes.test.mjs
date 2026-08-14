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

async function openAuthorizedNewsManager(page) {
  await page.goto(`${baseURL}/en/ci-admin/login`, { waitUntil: "domcontentloaded" });
  await page.getByLabel("Corporate Email").fill("admin@example.test");
  await page.getByLabel("Password").fill("admin-password");
  await page.getByRole("button", { name: "Authenticate" }).click();
  await page.getByRole("heading", { name: "Overview" }).waitFor();
  await page.goto(`${baseURL}/en/ci-admin/news`, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: "News Manager" }).waitFor();
}

async function invalidatePublicIsrThroughRealMutation(page) {
  await page.getByRole("button", { name: /Edit: Deterministic AI fixture/ }).click();
  const dialog = page.getByRole("dialog", { name: "Edit News" });
  const title = dialog.getByLabel("Title (EN)");
  const original = await title.inputValue();
  await title.fill(`${original} revalidate`);
  await dialog.getByRole("button", { name: "Save Changes" }).click();
  await page.getByRole("status").filter({ hasText: "News updated successfully." }).waitFor();
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

test("effective public layout renders the optimized logo without desktop or mobile overflow", async () => {
  for (const viewport of [
    { width: 1440, height: 900 },
    { width: 390, height: 844 },
  ]) {
    const context = await browser.newContext({ viewport });
    const page = await context.newPage();
    const response = await page.goto(`${baseURL}/en/news/${existingArticleId}`, {
      waitUntil: "domcontentloaded",
    });
    assert.equal(response?.status(), 200);

    const logo = page.locator('header img[alt="Little Mere News Logo"]');
    await logo.waitFor();
    assert.equal(await logo.count(), 1);
    const source = await logo.getAttribute("src");
    assert.match(source ?? "", /^\/_next\/image\?url=%2Flogo\.png(?:&|$)/);
    assert.equal(await logo.getAttribute("width"), "40");
    assert.equal(await logo.getAttribute("height"), "40");

    const box = await logo.boundingBox();
    assert.equal(Math.round(box?.width ?? 0), 40);
    assert.equal(Math.round(box?.height ?? 0), 40);
    const layout = await page.evaluate(() => ({
      viewportWidth: window.innerWidth,
      scrollWidth: document.documentElement.scrollWidth,
    }));
    assert.equal(layout.scrollWidth <= layout.viewportWidth, true);

    await context.close();
  }
});

test("missing public article returns not found", async () => {
  const page = await browser.newPage();
  const response = await page.goto(`${baseURL}/en/news/${missingArticleId}`, {
    waitUntil: "domcontentloaded",
  });
  assert.equal(response?.status(), 404);
  await page.close();
});

test("existing article provider failure renders unavailable state instead of not found", async () => {
  await fixturePost("/__test__/reset");
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await context.newPage();

  try {
    await openAuthorizedNewsManager(page);
    await fixturePost("/__test__/news-error", { enabled: true });
    await invalidatePublicIsrThroughRealMutation(page);

    const response = await page.goto(`${baseURL}/en/news/${existingArticleId}`, {
      waitUntil: "domcontentloaded",
    });
    assert.notEqual(response?.status(), 404);

    const alert = page.getByRole("alert").filter({ hasText: "Article temporarily unavailable" });
    await alert.waitFor();
    const text = (await alert.textContent()) ?? "";
    assert.match(text, /Article temporarily unavailable/);
    assert.match(text, /does not mean it was removed/i);
    assert.doesNotMatch(text, /E2E_PROVIDER_FAILURE|synthetic provider failure/i);
  } finally {
    await fixturePost("/__test__/news-error", { enabled: false });
    await context.close();
  }
});

test("public feed renders a user-safe provider failure after real ISR invalidation", async () => {
  await fixturePost("/__test__/reset");
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await context.newPage();

  try {
    await openAuthorizedNewsManager(page);
    await fixturePost("/__test__/news-error", { enabled: true });
    await invalidatePublicIsrThroughRealMutation(page);

    const response = await page.goto(`${baseURL}/en`, { waitUntil: "domcontentloaded" });
    assert.equal(response?.status(), 200);
    const alert = page.getByRole("alert").filter({ hasText: "News could not be loaded" });
    await alert.waitFor();
    const text = (await alert.textContent()) ?? "";
    assert.match(text, /News could not be loaded/);
    assert.doesNotMatch(text, /E2E_PROVIDER_FAILURE|synthetic provider failure/i);
  } finally {
    await fixturePost("/__test__/news-error", { enabled: false });
    await context.close();
  }
});

test("dashboard without a session returns to login", async () => {
  const page = await browser.newPage();
  await page.goto(`${baseURL}/en/ci-admin`, { waitUntil: "domcontentloaded" });
  await page.waitForURL(`${baseURL}/en/ci-admin/login`);
  await page.getByRole("heading", { name: "Restricted Access" }).waitFor();
  assert.equal(page.url(), `${baseURL}/en/ci-admin/login`);
  await page.close();
});
