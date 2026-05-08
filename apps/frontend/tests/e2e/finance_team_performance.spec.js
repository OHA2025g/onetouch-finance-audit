const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 7 — Finance team performance (PR-47)", () => {
  test("finance ops hub navigates to team performance surface", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/finance-operations");
    await expect(page.getByTestId("module-hub-finance-operations")).toBeVisible({ timeout: 30_000 });

    const hub = page.locator('[data-testid="module-hub-finance-operations"]');
    await hub
      .getByTestId("hub-card-finance-team")
      .or(hub.locator('a[href*="team-performance"]'))
      .first()
      .click();

    await expect(page).toHaveURL(/\/app\/finance-operations\/team-performance/);
    await expect(page.getByTestId("finance-team-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("masters-filter-strip")).toBeVisible();
    await expect(page.getByTestId("ft-cycles")).toBeVisible();
  });

  test("direct team performance route loads BFF KPI band", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/finance-operations/team-performance");
    await expect(page.getByTestId("finance-team-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("ft-readiness")).toBeVisible();
  });
});
