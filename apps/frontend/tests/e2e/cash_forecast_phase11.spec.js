const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 11 — Cash forecast route (PR-51)", () => {
  test("treasury hub navigates to cash forecast roadmap URL", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/treasury-command-center");
    await expect(page.getByTestId("module-hub-treasury")).toBeVisible({ timeout: 30_000 });

    const hub = page.locator('[data-testid="module-hub-treasury"]');
    await hub
      .getByTestId("hub-card-cash-forecast")
      .or(hub.locator('a[href*="treasury/cash-forecast"]'))
      .first()
      .click();

    await expect(page).toHaveURL(/\/app\/treasury\/cash-forecast\/?(?=\?|#|$)/);
    await expect(page.getByTestId("treasury-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="treasury-page"][data-cash-forecast-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("treasury-accounts")).toBeVisible();
    await expect(page.getByTestId("kpi-bt-count")).toBeVisible();
  });

  test("direct /treasury/cash-forecast marks forecast surface + treasury ladder", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/treasury/cash-forecast");
    await expect(page.getByTestId("treasury-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="treasury-page"][data-cash-forecast-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("treasury-txns")).toBeVisible();
  });
});
