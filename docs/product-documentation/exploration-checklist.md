# Exploration checklist

**Status vocabulary:** Explored | Partially Explored | Not Working | Not Accessible | Not Applicable | Assumption | Needs Clarification

**Legend for this run:** “Explored (shell)” means authenticated user reached the route and `app-layout` rendered without redirect to login (Playwright `smoke.spec.js` phase 1). Deep controls (every filter, modal, export) require row-by-row manual pass — marked **Partially Explored** unless an E2E spec explicitly covers them.

## A. Global chrome

| Item Type | Name | Location | Status | Notes |
|-----------|------|----------|--------|-------|
| Page | Landing (marketing) | `/` | Partially Explored | Redirects to role home when session exists |
| Page | Login | `/login` | Explored | `data-testid="login-page"`; email/password + quick persona buttons |
| Layout | App shell | `/app/*` | Explored | `data-testid="app-layout"` |
| Control | Sidebar collapse | Sidebar header | Partially Explored | `sidebar-collapse-btn` |
| Control | Mobile nav overlay | `<lg` | Partially Explored | `Layout.jsx` |
| Control | Theme (light/dark) | Login + header | Partially Explored | `ThemeProvider` / `useTheme` |
| Control | Breadcrumbs | Main content top | Partially Explored | `Breadcrumbs.jsx` + `ROUTE_LABELS` |
| Control | Sign out | Header | Partially Explored | Clears `ota_token` / `ota_user`, navigates `/` |
| Control | Masters filter strip | Many dashboards | Partially Explored | `MastersFilterContext` |

## B. Post-login redirect targets

| Item Type | Name | Location | Status | Notes |
|-----------|------|----------|--------|-------|
| Route | CFO home | `/app/cfo` | Partially Explored | Playwright saw “Loading command center…”; `cfo-cockpit` not visible within 30s |
| Route | Super Admin home | `/app/super-admin` | Explored (shell) | Visited via test flow |
| Route | Controller home | `/app/controller` | Needs Clarification | Code path exists |
| Route | Internal Auditor home | `/app/audit` | Explored (shell) | smoke spec |
| Route | Compliance home | `/app/compliance` | Needs Clarification | |
| Route | Process Owner home | `/app/my-cases` | Needs Clarification | |
| Route | External Auditor home | `/app/auditor` | Needs Clarification | |

## C. Authenticated routes (`/app/...`)

Relative paths below are prefixed with `/app/`.

