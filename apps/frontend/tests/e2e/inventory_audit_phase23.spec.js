const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 23 — Inventory audit workbench (PR-63)", () => {
  test("financial audit hub navigates to inventory audit dashboard URL", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/financial-audit");
    await expect(page.getByTestId("module-hub-financial-audit")).toBeVisible({ timeout: 30_000 });

    const hub = page.locator('[data-testid="module-hub-financial-audit"]');
    await hub
      .getByTestId("hub-card-inventory-audit-workbench")
      .or(hub.locator('a[href*="financial-audit/inventory-audit-dashboard"]'))
      .first()
      .click();

    await expect(page).toHaveURL(/\/app\/financial-audit\/inventory-audit-dashboard\/?(?=\?|#|$)/);
    await expect(page.getByTestId("inventory-audit-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(
      page.locator('[data-testid="inventory-audit-workbench-page"][data-inventory-audit-workbench-surface="true"]'),
    ).toBeVisible();
    await expect(page.getByTestId("inventory-kpi-item-count")).toBeVisible();
    await expect(page.getByTestId("inventory-valuation-exceptions-table")).toBeVisible();
  });

  test("direct inventory-audit-dashboard loads ladder", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/financial-audit/inventory-audit-dashboard");
    await expect(page.getByTestId("inventory-audit-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(
      page.locator('[data-testid="inventory-audit-workbench-page"][data-inventory-audit-workbench-surface="true"]'),
    ).toBeVisible();
    await expect(page.getByTestId("inventory-kpi-value")).toBeVisible();
  });
});
