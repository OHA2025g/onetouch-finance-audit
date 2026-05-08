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

test.describe("Phase 4 — CFO Command Center hub (PR-44)", () => {
  test("CFO hub loads; cockpit + readiness cards preserve master entity", async ({ page }) => {
    await loginAsCfo(page);
    await page.goto("/app/cfo-command-center");
    await expect(page.getByTestId("module-hub-cfo-command-center")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("masters-filter-bar-wrap")).toBeVisible();

    const entity = await selectSecondOptionValue(page, "master-filter-entity");
    await expect(page).toHaveURL(new RegExp(`m_entity=${entity}`));

    await page.getByTestId("hub-card-cfo-cockpit").click();
    await expect(page).toHaveURL(/\/app\/cfo/);
    await expect(page).toHaveURL(new RegExp(`m_entity=${entity}`));
    await expect(page.getByTestId("cfo-cockpit")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("masters-filter-strip")).toBeVisible();

    await page.goto(`/app/cfo-command-center?m_entity=${encodeURIComponent(entity)}`);
    await expect(page.getByTestId("module-hub-cfo-command-center")).toBeVisible();

    await page.getByTestId("hub-card-process-readiness").click();
    await expect(page).toHaveURL(/\/app\/readiness/);
    await expect(page).toHaveURL(new RegExp(`m_entity=${entity}`));
  });
});
