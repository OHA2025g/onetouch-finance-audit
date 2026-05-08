const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 21 — O2C audit workbench (PR-61)", () => {
  test("continuous audit hub navigates to O2C dashboard URL", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/continuous-audit");
    await expect(page.getByTestId("module-hub-continuous-audit")).toBeVisible({ timeout: 30_000 });

    const hub = page.locator('[data-testid="module-hub-continuous-audit"]');
    await hub
      .getByTestId("hub-card-o2c-audit-workbench")
      .or(hub.locator('a[href*="continuous-audit/o2c-audit-dashboard"]'))
      .first()
      .click();

    await expect(page).toHaveURL(/\/app\/continuous-audit\/o2c-audit-dashboard\/?(?=\?|#|$)/);
    await expect(page.getByTestId("o2c-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="o2c-workbench-page"][data-o2c-audit-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("o2c-kpi-customers")).toBeVisible();
    await expect(page.getByTestId("o2c-customers-table")).toBeVisible();
  });

  test("direct o2c-audit-dashboard loads ladder", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/continuous-audit/o2c-audit-dashboard");
    await expect(page.getByTestId("o2c-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="o2c-workbench-page"][data-o2c-audit-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("o2c-kpi-ar-open")).toBeVisible();
  });
});
