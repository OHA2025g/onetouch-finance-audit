# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: cfo_kpi_drilldown.spec.js >> Phase 3 — CFO KPI drill-down (PR-43) >> hero tile opens KPI drill-down; back returns to CFO cockpit
- Location: tests/e2e/cfo_kpi_drilldown.spec.js:27:3

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByTestId('cfo-cockpit')
Expected: visible
Timeout: 30000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" with timeout 30000ms
  - waiting for getByTestId('cfo-cockpit')

```

# Page snapshot

```yaml
- generic [ref=e2]:
  - region "Notifications alt+T"
  - generic [ref=e3]:
    - complementary [ref=e4]:
      - generic [ref=e5]:
        - generic [ref=e6]:
          - img [ref=e8]
          - generic [ref=e10]:
            - generic [ref=e11]: OneTouch
            - generic [ref=e12]: Audit · AI
        - button [ref=e13] [cursor=pointer]:
          - img [ref=e14]
      - navigation [ref=e16]:
        - generic [ref=e17]: Navigation
        - generic [ref=e18]:
          - button "CFO Command Center ▾" [expanded] [ref=e19] [cursor=pointer]:
            - generic [ref=e20]: CFO Command Center
            - generic [ref=e21]: ▾
          - link "CFO Cockpit →" [ref=e22] [cursor=pointer]:
            - /url: /app/cfo
            - img [ref=e23]
            - generic [ref=e25]: CFO Cockpit
            - generic [ref=e26]: →
          - link "Action queue →" [ref=e27] [cursor=pointer]:
            - /url: /app/cfo-action-queue
            - img [ref=e28]
            - generic [ref=e30]: Action queue
            - generic [ref=e31]: →
          - link "Process readiness matrix →" [ref=e32] [cursor=pointer]:
            - /url: /app/readiness
            - img [ref=e33]
            - generic [ref=e35]: Process readiness matrix
            - generic [ref=e36]: →
          - link "Controller dashboard →" [ref=e37] [cursor=pointer]:
            - /url: /app/controller
            - img [ref=e38]
            - generic [ref=e40]: Controller dashboard
            - generic [ref=e41]: →
          - link "Entity rollups →" [ref=e42] [cursor=pointer]:
            - /url: /app/rollups
            - img [ref=e43]
            - generic [ref=e45]: Entity rollups
            - generic [ref=e46]: →
          - link "Executive review →" [ref=e47] [cursor=pointer]:
            - /url: /app/executive-review
            - img [ref=e48]
            - generic [ref=e50]: Executive review
            - generic [ref=e51]: →
        - generic [ref=e52]:
          - button "Finance Operations ▾" [expanded] [ref=e53] [cursor=pointer]:
            - generic [ref=e54]: Finance Operations
            - generic [ref=e55]: ▾
          - link "Month-end close →" [ref=e56] [cursor=pointer]:
            - /url: /app/finance-operations/month-end-close
            - img [ref=e57]
            - generic [ref=e59]: Month-end close
            - generic [ref=e60]: →
          - link "Finance team →" [ref=e61] [cursor=pointer]:
            - /url: /app/finance-operations/team-performance
            - img [ref=e62]
            - generic [ref=e64]: Finance team
            - generic [ref=e65]: →
          - link "Budget master →" [ref=e66] [cursor=pointer]:
            - /url: /app/finance-operations/budget-master
            - img [ref=e67]
            - generic [ref=e69]: Budget master
            - generic [ref=e70]: →
          - link "Budget vs actual →" [ref=e71] [cursor=pointer]:
            - /url: /app/finance-operations/budget-vs-actual-dashboard
            - img [ref=e72]
            - generic [ref=e74]: Budget vs actual
            - generic [ref=e75]: →
          - link "Forecast accuracy →" [ref=e76] [cursor=pointer]:
            - /url: /app/finance-operations/forecast-accuracy-dashboard
            - img [ref=e77]
            - generic [ref=e79]: Forecast accuracy
            - generic [ref=e80]: →
          - link "FP&A snapshot →" [ref=e81] [cursor=pointer]:
            - /url: /app/finance-operations/fpa
            - img [ref=e82]
            - generic [ref=e84]: FP&A snapshot
            - generic [ref=e85]: →
          - link "Audit workspace →" [ref=e86] [cursor=pointer]:
            - /url: /app/audit
            - img [ref=e87]
            - generic [ref=e89]: Audit workspace
            - generic [ref=e90]: →
        - generic [ref=e91]:
          - button "Financial Audit ▾" [expanded] [ref=e92] [cursor=pointer]:
            - generic [ref=e93]: Financial Audit
            - generic [ref=e94]: ▾
          - link "GL audit workbench →" [ref=e95] [cursor=pointer]:
            - /url: /app/financial-audit/gl-audit-dashboard
            - img [ref=e96]
            - generic [ref=e98]: GL audit workbench
            - generic [ref=e99]: →
          - link "Journal risk →" [ref=e100] [cursor=pointer]:
            - /url: /app/financial-audit/journal-risk-dashboard
            - img [ref=e101]
            - generic [ref=e103]: Journal risk
            - generic [ref=e104]: →
          - link "Reconciliations →" [ref=e105] [cursor=pointer]:
            - /url: /app/financial-audit/reconciliations-dashboard
            - img [ref=e106]
            - generic [ref=e108]: Reconciliations
            - generic [ref=e109]: →
          - link "Bank reconciliation →" [ref=e110] [cursor=pointer]:
            - /url: /app/financial-audit/bank-reconciliation-dashboard
            - img [ref=e111]
            - generic [ref=e113]: Bank reconciliation
            - generic [ref=e114]: →
          - link "Inventory audit →" [ref=e115] [cursor=pointer]:
            - /url: /app/financial-audit/inventory-audit-dashboard
            - img [ref=e116]
            - generic [ref=e118]: Inventory audit
            - generic [ref=e119]: →
          - link "Physical verification →" [ref=e120] [cursor=pointer]:
            - /url: /app/financial-audit/physical-verification-dashboard
            - img [ref=e121]
            - generic [ref=e123]: Physical verification
            - generic [ref=e124]: →
          - link "Fixed assets · CAPEX →" [ref=e125] [cursor=pointer]:
            - /url: /app/financial-audit/fixed-assets-capex-dashboard
            - img [ref=e126]
            - generic [ref=e128]: Fixed assets · CAPEX
            - generic [ref=e129]: →
          - link "Audit planning →" [ref=e130] [cursor=pointer]:
            - /url: /app/audit-planning
            - img [ref=e131]
            - generic [ref=e133]: Audit planning
            - generic [ref=e134]: →
          - link "Evidence explorer →" [ref=e135] [cursor=pointer]:
            - /url: /app/evidence
            - img [ref=e136]
            - generic [ref=e138]: Evidence explorer
            - generic [ref=e139]: →
        - generic [ref=e140]:
          - button "Continuous Audit ▾" [expanded] [ref=e141] [cursor=pointer]:
            - generic [ref=e142]: Continuous Audit
            - generic [ref=e143]: ▾
          - link "Continuous assurance →" [ref=e144] [cursor=pointer]:
            - /url: /app/executive-review?tab=assurance
            - img [ref=e145]
            - generic [ref=e147]: Continuous assurance
            - generic [ref=e148]: →
          - link "Rules engine →" [ref=e149] [cursor=pointer]:
            - /url: /app/continuous-audit/rules-engine-dashboard
            - img [ref=e150]
            - generic [ref=e152]: Rules engine
            - generic [ref=e153]: →
          - link "Vendor risk →" [ref=e154] [cursor=pointer]:
            - /url: /app/continuous-audit/vendor-risk-dashboard
            - img [ref=e155]
            - generic [ref=e157]: Vendor risk
            - generic [ref=e158]: →
          - link "Three-way match →" [ref=e159] [cursor=pointer]:
            - /url: /app/continuous-audit/three-way-match-dashboard
            - img [ref=e160]
            - generic [ref=e162]: Three-way match
            - generic [ref=e163]: →
          - link "O2C audit →" [ref=e164] [cursor=pointer]:
            - /url: /app/continuous-audit/o2c-audit-dashboard
            - img [ref=e165]
            - generic [ref=e167]: O2C audit
            - generic [ref=e168]: →
          - link "Credit notes →" [ref=e169] [cursor=pointer]:
            - /url: /app/continuous-audit/credit-notes-dashboard
            - img [ref=e170]
            - generic [ref=e172]: Credit notes
            - generic [ref=e173]: →
          - link "Controls & tests →" [ref=e174] [cursor=pointer]:
            - /url: /app/audit
            - img [ref=e175]
            - generic [ref=e177]: Controls & tests
            - generic [ref=e178]: →
        - generic [ref=e179]:
          - button "Working Capital ▾" [expanded] [ref=e180] [cursor=pointer]:
            - generic [ref=e181]: Working Capital
            - generic [ref=e182]: ▾
          - link "WC dashboard →" [ref=e183] [cursor=pointer]:
            - /url: /app/working-capital
            - img [ref=e184]
            - generic [ref=e186]: WC dashboard
            - generic [ref=e187]: →
          - link "Receivables · AR ageing →" [ref=e188] [cursor=pointer]:
            - /url: /app/working-capital/receivables
            - img [ref=e189]
            - generic [ref=e191]: Receivables · AR ageing
            - generic [ref=e192]: →
          - link "Payables · AP ageing →" [ref=e193] [cursor=pointer]:
            - /url: /app/working-capital/payables
            - img [ref=e194]
            - generic [ref=e196]: Payables · AP ageing
            - generic [ref=e197]: →
          - link "Cash conversion cycle →" [ref=e198] [cursor=pointer]:
            - /url: /app/working-capital/cash-conversion
            - img [ref=e199]
            - generic [ref=e201]: Cash conversion cycle
            - generic [ref=e202]: →
        - generic [ref=e203]:
          - button "Treasury ▾" [expanded] [ref=e204] [cursor=pointer]:
            - generic [ref=e205]: Treasury
            - generic [ref=e206]: ▾
          - link "Treasury hub →" [ref=e207] [cursor=pointer]:
            - /url: /app/treasury
            - img [ref=e208]
            - generic [ref=e210]: Treasury hub
            - generic [ref=e211]: →
          - link "Cash forecast · 13-week →" [ref=e212] [cursor=pointer]:
            - /url: /app/treasury/cash-forecast
            - img [ref=e213]
            - generic [ref=e215]: Cash forecast · 13-week
            - generic [ref=e216]: →
          - link "Debt & investments →" [ref=e217] [cursor=pointer]:
            - /url: /app/treasury/debt-investments-dashboard
            - img [ref=e218]
            - generic [ref=e220]: Debt & investments
            - generic [ref=e221]: →
          - link "Forex exposure →" [ref=e222] [cursor=pointer]:
            - /url: /app/treasury/forex-exposure-dashboard
            - img [ref=e223]
            - generic [ref=e225]: Forex exposure
            - generic [ref=e226]: →
          - link "Bank / ERP connectors →" [ref=e227] [cursor=pointer]:
            - /url: /app/connectors
            - img [ref=e228]
            - generic [ref=e230]: Bank / ERP connectors
            - generic [ref=e231]: →
        - generic [ref=e232]:
          - button "Compliance ▾" [expanded] [ref=e233] [cursor=pointer]:
            - generic [ref=e234]: Compliance
            - generic [ref=e235]: ▾
          - link "Compliance dashboard →" [ref=e236] [cursor=pointer]:
            - /url: /app/compliance
            - img [ref=e237]
            - generic [ref=e239]: Compliance dashboard
            - generic [ref=e240]: →
          - link "Related party transactions →" [ref=e241] [cursor=pointer]:
            - /url: /app/compliance/rpt-dashboard
            - img [ref=e242]
            - generic [ref=e244]: Related party transactions
            - generic [ref=e245]: →
          - link "Legal notices & litigation →" [ref=e246] [cursor=pointer]:
            - /url: /app/compliance/legal-dashboard
            - img [ref=e247]
            - generic [ref=e249]: Legal notices & litigation
            - generic [ref=e250]: →
        - generic [ref=e251]:
          - button "Risk Intelligence ▾" [expanded] [ref=e252] [cursor=pointer]:
            - generic [ref=e253]: Risk Intelligence
            - generic [ref=e254]: ▾
          - link "Risk intelligence →" [ref=e255] [cursor=pointer]:
            - /url: /app/risk-intelligence
            - img [ref=e256]
            - generic [ref=e258]: Risk intelligence
            - generic [ref=e259]: →
          - link "Risk scoring →" [ref=e260] [cursor=pointer]:
            - /url: /app/risk-intelligence/risk-scoring-dashboard
            - img [ref=e261]
            - generic [ref=e263]: Risk scoring
            - generic [ref=e264]: →
          - link "Delegation of authority →" [ref=e265] [cursor=pointer]:
            - /url: /app/risk-intelligence/doa-dashboard
            - img [ref=e266]
            - generic [ref=e268]: Delegation of authority
            - generic [ref=e269]: →
          - link "Policy compliance →" [ref=e270] [cursor=pointer]:
            - /url: /app/risk-intelligence/policy-compliance-dashboard
            - img [ref=e271]
            - generic [ref=e273]: Policy compliance
            - generic [ref=e274]: →
          - link "Access & SoD →" [ref=e275] [cursor=pointer]:
            - /url: /app/risk-intelligence/user-access-sod-dashboard
            - img [ref=e276]
            - generic [ref=e278]: Access & SoD
            - generic [ref=e279]: →
          - link "Master data quality →" [ref=e280] [cursor=pointer]:
            - /url: /app/risk-intelligence/master-data-quality-dashboard
            - img [ref=e281]
            - generic [ref=e283]: Master data quality
            - generic [ref=e284]: →
        - generic [ref=e285]:
          - button "Evidence & Cases ▾" [expanded] [ref=e286] [cursor=pointer]:
            - generic [ref=e287]: Evidence & Cases
            - generic [ref=e288]: ▾
          - link "My cases →" [ref=e289] [cursor=pointer]:
            - /url: /app/my-cases
            - img [ref=e290]
            - generic [ref=e292]: My cases
            - generic [ref=e293]: →
          - link "All cases →" [ref=e294] [cursor=pointer]:
            - /url: /app/cases
            - img [ref=e295]
            - generic [ref=e297]: All cases
            - generic [ref=e298]: →
          - link "Evidence intelligence →" [ref=e299] [cursor=pointer]:
            - /url: /app/evidence/evidence-intelligence-dashboard
            - img [ref=e300]
            - generic [ref=e302]: Evidence intelligence
            - generic [ref=e303]: →
          - link "Evidence explorer →" [ref=e304] [cursor=pointer]:
            - /url: /app/evidence
            - img [ref=e305]
            - generic [ref=e307]: Evidence explorer
            - generic [ref=e308]: →
        - generic [ref=e309]:
          - button "Board Reporting ▾" [expanded] [ref=e310] [cursor=pointer]:
            - generic [ref=e311]: Board Reporting
            - generic [ref=e312]: ▾
          - link "CFO & Committee hub →" [ref=e313] [cursor=pointer]:
            - /url: /app/executive-review
            - img [ref=e314]
            - generic [ref=e316]: CFO & Committee hub
            - generic [ref=e317]: →
          - link "Audit committee →" [ref=e318] [cursor=pointer]:
            - /url: /app/audit-committee
            - img [ref=e319]
            - generic [ref=e321]: Audit committee
            - generic [ref=e322]: →
          - link "Report automation →" [ref=e323] [cursor=pointer]:
            - /url: /app/board-reporting/report-automation-dashboard
            - img [ref=e324]
            - generic [ref=e326]: Report automation
            - generic [ref=e327]: →
          - link "Reporting studio →" [ref=e328] [cursor=pointer]:
            - /url: /app/reporting-studio
            - img [ref=e329]
            - generic [ref=e331]: Reporting studio
            - generic [ref=e332]: →
        - generic [ref=e333]:
          - button "AI Copilot ▾" [expanded] [ref=e334] [cursor=pointer]:
            - generic [ref=e335]: AI Copilot
            - generic [ref=e336]: ▾
          - link "Copilot workspace →" [ref=e337] [cursor=pointer]:
            - /url: /app/copilot
            - img [ref=e338]
            - generic [ref=e340]: Copilot workspace
            - generic [ref=e341]: →
          - link "Copilot 2.0 →" [ref=e342] [cursor=pointer]:
            - /url: /app/copilot/copilot-2-dashboard
            - img [ref=e343]
            - generic [ref=e345]: Copilot 2.0
            - generic [ref=e346]: →
      - generic [ref=e347]:
        - generic [ref=e348]:
          - generic [ref=e349]: Signed in
          - generic [ref=e350]: Marion Acheson
          - generic [ref=e351]: CFO
        - button "Sign out" [ref=e352] [cursor=pointer]:
          - img [ref=e353]
          - text: Sign out
    - main [ref=e355]:
      - generic [ref=e356]:
        - generic [ref=e357]:
          - generic [ref=e358]: system · live
          - generic [ref=e360]: Tue 12 May, 01:26 GMT+5:30
        - generic [ref=e361]:
          - button "Toggle theme" [ref=e362] [cursor=pointer]:
            - img [ref=e363]
            - generic [ref=e365]: light
          - generic [ref=e366]:
            - generic [ref=e367]: M
            - generic [ref=e368]: CFO
      - generic [ref=e369]:
        - navigation "Breadcrumb" [ref=e370]:
          - link "Home" [ref=e371] [cursor=pointer]:
            - /url: /
            - generic [ref=e372]:
              - img [ref=e373]
              - text: Home
          - img [ref=e375]
          - link "Workspace" [ref=e377] [cursor=pointer]:
            - /url: /app
          - img [ref=e378]
          - generic [ref=e380]: CFO Cockpit
        - generic [ref=e381]: Loading command center…
