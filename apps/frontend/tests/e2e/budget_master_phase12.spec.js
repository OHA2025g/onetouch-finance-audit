const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 12 — Budget master route (PR-52)", () => {
  test("finance operations hub navigates to budget master governance page", async ({ page }) => {
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
    await expect(page.getByTestId("budget-master-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="budget-master-page"][data-budget-master-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("budget-upload-count")).toBeVisible();
    await expect(page.getByTestId("budget-create")).toBeVisible();
    await expect(page.getByTestId("budget-versions-table")).toBeVisible();
  });

  test("direct /finance-operations/budget-master shows upload and governance KPIs", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/finance-operations/budget-master");
    await expect(page.getByTestId("budget-master-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("budget-approved-count")).toBeVisible();
    await expect(page.getByTestId("budget-locked-count")).toBeVisible();
    await expect(page.getByTestId("budget-upload-file")).toBeVisible();
  });
});
