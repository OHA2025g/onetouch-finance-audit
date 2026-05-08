const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 6 — Month-end close surface (PR-46)", () => {
  test("Finance ops hub navigates to month-end close", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/finance-operations");
    await expect(page.getByTestId("module-hub-finance-operations")).toBeVisible({ timeout: 30_000 });
    const hub = page.locator('[data-testid="module-hub-finance-operations"]');
    await hub
      .getByTestId("hub-card-month-end-close")
      .or(hub.locator('a[href*="/finance-operations/month-end-close"]'))
      .first()
      .click();
    await expect(page).toHaveURL(/\/app\/finance-operations\/month-end-close\/?/);
    await expect(page.getByTestId("month-end-close-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("masters-filter-strip")).toBeVisible();
  });

  test("direct month-end close route loads shell; open first cycle shows tasks grid", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/finance-operations/month-end-close");
    await expect(page.getByTestId("month-end-close-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("masters-filter-strip")).toBeVisible();
    await expect(page.getByTestId("close-create-cycle")).toBeVisible();

    const cycleLink = page.locator('[data-testid^="close-cycle-"]').first();
    if (await cycleLink.isVisible({ timeout: 10_000 }).catch(() => false)) {
      await cycleLink.click();
      await expect(page.getByTestId("close-tasks-table")).toBeVisible({ timeout: 30_000 });
    }
  });
});
