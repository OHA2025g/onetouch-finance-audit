const { test, expect } = require("@playwright/test");

async function loginAsSuperAdmin(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-super-admin").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 40 — Enterprise hardening workbench (PR-80)", () => {
  test("enterprise hardening hub navigates to dashboard URL", async ({ page }) => {
    await loginAsSuperAdmin(page);
    await page.goto("/app/enterprise-hardening");
    await expect(page.getByTestId("module-hub-enterprise-hardening")).toBeVisible({ timeout: 30_000 });

    const hub = page.locator('[data-testid="module-hub-enterprise-hardening"]');
    await hub
      .getByTestId("hub-card-enterprise-hardening-workbench")
      .or(hub.locator('a[href*="enterprise-hardening/enterprise-hardening-dashboard"]'))
      .first()
      .click();

    await expect(page).toHaveURL(/\/app\/enterprise-hardening\/enterprise-hardening-dashboard\/?(?=\?|#|$)/);
    await expect(page.getByTestId("enterprise-hardening-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(
      page.locator('[data-testid="enterprise-hardening-workbench-page"][data-enterprise-hardening-phase40-surface="true"]')
    ).toBeVisible();
    await expect(page.getByTestId("eh40-kpi-live")).toBeVisible();
    await expect(page.getByTestId("eh40-audit-table")).toBeVisible();
  });

  test("direct enterprise-hardening/enterprise-hardening-dashboard loads for Super Admin", async ({ page }) => {
    await loginAsSuperAdmin(page);
    await page.goto("/app/enterprise-hardening/enterprise-hardening-dashboard");
    await expect(page.getByTestId("enterprise-hardening-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("eh40-kpi-deep-health")).toBeVisible();
    await expect(page.getByTestId("eh40-security-config-pre")).toBeVisible();
  });
});
