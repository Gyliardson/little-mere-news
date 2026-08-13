import assert from "node:assert/strict";
import { stat } from "node:fs/promises";
import { after, before, test } from "node:test";
import { chromium } from "playwright";

const baseURL = process.env.E2E_BASE_URL ?? "http://127.0.0.1:3000";
const originalLogoBytes = 5295274;
let browser;

before(async () => {
  browser = await chromium.launch({ headless: true });
});

after(async () => {
  await browser?.close();
});

test("public logo uses optimized delivery within its source budget and rendered size", async () => {
  const logoFile = await stat(new URL("../public/logo.png", import.meta.url));
  assert.ok(logoFile.size < originalLogoBytes / 10);

  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(`${baseURL}/en`, { waitUntil: "networkidle" });
  const logo = page.getByRole("img", { name: "Little Mere News Logo" });
  await logo.waitFor();

  const src = await logo.getAttribute("src");
  assert.ok(src?.startsWith("/_next/image?"));

  const box = await logo.boundingBox();
  assert.ok(box);
  assert.equal(Math.round(box.width), 40);
  assert.equal(Math.round(box.height), 40);

  await page.close();
});
