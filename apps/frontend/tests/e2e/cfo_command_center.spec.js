const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 4 — CFO Command Center cockpit shell (PR-44)", () => {
  test("cockpit shows masters strip, exports, snapshot → full queue → back", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/cfo");
    await expect(page.getByTestId("cfo-cockpit")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("masters-filter-strip")).toBeVisible();

    await expect(page.getByTestId("export-xlsx-btn")).toBeVisible();
    await expect(page.getByTestId("export-pack-btn")).toBeVisible();

    await expect(page.getByTestId("cfo-executive-snapshot")).toBeVisible({ timeout: 30_000 });
    await expect(
      page.getByTestId("cfo-action-queue-empty").or(page.locator('[data-testid^="cfo-action-item"]')),
    ).toBeVisible({ timeout: 30_000 });

    await Promise.all([
      page.waitForURL(/\/app\/cfo-action-queue/, { timeout: 30_000 }),
      page.getByTestId("cfo-snapshot-action-queue").click(),
    ]);
    await expect(page.getByTestId("cfo-action-queue-page")).toBeVisible({ timeout: 30_000 });

    await page.getByTestId("cfo-action-queue-back-cfo").click();
    await expect(page.getByTestId("cfo-cockpit")).toBeVisible({ timeout: 30_000 });
  });
});
