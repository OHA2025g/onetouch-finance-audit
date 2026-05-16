const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

async function selectSecondOptionValue(page, selectTestId) {
  const sel = page.getByTestId(selectTestId);
  await expect(sel).toBeVisible();
  await page.waitForFunction(
    (id) => {
      const el = document.querySelector(`[data-testid="${id}"]`);
      return el && el.tagName === "SELECT" && el.querySelectorAll("option").length >= 2;
    },
    selectTestId,
    { timeout: 30_000 },
  );
  const value = await sel.locator("option").nth(1).getAttribute("value");
  await sel.selectOption(value || undefined);
  return value;
}

test.describe("Phase 3 — CFO KPI drill-down (PR-43)", () => {
  test("hero tile opens KPI drill-down; back returns to CFO cockpit", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/cfo");
    await expect(page.getByTestId("cfo-cockpit")).toBeVisible({ timeout: 30_000 });

    await page.getByTestId("kpi-audit_readiness_pct").click();
    await expect(page).toHaveURL(/\/app\/kpi\/audit_readiness_pct/);
    await expect(page.getByTestId("kpi-drill-page")).toBeVisible();
    await expect(page.getByTestId("kpi-drill-loading")).toBeHidden({ timeout: 30_000 });
    await expect(page.getByTestId("kpi-drill-error")).toBeHidden();
    await expect(page.getByTestId("readiness-summary-strip")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("readiness-kpi-current")).toBeVisible();

    await page.getByTestId("kpi-back-cfo").click();
    await expect(page.getByTestId("cfo-cockpit")).toBeVisible({ timeout: 30_000 });
  });

  test("direct /app/kpi/:id route loads drill surface", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/kpi/high_critical_open_cases");
    await expect(page.getByTestId("kpi-drill-page")).toBeVisible();
    await expect(page.getByTestId("kpi-drill-loading")).toBeHidden({ timeout: 30_000 });
    await expect(page.getByTestId("kpi-drill-error")).toBeHidden();
  });

  test("master filter entity persists CFO → KPI navigation", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/cfo");
    await expect(page.getByTestId("cfo-cockpit")).toBeVisible({ timeout: 30_000 });

    const entity = await selectSecondOptionValue(page, "master-filter-entity");
    await expect(page).toHaveURL(new RegExp(`m_entity=${entity}`));

    await page.getByTestId("kpi-audit_readiness_pct").click();
    await expect(page).toHaveURL(/\/app\/kpi\/audit_readiness_pct/);
    await expect(page).toHaveURL(new RegExp(`m_entity=${entity}`));
  });
});
