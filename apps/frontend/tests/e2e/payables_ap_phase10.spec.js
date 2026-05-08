const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 10 — Payables & AP ageing route (PR-50)", () => {
  test("working capital hub navigates to payables roadmap URL", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/working-capital-command-center");
    await expect(page.getByTestId("module-hub-working-capital")).toBeVisible({ timeout: 30_000 });

    const hub = page.locator('[data-testid="module-hub-working-capital"]');
    await hub
      .getByTestId("hub-card-ap-payables")
      .or(hub.locator('a[href*="working-capital/payables"]'))
      .first()
      .click();

    await expect(page).toHaveURL(/\/app\/working-capital\/payables\/?(?=\?|#|$)/);
    await expect(page.getByTestId("working-capital-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="working-capital-page"][data-ap-payables-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("wc-ap-table")).toBeVisible();
    await expect(page.getByTestId("kpi-ap-open")).toBeVisible();
  });

  test("direct /working-capital/payables marks AP surface + AP ladder", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/working-capital/payables");
    await expect(page.getByTestId("working-capital-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="working-capital-page"][data-ap-payables-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("wc-ap-table")).toBeVisible();
    await expect(page.getByTestId("kpi-ap-open")).toBeVisible();
  });
});
