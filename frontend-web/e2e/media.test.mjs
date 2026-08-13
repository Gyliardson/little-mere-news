import assert from "node:assert/strict";
import { stat } from "node:fs/promises";
import { after, before, test } from "node:test";
import { chromium } from "playwright";

const baseURL = process.env.E2E_BASE_URL ?? "http://127.0.0.1:3000";
const originalLogoBytes = 5_295_274;
let browser;

before(async () => {
  browser = await chromium.launch({ headless: true });
});

after(async () => {
  await browser?.close();
});

test("public logo stays under a 10x source payload budget without layout drift", async () => {
  const logoFile = await stat(new URL("../public/logo.png", import.meta.url));
  assert.ok(
    logoFile.size < originalLogoBytes / 10,
    `logo source is still too large: ${logoFile.size} bytes`,
  );

  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(`${baseURL}/en`, { waitUntil: "networkidle" });

  const logo = page.getByRole("img", { name: "Little Mere News Logo" });
  await logo.waitFor();
  assert.equal(await logo.getAttribute("width"), "40");
  assert.equal(await logo.getAttribute("height"), "40");

  const box = await logo.boundingBox();
  assert.ok(box, "logo is not visible");
  assert.equal(Math.round(box.width), 40);
  assert.equal(Math.round(box.height), 40);

  await page.screenshot({ path: "test-results/media-desktop.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: "test-results/media-mobile.png", fullPage: true });
  await page.close();
});
