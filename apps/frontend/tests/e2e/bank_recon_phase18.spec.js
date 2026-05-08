const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 18 — Bank reconciliation suite (PR-58)", () => {
  test("financial audit hub navigates to bank recon dashboard URL", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/financial-audit");
    await expect(page.getByTestId("module-hub-financial-audit")).toBeVisible({ timeout: 30_000 });

    const hub = page.locator('[data-testid="module-hub-financial-audit"]');
    await hub
      .getByTestId("hub-card-bank-recon-workbench")
      .or(hub.locator('a[href*="financial-audit/bank-reconciliation-dashboard"]'))
      .first()
      .click();

    await expect(page).toHaveURL(/\/app\/financial-audit\/bank-reconciliation-dashboard\/?(?=\?|#|$)/);
    await expect(page.getByTestId("bank-recon-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="bank-recon-workbench-page"][data-bank-recon-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("br-kpi-statements")).toBeVisible();
    await expect(page.getByTestId("br-statements-table")).toBeVisible();
  });

  test("direct bank-reconciliation-dashboard loads ladder", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/financial-audit/bank-reconciliation-dashboard");
    await expect(page.getByTestId("bank-recon-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="bank-recon-workbench-page"][data-bank-recon-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("br-kpi-pending-signoff")).toBeVisible();
  });
});
