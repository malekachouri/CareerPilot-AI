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
  console.log("e2e smoke: OK");
} finally {
  await browser.close();
}
