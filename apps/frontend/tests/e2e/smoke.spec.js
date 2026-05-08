const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

async function loginAsSuperAdmin(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-super-admin").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

async function loginAsInternalAuditor(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-internal-auditor").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

test.describe("smoke library — CFO hubs", () => {
  test("CFO cockpit and treasury hub load", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/cfo");
    await expect(page.getByTestId("cfo-cockpit")).toBeVisible({ timeout: 30_000 });
    await page.goto("/app/treasury");
    await expect(page.getByTestId("treasury-page")).toBeVisible({ timeout: 30_000 });
  });

  test("Finance team performance page loads", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/finance-operations/team-performance");
    await expect(page.getByTestId("finance-team-page")).toBeVisible({ timeout: 30_000 });
  });
});

test.describe("phase 1 — expected module routes exist", () => {
  test("CFO can open all top-level module routes", async ({ page }) => {
    await loginAsCfo(page);
    const routes = [
      "/app/cfo-command-center",
      "/app/cfo-action-queue",
      "/app/finance-operations",
      "/app/financial-audit",
      "/app/continuous-audit",
      "/app/working-capital",
      "/app/treasury",
      "/app/compliance",
      "/app/risk-intelligence",
      "/app/evidence",
      "/app/cases",
      "/app/board-reporting",
      "/app/ai-copilot",
      "/app/integrations",
    ];
    for (const r of routes) {
      await page.goto(r);
      await expect(page.getByTestId("app-layout")).toBeVisible();
      // Should not bounce to login for authenticated user
      await expect(page).not.toHaveURL(/\/login/);
    }
  });

  test("CFO can open roadmap alias routes (wrappers)", async ({ page }) => {
    await loginAsCfo(page);
    const routes = [
      "/app/working-capital/receivables",
      "/app/working-capital/payables",
      "/app/treasury/dashboard",
      "/app/treasury/cash-forecast",
      "/app/treasury/forex-exposure",
      "/app/finance-operations/budget",
      "/app/finance-operations/budget-vs-actual",
      "/app/finance-operations/forecast-accuracy",
      "/app/financial-audit/gl-audit",
      "/app/financial-audit/journal-risk",
      "/app/financial-audit/reconciliations",
      "/app/financial-audit/bank-reconciliation",
      "/app/financial-audit/inventory-audit",
      "/app/financial-audit/physical-verification",
      "/app/financial-audit/fixed-assets-capex",
      "/app/continuous-audit/vendor-risk",
      "/app/continuous-audit/three-way-match",
      "/app/continuous-audit/revenue-audit",
      "/app/continuous-audit/credit-note-analytics",
      "/app/continuous-audit/rules-engine",
      "/app/compliance/related-party-transactions",
      "/app/compliance/notices-litigation",
      "/app/risk-intelligence/delegation-of-authority",
      "/app/risk-intelligence/policy-compliance",
      "/app/risk-intelligence/user-access-sod",
      "/app/risk-intelligence/master-data-quality",
      "/app/evidence/document-intelligence",
    ];
    for (const r of routes) {
      await page.goto(r);
      await expect(page.getByTestId("app-layout")).toBeVisible();
      await expect(page).not.toHaveURL(/\/login/);
    }
  });

  test("Super Admin can open admin routes", async ({ page }) => {
    await loginAsSuperAdmin(page);
    for (const r of ["/app/admin", "/app/admin/security", "/app/admin/audit-logs", "/app/admin/system-health"]) {
      await page.goto(r);
      await expect(page.getByTestId("app-layout")).toBeVisible();
      await expect(page).not.toHaveURL(/\/login/);
    }
  });

  test("Internal Auditor can open audit planning and evidence", async ({ page }) => {
    await loginAsInternalAuditor(page);
    for (const r of ["/app/audit", "/app/audit-planning", "/app/evidence", "/app/cases"]) {
      await page.goto(r);
      await expect(page.getByTestId("app-layout")).toBeVisible();
      await expect(page).not.toHaveURL(/\/login/);
    }
  });
});
