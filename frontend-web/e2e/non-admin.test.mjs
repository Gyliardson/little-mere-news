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

test("authenticated non-admin is returned to login with forbidden state", async () => {
  const context = await browser.newContext();
  const page = await context.newPage();

  await page.goto(`${baseURL}/en/ci-admin/login`, { waitUntil: "domcontentloaded" });
  await page.getByLabel("Corporate Email").fill("viewer@example.test");
  await page.getByLabel("Password").fill("viewer-password");
  await page.getByRole("button", { name: "Authenticate" }).click();

  // The protected route redirects through Next.js navigation. Assert the
  // visible denied boundary first instead of waiting for a full-page `load`,
  // then verify that the URL carries the explicit forbidden state.
  await page.getByRole("heading", { name: "Restricted Access" }).waitFor();
  await page.waitForFunction(
    (expected) => window.location.href === expected,
    `${baseURL}/en/ci-admin/login?error=forbidden`,
  );
  assert.equal(page.url(), `${baseURL}/en/ci-admin/login?error=forbidden`);

  await context.close();
});
