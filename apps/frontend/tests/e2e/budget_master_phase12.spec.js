const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 12 — Budget master route (PR-52)", () => {
  test("finance operations hub navigates to budget master roadmap URL", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/finance-operations");
    await expect(page.getByTestId("module-hub-finance-operations")).toBeVisible({ timeout: 30_000 });

    const hub = page.locator('[data-testid="module-hub-finance-operations"]');
    await hub
      .getByTestId("hub-card-budget-master")
      .or(hub.locator('a[href*="finance-operations/budget-master"]'))
      .first()
      .click();

    await expect(page).toHaveURL(/\/app\/finance-operations\/budget-master\/?(?=\?|#|$)/);
    await expect(page.getByTestId("fpa-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="fpa-page"][data-budget-master-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("kpi-capex-budget")).toBeVisible();
    await expect(page.getByTestId("fpa-capex-table")).toBeVisible();
  });

  test("direct /finance-operations/budget-master marks budget surface + FP&A ladder", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/finance-operations/budget-master");
    await expect(page.getByTestId("fpa-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="fpa-page"][data-budget-master-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("fpa-je-table")).toBeVisible();
  });
});
