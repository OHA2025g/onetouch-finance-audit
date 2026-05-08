const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 28 — Related party transactions workbench (PR-68)", () => {
  test("compliance command center navigates to RPT dashboard URL", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/compliance-command-center");
    await expect(page.getByTestId("module-hub-compliance")).toBeVisible({ timeout: 30_000 });

    const hub = page.locator('[data-testid="module-hub-compliance"]');
    await hub
      .getByTestId("hub-card-rpt-workbench")
      .or(hub.locator('a[href*="compliance/rpt-dashboard"]'))
      .first()
      .click();

    await expect(page).toHaveURL(/\/app\/compliance\/rpt-dashboard\/?(?=\?|#|$)/);
    await expect(page.getByTestId("rpt-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="rpt-workbench-page"][data-rpt-phase28-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("rpt28-kpi-parties")).toBeVisible();
    await expect(page.getByTestId("rpt-transactions-table")).toBeVisible();
  });

  test("direct compliance/rpt-dashboard loads ladder", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/compliance/rpt-dashboard");
    await expect(page.getByTestId("rpt-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="rpt-workbench-page"][data-rpt-phase28-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("rpt28-kpi-pending")).toBeVisible();
  });
});
