const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 19 — Vendor risk workbench (PR-59)", () => {
  test("continuous audit hub navigates to vendor risk dashboard URL", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/continuous-audit");
    await expect(page.getByTestId("module-hub-continuous-audit")).toBeVisible({ timeout: 30_000 });

    const hub = page.locator('[data-testid="module-hub-continuous-audit"]');
    await hub
      .getByTestId("hub-card-vendor-risk-workbench")
      .or(hub.locator('a[href*="continuous-audit/vendor-risk-dashboard"]'))
      .first()
      .click();

    await expect(page).toHaveURL(/\/app\/continuous-audit\/vendor-risk-dashboard\/?(?=\?|#|$)/);
    await expect(page.getByTestId("vr-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="vr-workbench-page"][data-vendor-risk-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("vr-kpi-vendor-count")).toBeVisible();
    await expect(page.getByTestId("vr-vendors-table")).toBeVisible();
  });

  test("direct vendor-risk-dashboard loads ladder", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/continuous-audit/vendor-risk-dashboard");
    await expect(page.getByTestId("vr-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="vr-workbench-page"][data-vendor-risk-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("vr-kpi-dup-signals")).toBeVisible();
  });
});
