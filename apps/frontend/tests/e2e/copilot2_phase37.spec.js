const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 37 — Copilot 2.0 workbench (PR-77)", () => {
  test("AI copilot hub navigates to copilot 2 dashboard URL", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/ai-copilot");
    await expect(page.getByTestId("module-hub-ai-copilot")).toBeVisible({ timeout: 30_000 });

    const hub = page.locator('[data-testid="module-hub-ai-copilot"]');
    await hub
      .getByTestId("hub-card-copilot-2-workbench")
      .or(hub.locator('a[href*="copilot/copilot-2-dashboard"]'))
      .first()
      .click();

    await expect(page).toHaveURL(/\/app\/copilot\/copilot-2-dashboard\/?(?=\?|#|$)/);
    await expect(page.getByTestId("copilot-2-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="copilot-2-workbench-page"][data-copilot-phase37-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("cp37-kpi-sessions")).toBeVisible();
    await expect(page.getByTestId("cp37-sessions-table")).toBeVisible();
  });

  test("direct copilot/copilot-2-dashboard loads ladder", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/copilot/copilot-2-dashboard");
    await expect(page.getByTestId("copilot-2-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="copilot-2-workbench-page"][data-copilot-phase37-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("cp37-kpi-indexed-docs")).toBeVisible();
  });
});