| Item Type | Name | Route | Status | Notes |
|-----------|------|-------|--------|-------|
| Route | App index (redirect) | `/app` | Explored | Maps to `RoleHome` → `roleToPath` |
| Route | CFO Command Center hub | `cfo-command-center` | Explored (shell) | `ModuleHubPage` |
| Route | Finance Operations hub | `finance-operations` | Explored (shell) | |
| Route | Financial Audit hub | `financial-audit` | Explored (shell) | |
| Route | Continuous Audit hub | `continuous-audit` | Explored (shell) | |
| Route | WC Command Center hub | `working-capital-command-center` | Needs Clarification | Not in short smoke list |
| Route | Treasury Command Center hub | `treasury-command-center` | Needs Clarification | |
| Route | Compliance Command Center hub | `compliance-command-center` | Needs Clarification | |
| Route | Risk Intelligence Command Center hub | `risk-intelligence-command-center` | Needs Clarification | |
| Route | WC dashboard | `working-capital` | Explored (shell) | |
| Route | Cash conversion | `working-capital/cash-conversion` | Partially Explored | Alias surface |
| Route | AR ageing | `working-capital/receivables` | Explored (shell) | smoke alias list |
| Route | AP ageing | `working-capital/payables` | Explored (shell) | |
| Route | Treasury hub | `treasury` | Explored (shell) | |
| Route | Treasury dashboard alias | `treasury/dashboard` | Explored (shell) | |
| Route | 13-week cash forecast | `treasury/cash-forecast` | Explored (shell) | |
| Route | Forex exposure | `treasury/forex-exposure` | Explored (shell) | |
| Route | Forex dashboard alias | `treasury/forex-exposure-dashboard` | Needs Clarification | |
| Route | Debt & investments | `treasury/debt-investments-dashboard` | Needs Clarification | |
| Route | Risk intelligence | `risk-intelligence` | Explored (shell) | |
| Route | Month-end close | `finance-operations/month-end-close` | Partially Explored | E2E `month_end_close.spec.js` |
| Route | MEC by cycle | `finance-operations/month-end-close/:cycleId` | Partially Explored | |
| Route | FP&A snapshot | `finance-operations/fpa` | Partially Explored | |
| Route | Budget master | `finance-operations/budget-master` | Partially Explored | E2E phase12 |
| Route | Budget vs actual | `finance-operations/budget-vs-actual-dashboard` | Partially Explored | |
| Route | Forecast accuracy | `finance-operations/forecast-accuracy-dashboard` | Partially Explored | |
| Route | Finance team performance | `finance-operations/team-performance` | Explored | `finance-team-page` visible in smoke |
| Route | Budget aliases | `finance-operations/budget` | Explored (shell) | |
| Route | BvA aliases | `finance-operations/budget-vs-actual` | Explored (shell) | |
| Route | Forecast alias | `finance-operations/forecast-accuracy` | Explored (shell) | |
| Route | Evidence & cases hub | `evidence-cases` | Needs Clarification | |
| Route | Board report automation | `board-reporting/report-automation-dashboard` | Partially Explored | E2E phase39 |
| Route | Board reporting hub | `board-reporting` | Explored (shell) | |
| Route | AI Copilot hub | `ai-copilot` | Explored (shell) | |
| Route | Integration hub dashboard | `integrations/integration-hub-dashboard` | Partially Explored | E2E phase38 |
| Route | Integrations hub | `integrations` | Explored (shell) | |
| Route | Enterprise hardening dashboard | `enterprise-hardening/enterprise-hardening-dashboard` | Partially Explored | E2E phase40 |
| Route | Enterprise hardening hub | `enterprise-hardening` | Needs Clarification | |
| Route | CFO Cockpit | `cfo` | Partially Explored | Data load stall in PW snapshot |
| Route | CFO action queue | `cfo-action-queue` | Partially Explored | |
| Route | KPI drill-down | `kpi/:kpiId` | Explored | `kpi-drill-page` direct route test passed |
| Route | Process readiness | `readiness` | Partially Explored | |
| Route | Controller dashboard | `controller` | Partially Explored | |
| Route | Reconciliation detail | `reconciliations/:reconciliationId` | Partially Explored | |
| Route | Audit workspace | `audit` | Explored (shell) | |
| Route | Compliance dashboard | `compliance` | Explored (shell) | |
| Route | RPT workbench | `compliance/rpt-dashboard` | Partially Explored | |
| Route | Legal workbench | `compliance/legal-dashboard` | Partially Explored | |
| Route | RPT alias | `compliance/related-party-transactions` | Explored (shell) | |
| Route | Legal alias | `compliance/notices-litigation` | Explored (shell) | |
| Route | My cases | `my-cases` | Partially Explored | |
| Route | All cases | `cases` | Explored (shell) | |
| Route | Case detail | `cases/:caseId` | Partially Explored | |
| Route | Evidence explorer | `evidence` | Explored (shell) | |
| Route | Evidence by exception | `evidence/:exceptionId` | Partially Explored | |
| Route | Evidence intelligence | `evidence/evidence-intelligence-dashboard` | Partially Explored | E2E phase34 |
| Route | Document intelligence alias | `evidence/document-intelligence` | Explored (shell) | |
| Route | Copilot 2 | `copilot/copilot-2-dashboard` | Partially Explored | E2E phase37 |
| Route | Copilot | `copilot` | Partially Explored | |
| Route | Admin console | `admin` | Explored (shell) | Super Admin smoke |
| Route | Admin security | `admin/security` | Explored (shell) | |
| Route | Admin system health | `admin/system-health` | Explored (shell) | |
| Route | Admin audit logs | `admin/audit-logs` | Explored (shell) | |
| Route | Admin org backfill | `admin/org-backfill` | Needs Clarification | |
| Route | Master audit trail | `admin/master-audit` | Needs Clarification | |
| Route | Master data quality admin | `admin/master-dq` | Needs Clarification | |
| Route | Audit log event | `audit-log/:logId` | Partially Explored | |
| Route | Entity rollups | `rollups` | Partially Explored | |
| Route | Governance / legal hold | `governance` | Partially Explored | |
| Route | Connectors | `connectors` | Partially Explored | |
| Route | Approvals queue | `approvals` | Partially Explored | |
| Route | Super Admin | `super-admin` | Explored (shell) | |
| Route | Audit planning list | `audit-planning` | Explored (shell) | Internal Auditor smoke |
| Route | New engagement | `audit-planning/new` | Partially Explored | |
| Route | Audit calendar | `audit-planning/calendar` | Partially Explored | |
| Route | Engagement detail | `audit-planning/engagements/:engagementId` | Partially Explored | |
| Route | Engagement team | `.../team` | Partially Explored | |
| Route | RACM builder | `.../racm` | Partially Explored | |
| Route | FS audit | `.../fs-audit` | Partially Explored | |
| Route | Schedules audit | `.../schedules-audit` | Partially Explored | |
| Route | IFC engine | `.../ifc-engine` | Partially Explored | |
| Route | Working papers hub | `.../working-papers` | Partially Explored | |
| Route | Sampling | `.../working-papers/sampling` | Partially Explored | |
| Route | Vouching | `.../working-papers/vouching` | Partially Explored | |
| Route | Working paper detail | `.../working-papers/:paperId` | Partially Explored | |
| Route | India compliance shell | `.../india-compliance` | Partially Explored | |
| Route | India sub-routes | `.../india-compliance/*` | Partially Explored | companies-act, gst, tds, tax-44ab, caro, calendar |
| Route | Report studio | `.../report-studio` | Partially Explored | |
| Route | Report studio children | `.../report-studio/*` | Partially Explored | observations, opinion, caro, preview |
| Route | Control library | `audit-planning/control-library` | Partially Explored | |
| Route | CA command center | `ca-command-center` | Partially Explored | |
| Route | Executive review | `executive-review` | Partially Explored | |
| Route | Audit committee | `audit-committee` | Partially Explored | |
| Route | FS Hub | `fs-hub` | Partially Explored | |
| Route | FS audit shortcut | `fs-audit` | Partially Explored | |
| Route | Schedule shortcut | `schedule` | Partially Explored | |
| Route | IFC shortcut | `ifc` | Partially Explored | |
| Route | India compliance shortcut | `india-compliance` | Partially Explored | |
| Route | Working papers shortcut | `working-papers` | Partially Explored | |
| Route | Reporting studio shortcut | `reporting-studio` | Partially Explored | |
| Route | Reporting tab shortcut | `reporting-tab` | Partially Explored | |
| Route | CSV upload | `upload` | Partially Explored | Super Admin nav |
| Route | Auditor portal | `auditor` | Partially Explored | |
| Route | Generic drill view | `drill/:type/:id` | Partially Explored | `DrillView.jsx` |
| Route | GL audit workbench | `financial-audit/gl-audit-dashboard` | Partially Explored | E2E phase15 |
| Route | GL audit hub alias | `financial-audit/gl-audit` | Explored (shell) | |
| Route | Journal risk | `financial-audit/journal-risk-dashboard` | Partially Explored | E2E phase16 |
| Route | Journal hub alias | `financial-audit/journal-risk` | Explored (shell) | |
| Route | Reconciliations WB | `financial-audit/reconciliations-dashboard` | Partially Explored | E2E phase17 |
| Route | Recon hub alias | `financial-audit/reconciliations` | Explored (shell) | |
| Route | Bank recon WB | `financial-audit/bank-reconciliation-dashboard` | Partially Explored | E2E phase18 |
| Route | Bank recon alias | `financial-audit/bank-reconciliation` | Explored (shell) | |
| Route | Inventory audit WB | `financial-audit/inventory-audit-dashboard` | Partially Explored | E2E phase23 |
| Route | Inventory alias | `financial-audit/inventory-audit` | Explored (shell) | |
| Route | Physical verification WB | `financial-audit/physical-verification-dashboard` | Partially Explored | E2E phase24 |
| Route | Physical ver alias | `financial-audit/physical-verification` | Explored (shell) | |
| Route | Fixed assets CAPEX WB | `financial-audit/fixed-assets-capex-dashboard` | Partially Explored | E2E phase25 |
| Route | FA alias | `financial-audit/fixed-assets-capex` | Explored (shell) | |
| Route | Vendor risk WB | `continuous-audit/vendor-risk-dashboard` | Partially Explored | E2E phase19 |
| Route | Vendor alias | `continuous-audit/vendor-risk` | Explored (shell) | |
| Route | Three-way match WB | `continuous-audit/three-way-match-dashboard` | Partially Explored | E2E phase20 |
| Route | TWM alias | `continuous-audit/three-way-match` | Explored (shell) | |
| Route | O2C audit WB | `continuous-audit/o2c-audit-dashboard` | Partially Explored | E2E phase21 |
| Route | Credit notes WB | `continuous-audit/credit-notes-dashboard` | Partially Explored | E2E phase22 |
| Route | O2C alias | `continuous-audit/revenue-audit` | Explored (shell) | |
| Route | Credit notes alias | `continuous-audit/credit-note-analytics` | Explored (shell) | |
| Route | Rules engine WB | `continuous-audit/rules-engine-dashboard` | Partially Explored | E2E phase35 |
| Route | Rules alias | `continuous-audit/rules-engine` | Explored (shell) | |
| Route | DoA WB | `risk-intelligence/doa-dashboard` | Partially Explored | E2E phase30 |
| Route | Policy compliance WB | `risk-intelligence/policy-compliance-dashboard` | Partially Explored | E2E phase31 |
| Route | Access SoD WB | `risk-intelligence/user-access-sod-dashboard` | Partially Explored | E2E phase32 |
| Route | Master DQ WB | `risk-intelligence/master-data-quality-dashboard` | Partially Explored | E2E phase33 |
| Route | Risk scoring WB | `risk-intelligence/risk-scoring-dashboard` | Partially Explored | E2E phase36 |
| Route | DoA aliases | `risk-intelligence/delegation-of-authority` | Explored (shell) | |
| Route | Policy aliases | `risk-intelligence/policy-compliance` | Explored (shell) | |
| Route | SoD aliases | `risk-intelligence/user-access-sod` | Explored (shell) | |
| Route | MDQ aliases | `risk-intelligence/master-data-quality` | Explored (shell) | |

