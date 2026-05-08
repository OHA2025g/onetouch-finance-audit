const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 8 — Working capital command center (PR-48)", () => {
  test("working capital hub navigates to AR/AP dashboard", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/working-capital-command-center");
    await expect(page.getByTestId("module-hub-working-capital")).toBeVisible({ timeout: 30_000 });

    const hub = page.locator('[data-testid="module-hub-working-capital"]');
    await hub
      .getByTestId("hub-card-wc-dashboard")
      .or(
        hub.locator(
          'a[href*="/app/working-capital"]:not([href*="cash-conversion"]):not([href*="receivables"]):not([href*="payables"])',
        ),
      )
      .first()
      .click();

    await expect(page).toHaveURL(/\/app\/working-capital\/?(?=\?|#|$)/);
    await expect(page.getByTestId("working-capital-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("masters-filter-strip")).toBeVisible();
    await expect(page.getByTestId("kpi-ar-open")).toBeVisible();
  });

  test("direct working capital dashboard route loads KPI band", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/working-capital");
    await expect(page.getByTestId("working-capital-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("wc-ar-table")).toBeVisible();
  });
});
