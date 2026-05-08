const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 39 — Board report automation workbench (PR-79)", () => {
  test("board reporting hub navigates to report automation dashboard URL", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/board-reporting");
    await expect(page.getByTestId("module-hub-board-reporting")).toBeVisible({ timeout: 30_000 });

    const hub = page.locator('[data-testid="module-hub-board-reporting"]');
    await hub
      .getByTestId("hub-card-board-reporting-workbench")
      .or(hub.locator('a[href*="board-reporting/report-automation-dashboard"]'))
      .first()
      .click();

    await expect(page).toHaveURL(/\/app\/board-reporting\/report-automation-dashboard\/?(?=\?|#|$)/);
    await expect(page.getByTestId("board-reporting-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(
      page.locator('[data-testid="board-reporting-workbench-page"][data-board-reporting-phase39-surface="true"]')
    ).toBeVisible();
    await expect(page.getByTestId("br39-kpi-templates")).toBeVisible();
    await expect(page.getByTestId("br39-templates-table")).toBeVisible();
  });

  test("direct board-reporting/report-automation-dashboard loads workbench", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/board-reporting/report-automation-dashboard");
    await expect(page.getByTestId("board-reporting-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("br39-kpi-export-formats")).toBeVisible();
    await expect(page.getByTestId("br39-versions-table")).toBeVisible();
  });
});
