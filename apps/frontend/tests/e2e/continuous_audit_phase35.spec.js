const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 35 — Continuous audit rules workbench (PR-75)", () => {
  test("continuous audit hub navigates to rules engine dashboard URL", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/continuous-audit");
    await expect(page.getByTestId("module-hub-continuous-audit")).toBeVisible({ timeout: 30_000 });

    const hub = page.locator('[data-testid="module-hub-continuous-audit"]');
    await hub
      .getByTestId("hub-card-continuous-audit-rules-workbench")
      .or(hub.locator('a[href*="continuous-audit/rules-engine-dashboard"]'))
      .first()
      .click();

    await expect(page).toHaveURL(/\/app\/continuous-audit\/rules-engine-dashboard\/?(?=\?|#|$)/);
    await expect(page.getByTestId("continuous-audit-rules-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="continuous-audit-rules-workbench-page"][data-ca-rules-phase35-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("ca35-kpi-active-rules")).toBeVisible();
    await expect(page.getByTestId("ca35-exceptions-table")).toBeVisible();
  });

  test("direct continuous-audit/rules-engine-dashboard loads ladder", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/continuous-audit/rules-engine-dashboard");
    await expect(page.getByTestId("continuous-audit-rules-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="continuous-audit-rules-workbench-page"][data-ca-rules-phase35-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("ca35-kpi-ca-exceptions")).toBeVisible();
  });
});
