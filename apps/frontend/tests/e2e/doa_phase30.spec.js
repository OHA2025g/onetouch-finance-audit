const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 30 — Delegation of authority workbench (PR-70)", () => {
  test("risk intelligence command center navigates to DOA dashboard URL", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/risk-intelligence-command-center");
    await expect(page.getByTestId("module-hub-risk-intelligence")).toBeVisible({ timeout: 30_000 });

    const hub = page.locator('[data-testid="module-hub-risk-intelligence"]');
    await hub
      .getByTestId("hub-card-doa-workbench")
      .or(hub.locator('a[href*="risk-intelligence/doa-dashboard"]'))
      .first()
      .click();

    await expect(page).toHaveURL(/\/app\/risk-intelligence\/doa-dashboard\/?(?=\?|#|$)/);
    await expect(page.getByTestId("doa-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="doa-workbench-page"][data-doa-phase30-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("doa30-kpi-matrix-rows")).toBeVisible();
    await expect(page.getByTestId("doa-breaches-table")).toBeVisible();
  });

  test("direct risk-intelligence/doa-dashboard loads ladder", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/risk-intelligence/doa-dashboard");
    await expect(page.getByTestId("doa-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="doa-workbench-page"][data-doa-phase30-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("doa30-kpi-rules")).toBeVisible();
  });
});
