const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 14 — Forecast accuracy route (PR-54)", () => {
  test("finance operations hub navigates to forecast accuracy dashboard URL", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/finance-operations");
    await expect(page.getByTestId("module-hub-finance-operations")).toBeVisible({ timeout: 30_000 });

    const hub = page.locator('[data-testid="module-hub-finance-operations"]');
    await hub
      .getByTestId("hub-card-forecast-accuracy")
      .or(hub.locator('a[href*="finance-operations/forecast-accuracy-dashboard"]'))
      .first()
      .click();

    await expect(page).toHaveURL(/\/app\/finance-operations\/forecast-accuracy-dashboard\/?(?=\?|#|$)/);
    await expect(page.getByTestId("fpa-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="fpa-page"][data-forecast-accuracy-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("kpi-je-total")).toBeVisible();
    await expect(page.getByTestId("fpa-je-table")).toBeVisible();
  });

  test("direct forecast-accuracy-dashboard marks forecast surface + FP&A ladder", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/finance-operations/forecast-accuracy-dashboard");
    await expect(page.getByTestId("fpa-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="fpa-page"][data-forecast-accuracy-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("kpi-manual-je")).toBeVisible();
  });
});
