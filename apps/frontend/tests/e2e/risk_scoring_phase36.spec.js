const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 36 — Risk scoring workbench (PR-76)", () => {
  test("risk intelligence command center navigates to risk scoring dashboard URL", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/risk-intelligence-command-center");
    await expect(page.getByTestId("module-hub-risk-intelligence")).toBeVisible({ timeout: 30_000 });

    const hub = page.locator('[data-testid="module-hub-risk-intelligence"]');
    await hub
      .getByTestId("hub-card-risk-scoring-workbench")
      .or(hub.locator('a[href*="risk-intelligence/risk-scoring-dashboard"]'))
      .first()
      .click();

    await expect(page).toHaveURL(/\/app\/risk-intelligence\/risk-scoring-dashboard\/?(?=\?|#|$)/);
    await expect(page.getByTestId("risk-scoring-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="risk-scoring-workbench-page"][data-risk-scoring-phase36-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("ri36-kpi-band-high")).toBeVisible();
    await expect(page.getByTestId("ri36-scores-table")).toBeVisible();
  });

  test("direct risk-intelligence/risk-scoring-dashboard loads ladder", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/risk-intelligence/risk-scoring-dashboard");
    await expect(page.getByTestId("risk-scoring-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="risk-scoring-workbench-page"][data-risk-scoring-phase36-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("ri36-heatmap-table")).toBeVisible();
  });
});
