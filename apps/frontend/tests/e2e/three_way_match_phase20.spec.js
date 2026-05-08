const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 20 — Three-way match workbench (PR-60)", () => {
  test("continuous audit hub navigates to three-way match dashboard URL", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/continuous-audit");
    await expect(page.getByTestId("module-hub-continuous-audit")).toBeVisible({ timeout: 30_000 });

    const hub = page.locator('[data-testid="module-hub-continuous-audit"]');
    await hub
      .getByTestId("hub-card-three-way-match-workbench")
      .or(hub.locator('a[href*="continuous-audit/three-way-match-dashboard"]'))
      .first()
      .click();

    await expect(page).toHaveURL(/\/app\/continuous-audit\/three-way-match-dashboard\/?(?=\?|#|$)/);
    await expect(page.getByTestId("twm-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="twm-workbench-page"][data-three-way-match-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("twm-kpi-open-exceptions")).toBeVisible();
    await expect(page.getByTestId("twm-exceptions-table")).toBeVisible();
  });

  test("direct three-way-match-dashboard loads ladder", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/continuous-audit/three-way-match-dashboard");
    await expect(page.getByTestId("twm-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="twm-workbench-page"][data-three-way-match-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("twm-kpi-tol-pct")).toBeVisible();
  });
});
