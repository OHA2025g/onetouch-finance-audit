const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 22 — Credit notes workbench (PR-62)", () => {
  test("continuous audit hub navigates to credit notes dashboard URL", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/continuous-audit");
    await expect(page.getByTestId("module-hub-continuous-audit")).toBeVisible({ timeout: 30_000 });

    const hub = page.locator('[data-testid="module-hub-continuous-audit"]');
    await hub
      .getByTestId("hub-card-credit-notes-workbench")
      .or(hub.locator('a[href*="continuous-audit/credit-notes-dashboard"]'))
      .first()
      .click();

    await expect(page).toHaveURL(/\/app\/continuous-audit\/credit-notes-dashboard\/?(?=\?|#|$)/);
    await expect(page.getByTestId("credit-notes-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(
      page.locator('[data-testid="credit-notes-workbench-page"][data-credit-notes-workbench-surface="true"]'),
    ).toBeVisible();
    await expect(page.getByTestId("credit-notes-kpi-count")).toBeVisible();
    await expect(page.getByTestId("credit-notes-table")).toBeVisible();
  });

  test("direct credit-notes-dashboard loads ladder", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/continuous-audit/credit-notes-dashboard");
    await expect(page.getByTestId("credit-notes-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(
      page.locator('[data-testid="credit-notes-workbench-page"][data-credit-notes-workbench-surface="true"]'),
    ).toBeVisible();
    await expect(page.getByTestId("credit-notes-kpi-total-amount")).toBeVisible();
  });
});
