const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 9 — Receivables & AR ageing route (PR-49)", () => {
  test("working capital hub navigates to receivables roadmap URL", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/working-capital-command-center");
    await expect(page.getByTestId("module-hub-working-capital")).toBeVisible({ timeout: 30_000 });

    const hub = page.locator('[data-testid="module-hub-working-capital"]');
    await hub
      .getByTestId("hub-card-ar-receivables")
      .or(hub.locator('a[href*="working-capital/receivables"]'))
      .first()
      .click();

    await expect(page).toHaveURL(/\/app\/working-capital\/receivables\/?(?=\?|#|$)/);
    await expect(page.getByTestId("working-capital-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="working-capital-page"][data-ar-receivables-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("wc-ar-table")).toBeVisible();
  });

  test("direct /working-capital/receivables marks AR surface + AR ladder", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/working-capital/receivables");
    await expect(page.getByTestId("working-capital-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="working-capital-page"][data-ar-receivables-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("kpi-ar-open")).toBeVisible();
  });
});
