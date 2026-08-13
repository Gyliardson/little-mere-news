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
  const page = await browser.newPage();
  await page.goto(`${baseURL}/en`, { waitUntil: "domcontentloaded" });

  const logo = page.getByRole("img", { name: "Little Mere News Logo" });
  await logo.waitFor();
  const src = await logo.getAttribute("src");

  assert.ok(src?.startsWith("/_next/image?"), `unexpected logo source: ${src}`);
  assert.equal(await logo.getAttribute("width"), "40");
  assert.equal(await logo.getAttribute("height"), "40");

  const optimizedResponse = await page.request.get(new URL(src, baseURL).toString());
  assert.equal(optimizedResponse.ok(), true);
  const optimizedBytes = (await optimizedResponse.body()).length;
  assert.ok(
    optimizedBytes < originalLogoBytes / 10,
    `optimized logo is still too large: ${optimizedBytes} bytes`,
  );

  await page.close();
});
