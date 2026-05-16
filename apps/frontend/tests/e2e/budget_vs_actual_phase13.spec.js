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
    await expect(page.getByTestId("budget-vs-actual-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="budget-vs-actual-page"][data-budget-vs-actual-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("bva-capex-variance")).toBeVisible();
    await expect(page.getByTestId("bva-variance-summary")).toBeVisible();
  });

  test("direct budget-vs-actual-dashboard shows variance workflow cards", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/finance-operations/budget-vs-actual-dashboard");
    await expect(page.getByTestId("budget-vs-actual-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("bva-capex-actual")).toBeVisible();
    await expect(page.getByTestId("bva-variance-table")).toBeVisible();
  });
});
