const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 38 — Integration hub workbench (PR-78)", () => {
  test("integrations hub navigates to integration hub dashboard URL", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/integrations");
    await expect(page.getByTestId("module-hub-integrations")).toBeVisible({ timeout: 30_000 });

    const hub = page.locator('[data-testid="module-hub-integrations"]');
    await hub
      .getByTestId("hub-card-integration-hub-workbench")
      .or(hub.locator('a[href*="integrations/integration-hub-dashboard"]'))
      .first()
      .click();

    await expect(page).toHaveURL(/\/app\/integrations\/integration-hub-dashboard\/?(?=\?|#|$)/);
    await expect(page.getByTestId("integration-hub-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(
      page.locator('[data-testid="integration-hub-workbench-page"][data-integration-hub-phase38-surface="true"]')
    ).toBeVisible();
    await expect(page.getByTestId("int38-kpi-connectors")).toBeVisible();
    await expect(page.getByTestId("int38-connectors-table")).toBeVisible();
  });

  test("direct integrations/integration-hub-dashboard loads workbench", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/integrations/integration-hub-dashboard");
    await expect(page.getByTestId("integration-hub-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("int38-kpi-catalog")).toBeVisible();
    await expect(page.getByTestId("int38-sync-logs-table")).toBeVisible();
  });
});
