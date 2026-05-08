const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 26 — Treasury debt & investments workbench (PR-66)", () => {
  test("treasury command center navigates to debt & investments dashboard URL", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/treasury-command-center");
    await expect(page.getByTestId("module-hub-treasury")).toBeVisible({ timeout: 30_000 });

    const hub = page.locator('[data-testid="module-hub-treasury"]');
    await hub
      .getByTestId("hub-card-treasury-debt-investments-workbench")
      .or(hub.locator('a[href*="treasury/debt-investments-dashboard"]'))
      .first()
      .click();

    await expect(page).toHaveURL(/\/app\/treasury\/debt-investments-dashboard\/?(?=\?|#|$)/);
    await expect(page.getByTestId("treasury-debt-inv-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(
      page.locator('[data-testid="treasury-debt-inv-workbench-page"][data-treasury-phase26-surface="true"]'),
    ).toBeVisible();
    await expect(page.getByTestId("treasury26-kpi-debt-count")).toBeVisible();
    await expect(page.getByTestId("treasury-debt-table")).toBeVisible();
  });

  test("direct debt-investments-dashboard loads ladder", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/treasury/debt-investments-dashboard");
    await expect(page.getByTestId("treasury-debt-inv-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(
      page.locator('[data-testid="treasury-debt-inv-workbench-page"][data-treasury-phase26-surface="true"]'),
    ).toBeVisible();
    await expect(page.getByTestId("treasury26-kpi-investment-count")).toBeVisible();
  });
});
