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

async function structuralViolations(page) {
  return page.evaluate(() => ({
    imagesWithoutAlt: [...document.querySelectorAll("img")]
      .filter((node) => !node.hasAttribute("alt")).length,
    unnamedButtons: [...document.querySelectorAll("button")]
      .filter((node) => !(node.getAttribute("aria-label") || node.textContent?.trim())).length,
    unlabeledInputs: [...document.querySelectorAll("input")]
      .filter((node) => {
        const id = node.getAttribute("id");
        const aria = node.getAttribute("aria-label") || node.getAttribute("aria-labelledby");
        return !aria && (!id || !document.querySelector(`label[for="${CSS.escape(id)}"]`));
      }).length,
  }));
}

test("public error state keeps basic accessible structure", async () => {
  const page = await browser.newPage();
  const response = await page.goto(`${baseURL}/en`, { waitUntil: "domcontentloaded" });
  assert.equal(response?.status(), 200);
  await page.getByRole("alert").waitFor();
  assert.deepEqual(await structuralViolations(page), {
    imagesWithoutAlt: 0,
    unnamedButtons: 0,
    unlabeledInputs: 0,
  });
  await page.close();
});

test("admin login keeps basic accessible structure", async () => {
  const page = await browser.newPage();
  await page.goto(`${baseURL}/en/ci-admin/login`, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: "Restricted Access" }).waitFor();
  assert.deepEqual(await structuralViolations(page), {
    imagesWithoutAlt: 0,
    unnamedButtons: 0,
    unlabeledInputs: 0,
  });
  await page.close();
});