## D. CFO sidebar navigation items (from `CFO_GROUPS`)

Each item: **Partially Explored** at minimum (link exists; destination shell often verified in Playwright batch).

See [`apps/frontend/src/lib/routeConfig.jsx`](../../apps/frontend/src/lib/routeConfig.jsx) — groups `cfo-command-center`, `finance-operations`, `financial-audit`, `continuous-audit`, `working-capital`, `treasury`, `compliance`, `risk-intelligence`, `evidence-cases`, `board-reporting`, `ai-copilot` with `to` paths as implemented in source.

## E. Super Admin sidebar (from `SUPER_ADMIN_GROUPS`)

Items under **Admin & Integrations**, **Platform**, **Command previews** — Explored (shell) for `/app/admin`, `/app/admin/security`, `/app/admin/audit-logs`, `/app/admin/system-health`; others **Needs Clarification** for deep forms.

## F. Auditor bundle sidebar

Produced dynamically by `auditorNavGroups(user)` — includes role-specific pin, CFO CC shortcuts, financial audit, compliance/IFC, continuous, board, evidence, AI, WC/treasury/risk hubs. **Partially Explored** per role without full matrix run.

## G. QA seed — E2E spec files (`apps/frontend/tests/e2e/`)

Use as **Test Case family IDs** (extend with step numbers in test plan):

