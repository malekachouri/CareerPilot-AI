// End-to-end smoke test against a running stack (docker compose up): register → dashboard → logout →
// protected redirect → bad login → login. Usage: BASE_URL=http://localhost:3000 node e2e/smoke.mjs
import assert from "node:assert/strict";
import { chromium } from "playwright";

const base = process.env.BASE_URL ?? "http://localhost:3000";
const email = `smoke-${Date.now()}@example.org`;
const password = "a-long-smoke-test-passphrase";

const browser = await chromium.launch();
const page = await browser.newPage();
const alert = page.locator("p[role=alert]");
try {
  await page.goto(`${base}/register`);
  await page.fill("#field-display_name", "Smoke Test");
  await page.fill("#field-email", email);
  await page.fill("#field-password", "short");
  await page.click("button[type=submit]");
  assert.match(await alert.innerText(), /12 characters/);

  await page.fill("#field-password", password);
  await page.click("button[type=submit]");
  await page.waitForURL(/\/dashboard$/);
  await page.getByText("Welcome, Smoke Test").waitFor();

  await page.getByRole("button", { name: "Log out" }).click();
  await page.waitForURL(/\/login$/);

  await page.goto(`${base}/dashboard`);
  assert.match(page.url(), /\/login\?next=%2Fdashboard$/);

  await page.fill("#field-email", email);
  await page.fill("#field-password", "wrong-password-123");
  await page.click("button[type=submit]");
  assert.equal(await alert.innerText(), "Invalid email or password");

  await page.fill("#field-password", password);
  await page.click("button[type=submit]");
  await page.waitForURL(/\/dashboard$/);

  // Tests Hub: library → test → timed attempt → autosave → submit → results with explanations.
  await page.goto(`${base}/tests`);
  await page.getByText("Linux & networking fundamentals").click();
  await page.getByRole("button", { name: "Start test" }).click();
  await page.waitForURL(/\/attempts\/[^/]+$/);
  await page.getByRole("timer").waitFor();
  await page.locator("fieldset label").first().click();
  await page.getByText("1/6 answered").waitFor();
  await page.reload(); // resume: the saved answer comes back
  await page.getByText("1/6 answered").waitFor();
  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: "Submit" }).click();
  await page.waitForURL(/\/results$/);
  await page.getByText("Review & explanations").waitFor();
  assert.ok((await page.getByText("Explanation").count()) > 0);

  await page.goto(`${base}/analytics`);
  await page.getByText("Accuracy by topic").waitFor();

  // Coach without a model (CI): a multiple-choice question is still presented and graded by its key.
  await page.goto(`${base}/coach`);
  await page.getByRole("button", { name: /^DevOps Interview Agent/ }).click();
  await page.waitForURL(/\/coach\/[^/]+$/);
  await page.getByText(/recommended \d+ min/).waitFor();
  await page.locator("fieldset label").first().click();
  await page.getByRole("button", { name: "Submit answer" }).click();
  await page.getByText(/Correct answer:/).waitFor();
  console.log("e2e smoke: OK");
} finally {
  await browser.close();
}
