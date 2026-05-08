const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 32 — Access & SoD workbench (PR-72)", () => {
  test("risk intelligence command center navigates to user access & SoD dashboard URL", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/risk-intelligence-command-center");
    await expect(page.getByTestId("module-hub-risk-intelligence")).toBeVisible({ timeout: 30_000 });

    const hub = page.locator('[data-testid="module-hub-risk-intelligence"]');
    await hub
      .getByTestId("hub-card-access-sod-workbench")
      .or(hub.locator('a[href*="risk-intelligence/user-access-sod-dashboard"]'))
      .first()
      .click();

    await expect(page).toHaveURL(/\/app\/risk-intelligence\/user-access-sod-dashboard\/?(?=\?|#|$)/);
    await expect(page.getByTestId("access-sod-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="access-sod-workbench-page"][data-access-sod-phase32-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("ac32-kpi-users")).toBeVisible();
    await expect(page.getByTestId("access-sod-conflicts-table")).toBeVisible();
  });

  test("direct risk-intelligence/user-access-sod-dashboard loads ladder", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/risk-intelligence/user-access-sod-dashboard");
    await expect(page.getByTestId("access-sod-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="access-sod-workbench-page"][data-access-sod-phase32-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("ac32-kpi-sod-conflicts")).toBeVisible();
  });
});
