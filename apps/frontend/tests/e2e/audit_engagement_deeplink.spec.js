const { test, expect } = require("@playwright/test");

async function loginAsInternalAuditor(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-internal-auditor").click();
  // Any authenticated landing page is fine; role routes to /app/audit
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("CA engagement deep links", () => {
  test("opens financial tab from ?tab=financial and renders FS panel", async ({ page }) => {
    await loginAsInternalAuditor(page);

    await page.goto("/app/audit-planning/engagements/ENG-DEMO-IN-2025?tab=financial");

    // Kicker labels can collide with other copy; assert exact section kicker.
    await expect(page.getByText("TRIAL BALANCE", { exact: true })).toBeVisible();
    // The upload card title is always rendered even when no snapshot exists.
    await expect(page.getByText("Upload CSV / XLSX", { exact: true })).toBeVisible();
  });

  test("opens working papers tab from ?tab=wp", async ({ page }) => {
    await loginAsInternalAuditor(page);

    await page.goto("/app/audit-planning/engagements/ENG-DEMO-IN-2025?tab=wp");

    await expect(page.getByText("WORKING PAPERS", { exact: true })).toBeVisible();
    // Working papers tab is a summary card; module repository lives under /working-papers.
    await expect(page.getByText("Open module", { exact: true })).toBeVisible();
  });
});