```

# Test source

```ts
  1  | const { test, expect } = require("@playwright/test");
  2  | 
  3  | async function loginAsCfo(page) {
  4  |   await page.goto("/login");
  5  |   await expect(page.getByTestId("login-page")).toBeVisible();
  6  |   await page.getByTestId("quick-persona-cfo").click();
  7  |   await page.waitForURL(/\/app\//, { timeout: 30_000 });
  8  | }
  9  | 
  10 | async function selectSecondOptionValue(page, selectTestId) {
  11 |   const sel = page.getByTestId(selectTestId);
  12 |   await expect(sel).toBeVisible();
  13 |   await page.waitForFunction(
  14 |     (id) => {
  15 |       const el = document.querySelector(`[data-testid="${id}"]`);
  16 |       return el && el.tagName === "SELECT" && el.querySelectorAll("option").length >= 2;
  17 |     },
  18 |     selectTestId,
  19 |     { timeout: 30_000 },
  20 |   );
  21 |   const value = await sel.locator("option").nth(1).getAttribute("value");
  22 |   await sel.selectOption(value || undefined);
  23 |   return value;
  24 | }
  25 | 
  26 | test.describe("Phase 3 — CFO KPI drill-down (PR-43)", () => {
  27 |   test("hero tile opens KPI drill-down; back returns to CFO cockpit", async ({ page }) => {
  28 |     await loginAsCfo(page);
  29 |     await page.goto("/app/cfo");
> 30 |     await expect(page.getByTestId("cfo-cockpit")).toBeVisible({ timeout: 30_000 });
     |                                                   ^ Error: expect(locator).toBeVisible() failed
  31 | 
  32 |     await page.getByTestId("kpi-audit_readiness_pct").click();
  33 |     await expect(page).toHaveURL(/\/app\/kpi\/audit_readiness_pct/);
  34 |     await expect(page.getByTestId("kpi-drill-page")).toBeVisible();
  35 |     await expect(page.getByTestId("kpi-drill-loading")).toBeHidden({ timeout: 30_000 });
  36 |     await expect(page.getByTestId("kpi-drill-error")).toBeHidden();
  37 | 
  38 |     await page.getByTestId("kpi-back-cfo").click();
  39 |     await expect(page.getByTestId("cfo-cockpit")).toBeVisible({ timeout: 30_000 });
  40 |   });
  41 | 
  42 |   test("direct /app/kpi/:id route loads drill surface", async ({ page }) => {
  43 |     await loginAsCfo(page);
  44 |     await page.goto("/app/kpi/high_critical_open_cases");
  45 |     await expect(page.getByTestId("kpi-drill-page")).toBeVisible();
  46 |     await expect(page.getByTestId("kpi-drill-loading")).toBeHidden({ timeout: 30_000 });
  47 |     await expect(page.getByTestId("kpi-drill-error")).toBeHidden();
  48 |   });
  49 | 
  50 |   test("master filter entity persists CFO → KPI navigation", async ({ page }) => {
  51 |     await loginAsCfo(page);
  52 |     await page.goto("/app/cfo");
  53 |     await expect(page.getByTestId("cfo-cockpit")).toBeVisible({ timeout: 30_000 });
  54 | 
  55 |     const entity = await selectSecondOptionValue(page, "master-filter-entity");
  56 |     await expect(page).toHaveURL(new RegExp(`m_entity=${entity}`));
  57 | 
  58 |     await page.getByTestId("kpi-audit_readiness_pct").click();
  59 |     await expect(page).toHaveURL(/\/app\/kpi\/audit_readiness_pct/);
  60 |     await expect(page).toHaveURL(new RegExp(`m_entity=${entity}`));
  61 |   });
  62 | });
  63 | 
```