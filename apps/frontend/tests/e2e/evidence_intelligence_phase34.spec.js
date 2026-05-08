const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 34 — Evidence intelligence workbench (PR-74)", () => {
  test("evidence & cases hub navigates to evidence intelligence dashboard URL", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/evidence-cases");
    await expect(page.getByTestId("module-hub-evidence-cases")).toBeVisible({ timeout: 30_000 });

    const hub = page.locator('[data-testid="module-hub-evidence-cases"]');
    await hub
      .getByTestId("hub-card-evidence-intelligence-workbench")
      .or(hub.locator('a[href*="evidence/evidence-intelligence-dashboard"]'))
      .first()
      .click();

    await expect(page).toHaveURL(/\/app\/evidence\/evidence-intelligence-dashboard\/?(?=\?|#|$)/);
    await expect(page.getByTestId("evidence-intelligence-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="evidence-intelligence-workbench-page"][data-evidence-intelligence-phase34-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("ei34-kpi-open-qi")).toBeVisible();
    await expect(page.getByTestId("evidence-qi-table")).toBeVisible();
  });

  test("direct evidence/evidence-intelligence-dashboard loads ladder", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/evidence/evidence-intelligence-dashboard");
    await expect(page.getByTestId("evidence-intelligence-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="evidence-intelligence-workbench-page"][data-evidence-intelligence-phase34-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("ei34-kpi-exceptions")).toBeVisible();
  });
});
