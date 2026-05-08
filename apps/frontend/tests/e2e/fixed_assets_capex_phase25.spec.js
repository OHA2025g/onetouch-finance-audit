const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 25 — Fixed assets & CAPEX workbench (PR-65)", () => {
  test("financial audit hub navigates to fixed assets capex dashboard URL", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/financial-audit");
    await expect(page.getByTestId("module-hub-financial-audit")).toBeVisible({ timeout: 30_000 });

    const hub = page.locator('[data-testid="module-hub-financial-audit"]');
    await hub
      .getByTestId("hub-card-fixed-assets-capex-workbench")
      .or(hub.locator('a[href*="financial-audit/fixed-assets-capex-dashboard"]'))
      .first()
      .click();

    await expect(page).toHaveURL(/\/app\/financial-audit\/fixed-assets-capex-dashboard\/?(?=\?|#|$)/);
    await expect(page.getByTestId("fa-capex-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(
      page.locator('[data-testid="fa-capex-workbench-page"][data-fa-capex-workbench-surface="true"]'),
    ).toBeVisible();
    await expect(page.getByTestId("fa-kpi-asset-count")).toBeVisible();
    await expect(page.getByTestId("fa-assets-table")).toBeVisible();
  });

  test("direct fixed-assets-capex-dashboard loads ladder", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/financial-audit/fixed-assets-capex-dashboard");
    await expect(page.getByTestId("fa-capex-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(
      page.locator('[data-testid="fa-capex-workbench-page"][data-fa-capex-workbench-surface="true"]'),
    ).toBeVisible();
    await expect(page.getByTestId("fa-kpi-capex-over-budget")).toBeVisible();
  });
});
