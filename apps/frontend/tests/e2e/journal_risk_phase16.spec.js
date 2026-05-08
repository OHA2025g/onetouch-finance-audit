const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 16 — Journal risk workbench (PR-56)", () => {
  test("financial audit hub navigates to journal risk dashboard URL", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/financial-audit");
    await expect(page.getByTestId("module-hub-financial-audit")).toBeVisible({ timeout: 30_000 });

    const hub = page.locator('[data-testid="module-hub-financial-audit"]');
    await hub
      .getByTestId("hub-card-journal-risk-workbench")
      .or(hub.locator('a[href*="financial-audit/journal-risk-dashboard"]'))
      .first()
      .click();

    await expect(page).toHaveURL(/\/app\/financial-audit\/journal-risk-dashboard\/?(?=\?|#|$)/);
    await expect(page.getByTestId("journal-risk-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="journal-risk-page"][data-journal-risk-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("jr-kpi-rules-count")).toBeVisible();
    await expect(page.getByTestId("jr-rules-table")).toBeVisible();
    await expect(page.getByTestId("jr-journals-table")).toBeVisible();
  });

  test("direct journal-risk-dashboard loads risk ladder", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/financial-audit/journal-risk-dashboard");
    await expect(page.getByTestId("journal-risk-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="journal-risk-page"][data-journal-risk-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("jr-kpi-je-count")).toBeVisible();
  });
});
