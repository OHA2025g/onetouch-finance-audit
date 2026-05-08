const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 24 — Physical verification workbench (PR-64)", () => {
  test("financial audit hub navigates to physical verification dashboard URL", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/financial-audit");
    await expect(page.getByTestId("module-hub-financial-audit")).toBeVisible({ timeout: 30_000 });

    const hub = page.locator('[data-testid="module-hub-financial-audit"]');
    await hub
      .getByTestId("hub-card-physical-verification-workbench")
      .or(hub.locator('a[href*="financial-audit/physical-verification-dashboard"]'))
      .first()
      .click();

    await expect(page).toHaveURL(/\/app\/financial-audit\/physical-verification-dashboard\/?(?=\?|#|$)/);
    await expect(page.getByTestId("pv-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="pv-workbench-page"][data-pv-workbench-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("pv-kpi-cycle-count")).toBeVisible();
    await expect(page.getByTestId("pv-cycles-table")).toBeVisible();
  });

  test("direct physical-verification-dashboard loads ladder", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/financial-audit/physical-verification-dashboard");
    await expect(page.getByTestId("pv-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="pv-workbench-page"][data-pv-workbench-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("pv-kpi-open-cycles")).toBeVisible();
  });
});
