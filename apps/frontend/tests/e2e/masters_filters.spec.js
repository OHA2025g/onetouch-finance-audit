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
  // Wait for options to populate (EntityFilter loads from /api/masters/entities)
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

test.describe("Phase 2 — masters filters are URL-synced and preserved", () => {
  test("masters filter bar updates URL + hub card links preserve params", async ({ page }) => {
    await loginAsCfo(page);

    await page.goto("/app/finance-operations");
    await expect(page.getByTestId("module-hub-finance-operations")).toBeVisible();
    await expect(page.getByTestId("masters-filter-bar-wrap")).toBeVisible();

    const entity = await selectSecondOptionValue(page, "master-filter-entity");
    // Selecting a non-default period should write m_period; PeriodFilter always has options.
    const periodSel = page.getByTestId("master-filter-period");
    await expect(periodSel).toBeVisible();
    const periodValue = await periodSel.locator("option").nth(2).getAttribute("value");
    await periodSel.selectOption(periodValue || undefined);

    await expect(page).toHaveURL(new RegExp(`m_entity=${entity}`));
    if (periodValue) await expect(page).toHaveURL(new RegExp(`m_period=${periodValue}`));

    // Hub cards should append master params (hrefWithMasterParams)
    await page.getByRole("link", { name: /month-end close/i }).click();
    await expect(page).toHaveURL(/\/app\/finance-operations\/month-end-close/);
    await expect(page).toHaveURL(new RegExp(`m_entity=${entity}`));
  });

  test("masters filter strip exists on key dashboards", async ({ page }) => {
    await loginAsCfo(page);
    for (const r of ["/app/cfo", "/app/working-capital", "/app/treasury", "/app/risk-intelligence"]) {
      await page.goto(r);
      await expect(page.getByTestId("app-layout")).toBeVisible();
      await expect(page.getByTestId("masters-filter-strip")).toBeVisible({ timeout: 30_000 });
    }
  });
});

