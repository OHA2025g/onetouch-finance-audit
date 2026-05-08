const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 13 — Budget vs actual route (PR-53)", () => {
  test("finance operations hub navigates to BvA dashboard URL", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/finance-operations");
    await expect(page.getByTestId("module-hub-finance-operations")).toBeVisible({ timeout: 30_000 });

    const hub = page.locator('[data-testid="module-hub-finance-operations"]');
    await hub
      .getByTestId("hub-card-budget-vs-actual")
      .or(hub.locator('a[href*="finance-operations/budget-vs-actual-dashboard"]'))
      .first()
      .click();

    await expect(page).toHaveURL(/\/app\/finance-operations\/budget-vs-actual-dashboard\/?(?=\?|#|$)/);
    await expect(page.getByTestId("fpa-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="fpa-page"][data-budget-vs-actual-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("kpi-capex-var")).toBeVisible();
    await expect(page.getByTestId("fpa-capex-table")).toBeVisible();
  });

  test("direct budget-vs-actual-dashboard marks BvA surface + FP&A ladder", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/finance-operations/budget-vs-actual-dashboard");
    await expect(page.getByTestId("fpa-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="fpa-page"][data-budget-vs-actual-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("kpi-capex-actual")).toBeVisible();
  });
});
