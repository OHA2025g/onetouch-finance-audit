const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 29 — Legal notices & litigation workbench (PR-69)", () => {
  test("compliance command center navigates to legal dashboard URL", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/compliance-command-center");
    await expect(page.getByTestId("module-hub-compliance")).toBeVisible({ timeout: 30_000 });

    const hub = page.locator('[data-testid="module-hub-compliance"]');
    await hub
      .getByTestId("hub-card-legal-workbench")
      .or(hub.locator('a[href*="compliance/legal-dashboard"]'))
      .first()
      .click();

    await expect(page).toHaveURL(/\/app\/compliance\/legal-dashboard\/?(?=\?|#|$)/);
    await expect(page.getByTestId("legal-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="legal-workbench-page"][data-legal-phase29-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("legal29-kpi-notice-count")).toBeVisible();
    await expect(page.getByTestId("legal-notices-table")).toBeVisible();
  });

  test("direct compliance/legal-dashboard loads ladder", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/compliance/legal-dashboard");
    await expect(page.getByTestId("legal-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="legal-workbench-page"][data-legal-phase29-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("legal29-kpi-litigation-count")).toBeVisible();
  });
});