| QA family ID | Spec file |
|--------------|-----------|
| TC-E2E-SMOKE | `smoke.spec.js` |
| TC-E2E-CFO-CC | `cfo_command_center.spec.js`, `cfo_command_center_hub.spec.js` |
| TC-E2E-CFO-KPI | `cfo_kpi_drilldown.spec.js` |
| TC-E2E-CFO-AQ | `cfo_action_queue.spec.js` |
| TC-E2E-MEC | `month_end_close.spec.js` |
| TC-E2E-WC | `working_capital.spec.js` |
| TC-E2E-MASTERS | `masters_filters.spec.js` |
| TC-E2E-PH09–40 | `receivables_ar_phase9.spec.js` … `enterprise_hardening_phase40.spec.js` (phase library) |

---

### Navigation hierarchy (condensed)

```
Application
├── / (LandingOrAppHome)
├── /login
└── /app (Protected + Layout)
    ├── Role home → roleToPath
    ├── Module hubs (command centers)
    ├── CFO Cockpit / readiness / controller / rollups / executive-review
    ├── Finance ops (MEC, FP&A, budget, forecast, team)
    ├── Financial audit (workbenches + audit planning + evidence + drill)
    ├── Continuous audit (workbenches + rules)
    ├── Working capital + treasury surfaces
    ├── Compliance + risk intelligence workbenches
    ├── Cases + evidence + copilot
    ├── Board reporting + audit committee
    ├── Integrations + enterprise hardening
    ├── Admin + super-admin + governance + connectors + approvals + upload
    ├── Audit planning / engagements / working papers / India / report studio
    └── Shortcuts (fs-hub, auditor portal, …)
```
