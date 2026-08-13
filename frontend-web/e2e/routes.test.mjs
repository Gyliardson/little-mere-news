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

test("unsupported locale returns not found", async () => {
  const page = await browser.newPage();
  const response = await page.goto(`${baseURL}/fr`, { waitUntil: "domcontentloaded" });
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
