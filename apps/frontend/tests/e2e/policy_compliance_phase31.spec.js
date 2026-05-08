const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("Phase 31 — Policy compliance workbench (PR-71)", () => {
  test("risk intelligence command center navigates to policy compliance dashboard URL", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/risk-intelligence-command-center");
    await expect(page.getByTestId("module-hub-risk-intelligence")).toBeVisible({ timeout: 30_000 });

    const hub = page.locator('[data-testid="module-hub-risk-intelligence"]');
    await hub
      .getByTestId("hub-card-policy-compliance-workbench")
      .or(hub.locator('a[href*="risk-intelligence/policy-compliance-dashboard"]'))
      .first()
      .click();

    await expect(page).toHaveURL(/\/app\/risk-intelligence\/policy-compliance-dashboard\/?(?=\?|#|$)/);
    await expect(page.getByTestId("policy-compliance-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="policy-compliance-workbench-page"][data-policy-compliance-phase31-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("pc31-kpi-policies")).toBeVisible();
    await expect(page.getByTestId("policy-breaches-table")).toBeVisible();
  });

  test("direct risk-intelligence/policy-compliance-dashboard loads ladder", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/risk-intelligence/policy-compliance-dashboard");
    await expect(page.getByTestId("policy-compliance-workbench-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="policy-compliance-workbench-page"][data-policy-compliance-phase31-surface="true"]')).toBeVisible();
    await expect(page.getByTestId("pc31-kpi-attestations")).toBeVisible();
  });
});
