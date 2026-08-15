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
  return page.evaluate(() => {
    const ids = [...document.querySelectorAll("[id]")].map((node) => node.id).filter(Boolean);
    const duplicateIds = ids.filter((id, index) => ids.indexOf(id) !== index);
    const headings = [...document.querySelectorAll("h1,h2,h3,h4,h5,h6")];
    let skippedHeadingLevels = 0;
    let previousLevel = 0;
    for (const heading of headings) {
      const level = Number(heading.tagName.slice(1));
      if (previousLevel > 0 && level > previousLevel + 1) skippedHeadingLevels += 1;
      previousLevel = level;
    }

    const hasName = (node) =>
      Boolean(
        node.getAttribute("aria-label") ||
          node.getAttribute("aria-labelledby") ||
          node.textContent?.trim(),
      );

    const formControls = [
      ...document.querySelectorAll("input:not([type='hidden']), textarea, select"),
    ];

    return {
      missingDocumentLang: document.documentElement.lang.trim() ? 0 : 1,
      mainLandmarkCount: document.querySelectorAll("main").length,
      imagesWithoutAlt: [...document.querySelectorAll("img")].filter(
        (node) => !node.hasAttribute("alt"),
      ).length,
      unnamedButtons: [...document.querySelectorAll("button")].filter((node) => !hasName(node))
        .length,
      unnamedLinks: [...document.querySelectorAll("a[href]")].filter((node) => !hasName(node)).length,
      unlabeledControls: formControls.filter((node) => {
        const id = node.getAttribute("id");
        const aria = node.getAttribute("aria-label") || node.getAttribute("aria-labelledby");
        return !aria && (!id || !document.querySelector(`label[for="${CSS.escape(id)}"]`));
      }).length,
      duplicateIds: new Set(duplicateIds).size,
      emptyHeadings: headings.filter((node) => !node.textContent?.trim()).length,
      skippedHeadingLevels,
      positiveTabIndex: [...document.querySelectorAll("[tabindex]")].filter(
        (node) => Number(node.getAttribute("tabindex")) > 0,
      ).length,
    };
  });
}

async function assertRepresentativeStructure(page) {
  const result = await structuralViolations(page);
  assert.equal(result.missingDocumentLang, 0);
  assert.equal(result.mainLandmarkCount, 1);
  assert.equal(result.imagesWithoutAlt, 0);
  assert.equal(result.unnamedButtons, 0);
  assert.equal(result.unnamedLinks, 0);
  assert.equal(result.unlabeledControls, 0);
  assert.equal(result.duplicateIds, 0);
  assert.equal(result.emptyHeadings, 0);
  assert.equal(result.skippedHeadingLevels, 0);
  assert.equal(result.positiveTabIndex, 0);
}

test("public feed keeps representative accessible structure and keyboard reachability", async () => {
  const page = await browser.newPage();
  const response = await page.goto(`${baseURL}/en`, { waitUntil: "domcontentloaded" });
  assert.equal(response?.status(), 200);
  await page.getByRole("heading", { name: "Latest News" }).waitFor();
  const articleLink = page.getByRole("link", {
    name: "Read more about Deterministic AI fixture",
  });
  await articleLink.waitFor();
  await assertRepresentativeStructure(page);

  let reachedArticleLink = false;
  for (let index = 0; index < 30; index += 1) {
    await page.keyboard.press("Tab");
    if (await articleLink.evaluate((node) => document.activeElement === node)) {
      reachedArticleLink = true;
      break;
    }
  }
  assert.equal(reachedArticleLink, true, "primary article action must be keyboard reachable");
  await page.close();
});

test("article detail keeps representative accessible structure", async () => {
  const page = await browser.newPage();
  await page.goto(`${baseURL}/en/news/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa`, {
    waitUntil: "domcontentloaded",
  });
  await page.getByRole("heading", { level: 1, name: "Deterministic AI fixture" }).waitFor();
  await assertRepresentativeStructure(page);
  await page.close();
});

test("admin login keeps representative accessible structure and keyboard-reachable form", async () => {
  const page = await browser.newPage();
  await page.goto(`${baseURL}/en/ci-admin/login`, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: "Restricted Access" }).waitFor();
  await assertRepresentativeStructure(page);

  const email = page.getByLabel("Corporate Email");
  const password = page.getByLabel("Password");
  const submit = page.getByRole("button", { name: "Authenticate" });
  const reached = new Set();
  for (let index = 0; index < 20; index += 1) {
    await page.keyboard.press("Tab");
    if (await email.evaluate((node) => document.activeElement === node)) reached.add("email");
    if (await password.evaluate((node) => document.activeElement === node)) reached.add("password");
    if (await submit.evaluate((node) => document.activeElement === node)) reached.add("submit");
  }
  assert.deepEqual([...reached].sort(), ["email", "password", "submit"]);
  await page.close();
});
