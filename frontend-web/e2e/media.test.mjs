import assert from "node:assert/strict";
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

test("public logo is delivered through the image optimizer under a 10x payload budget", async () => {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(`${baseURL}/en`, { waitUntil: "networkidle" });

  const logo = page.getByRole("img", { name: "Little Mere News Logo" });
  await logo.waitFor();

  const delivery = await logo.evaluate((node) => {
    const selected = new URL(node.currentSrc);
    const timing = performance
      .getEntriesByName(node.currentSrc)
      .find((entry) => entry.entryType === "resource");

    return {
      pathname: selected.pathname,
      encodedBodySize: "encodedBodySize" in (timing ?? {}) ? timing.encodedBodySize : 0,
    };
  });

  assert.equal(delivery.pathname, "/_next/image");
  assert.equal(await logo.getAttribute("width"), "40");
  assert.equal(await logo.getAttribute("height"), "40");
  assert.ok(delivery.encodedBodySize > 0, "optimized logo resource timing is missing");
  assert.ok(
    delivery.encodedBodySize < originalLogoBytes / 10,
    `optimized logo is still too large: ${delivery.encodedBodySize} bytes`,
  );

  await page.screenshot({ path: "test-results/media-desktop.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: "test-results/media-mobile.png", fullPage: true });
  await page.close();
});
