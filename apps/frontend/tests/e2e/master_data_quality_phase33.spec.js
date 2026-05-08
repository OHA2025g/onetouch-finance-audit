const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 33 — Master data quality workbench (PR-73)", () => {
  test("risk intelligence command center navigates to master data quality dashboard URL", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/risk-intelligence-command-center");
    await expect(page.getByTestId("module-hub-risk-intelligence")).toBeVisible({ timeout: 30_000 });

    const hub = page.locator('[data-testid="module-hub-risk-intelligence"]');
    await hub
      .getByTestId("hub-card-master-dq-workbench")
      .or(hub.locator('a[href*="risk-intelligence/master-data-quality-dashboard"]'))
      .first()
      .click();

    await expect(page).toHaveURL(/\/app\/risk-intelligence\/master-data-quality-dashboard\/?(?=\?|#|$)/);
    await expect(page.getByTestId("master-dq-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="master-dq-workbench-page"][data-mdq-phase33-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("mdq33-kpi-open-scope")).toBeVisible();
    await expect(page.getByTestId("mdq-vendor-findings-table")).toBeVisible();
  });

  test("direct risk-intelligence/master-data-quality-dashboard loads ladder", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/risk-intelligence/master-data-quality-dashboard");
    await expect(page.getByTestId("master-dq-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="master-dq-workbench-page"][data-mdq-phase33-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("mdq33-kpi-duplicates")).toBeVisible();
  });
});
