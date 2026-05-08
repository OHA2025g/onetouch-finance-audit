const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 5 — CFO Action Queue (PR-45)", () => {
  test("hub card opens dedicated queue route", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/cfo-command-center");
    await expect(page.getByTestId("module-hub-cfo-command-center")).toBeVisible({ timeout: 30_000 });
    await page.getByTestId("hub-card-cfo-action-queue").click();
    await expect(page).toHaveURL(/\/app\/cfo-action-queue/);
    await expect(page.getByTestId("cfo-action-queue-page")).toBeVisible();
  });

  test("direct queue route loads and back reaches CFO cockpit", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/cfo-action-queue");
    await expect(page.getByTestId("cfo-action-queue-page")).toBeVisible({ timeout: 30_000 });

    await page.getByTestId("cfo-action-queue-refresh").click();
    await expect(page.getByTestId("cfo-action-queue-list-loading")).toBeHidden({ timeout: 60_000 });

    const row = page.locator('[data-testid^="cfo-aq-row-"]').first();
    if (await row.isVisible({ timeout: 10_000 }).catch(() => false)) {
      await row.click();
      await expect(page.getByTestId("cfo-aq-approve")).toBeVisible();
    }

    await page.getByTestId("cfo-action-queue-back-cfo").click();
    await expect(page.getByTestId("cfo-cockpit")).toBeVisible({ timeout: 30_000 });
  });
});
