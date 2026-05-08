const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 17 — Reconciliations suite (PR-57)", () => {
  test("financial audit hub navigates to reconciliations dashboard URL", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/financial-audit");
    await expect(page.getByTestId("module-hub-financial-audit")).toBeVisible({ timeout: 30_000 });

    const hub = page.locator('[data-testid="module-hub-financial-audit"]');
    await hub
      .getByTestId("hub-card-reconciliations-workbench")
      .or(hub.locator('a[href*="financial-audit/reconciliations-dashboard"]'))
      .first()
      .click();

    await expect(page).toHaveURL(/\/app\/financial-audit\/reconciliations-dashboard\/?(?=\?|#|$)/);
    await expect(page.getByTestId("recon-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="recon-workbench-page"][data-reconciliation-suite-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("recon-kpi-total")).toBeVisible();
    await expect(page.getByTestId("recon-list-table")).toBeVisible();
  });

  test("direct reconciliations-dashboard loads suite ladder", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/financial-audit/reconciliations-dashboard");
    await expect(page.getByTestId("recon-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="recon-workbench-page"][data-reconciliation-suite-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("recon-kpi-open")).toBeVisible();
  });
});
