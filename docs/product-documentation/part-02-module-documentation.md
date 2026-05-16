# Part 2 — Module-wise deep documentation

Each module follows the template: **4.x.1 Overview** → **4.x.2 Entry points** → **4.x.3 Screen index** → **4.x.4 Notes** (screen-level A–P detail for CFO Cockpit and KPI drill only; other screens follow the same pattern in implementation — extend during customer UAT).

---

## Module 1: CFO Command Center

### 4.1.1 Module overview

| Item | Details |
|------|---------|
| Module name | CFO Command Center |
| Menu location | Sidebar — first group for CFO; “CFO overview” in auditor bundle |
| Routes | `/app/cfo`, `/app/cfo-action-queue`, `/app/readiness`, `/app/controller`, `/app/rollups`, `/app/executive-review`, `/app/kpi/:kpiId` |
| Business purpose | Executive visibility into audit readiness, exposure, cases, evidence, remediation; fast actions |
| Primary users | CFO |
| Secondary users | Controller (controller dashboard link), auditors (read-only previews in their nav) |
| Key outcomes | Prioritized actions, KPI trends, exportable committee pack |
| Main screens | CFO Cockpit, Action queue, Readiness matrix, KPI drill-down |
| Workflow type | Monitoring + transactional (approvals) + reporting |

### 4.1.2 Entry points

| Entry point | Source | Action | Destination |
|-------------|--------|--------|---------------|
| Sidebar | Any | Click “CFO Cockpit” | `/app/cfo` |
| Post-login | Auth | CFO login | `/app/cfo` |
| KPI tile | CFO Cockpit | Click KPI link | `/app/kpi/{id}` or `drill_path` |
| Quick link | CFO Cockpit header | Risk intelligence | `/app/risk-intelligence` |
| Quick link | CFO Cockpit header | Audit committee | `/app/audit-committee` |

### 4.1.3 Screens inside module

| Screen ID | Screen name | Route | Screen type | Purpose | Primary action |
|-----------|---------------|-------|-------------|---------|----------------|
| CC-01 | CFO Cockpit | `/app/cfo` | Dashboard | KPIs, heatmap, charts, action queue | Run all, export, approve |
| CC-02 | CFO action queue | `/app/cfo-action-queue` | List / detail | Full queue | Approve / escalate |
| CC-03 | Process readiness | `/app/readiness` | Matrix | Process × readiness | Filter / navigate |
| CC-04 | KPI drill-down | `/app/kpi/:kpiId` | Drill-down | Trend + contributing rows | Navigate to related records |
| CC-05 | Controller dashboard | `/app/controller` | Dashboard | Controller KPIs | Review |
| CC-06 | Entity rollups | `/app/rollups` | Configuration / analytics | Grouping | Select entities |
| CC-07 | Executive review | `/app/executive-review` | Hub / tabs | Committee views | Tab navigation |

### 4.1.4 Screen deep dive — CFO Cockpit (CC-01)

**A. Basic details:** Dashboard for CFO; answers “Are we audit-ready and where is exposure?”; primary actions: refresh data, run all controls, export pack, process filter, hero reorder, action queue approve/escalate, open copilot.

**B. Layout sections:** Page header; masters strip; hero KPI band; readiness heatmap; top failing controls; charts (Recharts); insight side panel; action queue strip.

**C. Header controls:** Export XLSX, export pack (PDF/PPTX), run all, process filter + clear, mobile filters, links to audit committee & risk intelligence, hero reorder UI.

**D. KPI cards (hero):** Driven by `GET /kpi/cfo-summary` when available; else defaults in code:

| KPI id / label | Drill | Interpretation |
|----------------|-------|----------------|
| `audit_readiness_pct` / Audit readiness | `/app/readiness` | Higher is better |
| `unresolved_high_risk_exposure` | `/app/cases?status=open` | USD exposure |
| `high_critical_open_cases` | `/app/cases?status=open&severity=critical` | Count |
| `repeat_finding_rate_pct` | `/app/audit` | Lower repeat rate preferred |
| `evidence_completeness_pct` | `/app/evidence` | Completeness |
| `remediation_sla_pct` | `/app/cases` | SLA adherence |

**E. Charts:** Line/area charts from CFO dashboard payload (`data` from `/dashboard/cfo`) — exact series depend on API.

**F. Tables:** Top risks table; action queue list; failing controls list — columns from API models.

**G. Filters:** Entity/period/department/cost center via `MastersFilterStrip`; process filter client-side on heatmap/top risks.

**H. Buttons:** Run all, exports, approve, escalate, copilot, reorder controls — see `data-testid` in `CFOCockpit.jsx`.

**I–P:** Forms are minimal inline notes for approve/escalate; modals per implementation; drill-down to `KpiDrilldownPage` or `drill_path`; business rules from severity coloring in `hero` useMemo; errors: `cfo-error` + toast on load failure.

