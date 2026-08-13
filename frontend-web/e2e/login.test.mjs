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

test("login form is labeled and keyboard reachable", async () => {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const response = await page.goto(`${baseURL}/en/ci-admin/login`, { waitUntil: "domcontentloaded" });
  assert.equal(response?.status(), 200);

  const heading = page.getByRole("heading", { name: "Restricted Access" });
  const email = page.getByLabel("Corporate Email");
  const password = page.getByLabel("Password");
  const submit = page.getByRole("button", { name: "Authenticate" });

  await heading.waitFor();
  assert.equal(await email.count(), 1);
  assert.equal(await password.count(), 1);
  assert.equal(await submit.count(), 1);

  await email.focus();
  await page.keyboard.press("Tab");
  assert.equal(await password.evaluate((node) => document.activeElement === node), true);
  await page.keyboard.press("Tab");
  assert.equal(await submit.evaluate((node) => document.activeElement === node), true);

  await page.close();
});
