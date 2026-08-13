import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { chromium } from "playwright";

const baseURL = process.env.E2E_BASE_URL ?? "http://127.0.0.1:3000";
let browser;

before(async () => {
  browser = await chromium.launch({ headless: true });
});

after(async () => {
  await browser?.close();
});

async function signIn(page) {
  await page.goto(`${baseURL}/en/ci-admin/login`, { waitUntil: "domcontentloaded" });
  await page.getByLabel("Corporate Email").fill("admin@example.test");
  await page.getByLabel("Password").fill("admin-password");
  await page.getByRole("button", { name: "Authenticate" }).click();

  // Next.js performs a client-side router.replace after the auth cookie is
  // persisted. Synchronize on the authorized UI boundary rather than a full
  // document `load` event, which is not a stable lifecycle signal for a
  // client-side transition.
  await page.getByRole("heading", { name: "Overview" }).waitFor();
  assert.equal(page.url(), `${baseURL}/en/ci-admin`);
}

test("authorized administrator reaches the real dashboard boundary", async () => {
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await context.newPage();
  await signIn(page);

  assert.equal(await page.getByText("Total Processed (Week)").count(), 1);
  assert.equal(await page.getByText("Articles Today").count(), 1);
  assert.equal(await page.getByText("Active Sources").count(), 1);

  await context.close();
});

test("CMS news dialog has accessible semantics and keyboard close", async () => {
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await context.newPage();
  await signIn(page);
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
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await context.newPage();
  await signIn(page);
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