---

## Module 2: Finance Operations

### 4.2.1 Overview

| Item | Details |
|------|---------|
| Purpose | Month-end close, FP&A, budgets, forecasts, finance team performance |
| Routes | `/app/finance-operations/*`, `/app/finance-operations` hub |
| Users | CFO primarily |
| Workflow | Monitoring + transactional (variance comments / approvals in BvA) |

### 4.2.3 Screens

| Screen | Route | Type |
|---------|-------|------|
| Month-end close | `.../month-end-close`, `.../:cycleId` | Dashboard + cycle detail |
| FP&A snapshot | `.../fpa` | Dashboard |
| Budget master | `.../budget-master` | Tables / forms |
| Budget vs actual | `.../budget-vs-actual-dashboard` | Analytics + POST comments/approve |
| Forecast accuracy | `.../forecast-accuracy-dashboard` | Analytics |
| Finance team | `.../team-performance` | HR-like metrics |

---

## Module 3: Financial Audit

### 4.3.1 Overview

Financial statement support: GL, journals, reconciliations, bank, inventory, physical counts, fixed assets; plus **audit planning** engagement tree and **control library**.

**Key routes:** `/app/financial-audit/*`, `/app/audit-planning*`, `/app/evidence*`, `/app/audit-planning/control-library`.

**Screens (workbenches):** Each `*WorkbenchPage.jsx` — summary cards + data tables + filters; API patterns in [cross-check-api-surfaces.md](./cross-check-api-surfaces.md).

---

## Module 4: Continuous Audit

Routes under `/app/continuous-audit/*` — vendor risk, three-way match, O2C, credit notes, rules engine. Hub routes alias to `ModuleHubPage`.

---

## Module 5: Working Capital & Treasury

| Area | Routes |
|------|--------|
| WC | `/app/working-capital`, `.../receivables`, `.../payables`, `.../cash-conversion` |
| Treasury | `/app/treasury`, `.../cash-forecast`, `.../forex-exposure*`, `.../debt-investments-dashboard` |

**Notable action:** AP payment hold `POST /ap/payment-hold` from payables page.

---

## Module 6: Compliance

| Screen | Route |
|--------|-------|
| Compliance dashboard | `/app/compliance` — `GET /dashboard/compliance` |
| Related party | `.../rpt-dashboard`, alias `.../related-party-transactions` |
| Legal notices | `.../legal-dashboard`, alias `.../notices-litigation` |

---

## Module 7: Risk Intelligence

Routes: `/app/risk-intelligence`, scoring dashboard, DoA, policy compliance, access SoD, master data quality. APIs listed in cross-check doc.

---

## Module 8: Evidence & Cases

| Screen | Route |
|--------|-------|
| My cases | `/app/my-cases` |
| All cases | `/app/cases`, `/app/cases/:caseId` |
| Evidence explorer | `/app/evidence`, `/app/evidence/:exceptionId` |
| Evidence intelligence | `/app/evidence/evidence-intelligence-dashboard` |

---

## Module 9: Board Reporting

`/app/audit-committee`, `/app/board-reporting*`, `/app/reporting-studio`, `/app/reporting-tab`, `/app/board-reporting/report-automation-dashboard`.

---

## Module 10: AI Copilot

`/app/copilot`, `/app/copilot/copilot-2-dashboard`, `/app/ai-copilot` hub. Uses insights and copilot-specific flows (see Part 6).

---

## Module 11: Integrations & Enterprise

`/app/integrations*`, `/app/enterprise-hardening*`, `/app/connectors`.

---

## Module 12: Admin & Platform

| Screen | Route | Role |
|--------|-------|------|
| Super Admin users | `/app/super-admin` | Super Admin |
| Admin console | `/app/admin` | Super Admin |
| Security / health / logs | `/app/admin/security`, `system-health`, `audit-logs` | Super Admin |
| Master audit / DQ | `/app/admin/master-audit`, `master-dq` | Super Admin |
| Org backfill | `/app/admin/org-backfill` | Super Admin |
| Governance | `/app/governance` | Super Admin |
| Approvals | `/app/approvals` | Super Admin |
| CSV upload | `/app/upload` | Super Admin |

---

## Module 13: Audit Planning & Report Studio

**Engagement routes** (`/app/audit-planning/engagements/:engagementId/...`): detail, team, RACM, FS audit, schedules audit, IFC engine, working papers (hub, sampling, vouching, paper detail), India compliance subtree, report studio subtree (observations, opinion, CARO, preview).

**Shortcuts:** `/app/fs-hub`, `/app/fs-audit`, `/app/schedule`, `/app/ifc`, `/app/india-compliance`, `/app/working-papers`, `/app/reporting-studio`, `/app/reporting-tab`, `/app/ca-command-center`, `/app/auditor`.

---

*End of Part 2 — extend per-screen A–P tables during customer UAT using this skeleton.*
