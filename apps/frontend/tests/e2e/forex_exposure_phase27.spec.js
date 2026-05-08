const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 27 — Forex exposure workbench (PR-67)", () => {
  test("treasury command center navigates to forex exposure dashboard URL", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/treasury-command-center");
    await expect(page.getByTestId("module-hub-treasury")).toBeVisible({ timeout: 30_000 });

    const hub = page.locator('[data-testid="module-hub-treasury"]');
    await hub
      .getByTestId("hub-card-forex-exposure-workbench")
      .or(hub.locator('a[href*="treasury/forex-exposure-dashboard"]'))
      .first()
      .click();

    await expect(page).toHaveURL(/\/app\/treasury\/forex-exposure-dashboard\/?(?=\?|#|$)/);
    await expect(page.getByTestId("forex-exposure-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="forex-exposure-workbench-page"][data-forex-phase27-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("fx27-kpi-exposure-count")).toBeVisible();
    await expect(page.getByTestId("fx-exposure-table")).toBeVisible();
  });

  test("direct forex-exposure-dashboard loads ladder", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/treasury/forex-exposure-dashboard");
    await expect(page.getByTestId("forex-exposure-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="forex-exposure-workbench-page"][data-forex-phase27-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("fx27-kpi-hedge-count")).toBeVisible();
  });
});
