const { test, expect } = require("@playwright/test");

async function loginAsCfo(page) {
  await page.goto("/login");
  await page.getByTestId("quick-persona-cfo").click();
  await page.waitForURL(/\/app\//, { timeout: 30_000 });
}

async function selectSecondEntity(page) {
  const sel = page.getByTestId("master-filter-entity");
  await expect(sel).toBeVisible();
  await page.waitForFunction(
    (id) => {
      const el = document.querySelector(`[data-testid="${id}"]`);
      return el && el.options && el.options.length >= 2;
    },
    "master-filter-entity",
    { timeout: 30_000 }
  );
  const value = await sel.locator("option").nth(1).getAttribute("value");
  await sel.selectOption(value || undefined);
  return value;
}

test.describe("Audit workspace PR1–PR5", () => {
  test("loads KPI strip, charts, and control deep link", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/audit");
    await expect(page.getByTestId("audit-workspace")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("audit-kpi-strip")).toBeVisible();
    await expect(page.getByTestId("audit-health-donut")).toBeVisible();
    await expect(page.getByTestId("audit-by-severity-chart")).toBeVisible();
    await expect(page.getByTestId("audit-posture-sentence")).toBeVisible();
    await expect(page.getByRole("heading", { name: /Audit workspace/i })).toBeVisible();
    const firstRow = page.locator('[data-testid^="control-row-"]').first();
    await expect(firstRow).toBeVisible();
    await firstRow.click();
    await expect(page).toHaveURL(/control=/);
    await expect(page.getByTestId("control-detail")).toBeVisible();
    await expect(page.getByTestId("run-control-btn")).toBeVisible();
    await expect(page.getByTestId("audit-run-all-btn")).toHaveText(/Run all controls/i);
  });

  test("external auditor cannot run controls", async ({ page }) => {
    await page.goto("/login");
    await page.getByTestId("quick-persona-external-auditor").click();
    await page.waitForURL(/\/app\//, { timeout: 30_000 });
    await page.goto("/app/audit");
    await expect(page.getByTestId("audit-workspace")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("audit-run-disabled")).toBeVisible();
    await expect(page.getByTestId("run-control-btn")).toHaveCount(0);
    await expect(page.getByTestId("audit-run-all-btn")).toHaveCount(0);
  });

  test("entity scope updates readiness KPI", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/audit");
    await expect(page.getByTestId("audit-workspace")).toBeVisible({ timeout: 30_000 });
    const readiness = page.getByTestId("audit-kpi-readiness");
    const firstEntity = await page.getByTestId("master-filter-entity").inputValue();
    const before = (await readiness.textContent())?.trim();
    await selectSecondEntity(page);
    await expect(page.getByTestId("audit-scope-chips")).toBeVisible({ timeout: 15_000 });
    await expect
      .poll(async () => (await readiness.textContent())?.trim(), { timeout: 15_000 })
      .not.toBe(before);
    await page.getByTestId("master-filter-entity").selectOption(firstEntity);
  });

  test("scope chips and list filter update posture", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/audit");
    await expect(page.getByTestId("audit-workspace")).toBeVisible({ timeout: 30_000 });

    const entity = await selectSecondEntity(page);
    await expect(page.getByTestId("audit-scope-chips")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("audit-scope-chips")).toContainText(entity);

    const posture = page.getByTestId("audit-posture-sentence");
    const before = await posture.textContent();

    await page.getByTestId("audit-status-chips").getByRole("button", { name: "Fail" }).click();
    await expect(posture).toContainText("controls in view");
    const after = await posture.textContent();
    expect(after).not.toEqual(before);
  });

  test("empty filter state and clear filters", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/audit");
    await expect(page.getByTestId("audit-workspace")).toBeVisible({ timeout: 30_000 });
    await page.getByTestId("audit-search-input").fill("__no_match_xyz__");
    await expect(page.getByTestId("audit-empty-filters")).toBeVisible({ timeout: 5_000 });
    await page.getByTestId("audit-empty-filters").getByRole("button", { name: /Clear all filters/i }).click();
    await expect(page.getByTestId("audit-empty-filters")).toHaveCount(0);
    await expect(page.locator('[data-testid^="control-row-"]').first()).toBeVisible();
  });

  test("trend window toggle reloads chart", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/audit");
    await expect(page.getByTestId("audit-trends-chart")).toBeVisible({ timeout: 30_000 });
    await page.getByTestId("audit-trend-days-toggle").getByRole("button", { name: "90d" }).click();
    await expect(page.getByTestId("audit-trends-chart")).toBeVisible();
  });
});
