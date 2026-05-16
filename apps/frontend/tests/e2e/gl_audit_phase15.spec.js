const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 15 — GL audit workbench (PR-55)", () => {
  test("financial audit hub navigates to GL audit dashboard URL", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/financial-audit");
    await expect(page.getByTestId("module-hub-financial-audit")).toBeVisible({ timeout: 30_000 });

    const hub = page.locator('[data-testid="module-hub-financial-audit"]');
    await hub
      .getByTestId("hub-card-gl-audit-workbench")
      .or(hub.locator('a[href*="financial-audit/gl-audit-dashboard"]'))
      .first()
      .click();

    await expect(page).toHaveURL(/\/app\/financial-audit\/gl-audit-dashboard\/?(?=\?|#|$)/);
    await expect(page.getByTestId("gl-audit-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="gl-audit-page"][data-gl-audit-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("gl-kpi-txn-count")).toBeVisible();
    await expect(page.getByTestId("gl-accounts-table")).toBeVisible();
    await expect(page.getByTestId("gl-movement-section")).toBeVisible();
    await expect(page.getByTestId("gl-anomalies-section")).toBeVisible();
  });

  test("direct gl-audit-dashboard loads GL ladder", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/financial-audit/gl-audit-dashboard");
    await expect(page.getByTestId("gl-audit-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="gl-audit-page"][data-gl-audit-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("gl-kpi-total-amount")).toBeVisible();
    await expect(page.getByTestId("gl-movement-section")).toBeVisible();
    await expect(page.getByTestId("gl-anomalies-section")).toBeVisible();
  });
});
