# Part 3 — Screen-level patterns & drill-down catalogue

## Screen template (reuse for UAT)

For any screen not expanded in Part 2, capture during walkthrough:

| Block | What to record |
|-------|----------------|
| A | Title, route, type, purpose, actors |
| B | Sections (header, filters, main, side panels) |
| C | Global controls (breadcrumb, refresh, export) |
| D | KPI cards — value, definition, drill |
| E | Charts — axes, legend, interaction, export |
| F | Tables — columns, sort, pagination, row actions, bulk |
| G | Filters — scope to KPI/chart/table, reset, persistence |
| H | Buttons — primary/secondary/destructive |
| I | Forms — validation messages |
| J | Modals — open/close, ESC, overlay click |
| K | Drill-downs — source, destination, query params |
| L | Detail pages — history, attachments, audit |
| M | Workflow steps |
| N | Business rules observed |
| O | Error / empty / loading |
| P | Gaps & recommendations |

---

## Drill-down catalogue (canonical paths)

Source: [`apps/frontend/src/lib/drillPaths.js`](../../apps/frontend/src/lib/drillPaths.js) and [`DrillView`](../../apps/frontend/src/pages/DrillView.jsx).

| Drill-down ID | Source | Trigger | Destination pattern | Filter / context |
|----------------|--------|---------|---------------------|------------------|
| DD-01 | Evidence graph / exceptions | Click related record | `/app/evidence/:exceptionId` | Exception scope |
| DD-02 | Evidence intelligence | Document link | `/app/evidence/evidence-intelligence-dashboard?document=` | Query `document` |
| DD-03 | KPI / insights | Typed link | `/app/cases/:id` | Case id |
| DD-04 | Reconciliation list | Row | `/app/reconciliations/:reconciliationId` | |
| DD-05 | Generic drill | Link builder | `/app/drill/:type/:id` | `type` ∈ control, invoice, vendor, customer, payment, journal, user, fixed_asset, capex_project, payroll_entry, ar_invoice, sales_order, employee, bank_transaction |
| DD-06 | CFO hero KPI | KPI with slug | `/app/kpi/:kpiId` | Masters params appended via `hrefWithMasterParams` |
| DD-07 | CFO hero row `drill_path` | Tile link | Static path (readiness, cases querystrings, audit, evidence) | Query params preserved where implemented |
| DD-08 | Exception source | `exceptionSourceDrillPath` | Maps `access_event` → user drill email/id | |

### KPI drill-down screen (`KpiDrilldownPage`)

| Item | Behavior |
|------|----------|
| Data load | Parallel `GET /kpi/definitions`, `/kpi/trend/:kpiId`, `/kpi/drilldown/:kpiId` |
| Back | Link to `/app/cfo` with master params |
| Contributing rows | `refRowHref` maps `type`+`id` via `pathForRelatedType`; special case `close_task` → month-end close cycle URL |

---

## Representative non-CFO screens (condensed)

### Evidence explorer

- **Route:** `/app/evidence`, `/app/evidence/:exceptionId`
- **API:** `/exceptions`, `/exceptions/count`
- **Purpose:** Browse control exceptions, navigate graph, open drills.

### Cases list & detail

- **Routes:** `/app/cases`, `/app/cases/:caseId`
- **Purpose:** Case workflow — **Needs Clarification** on full field list without live data.

### Month-end close

- **Routes:** `/app/finance-operations/month-end-close` and `/:cycleId`
- **Purpose:** Close task tracking — E2E in `month_end_close.spec.js`.

### Upload (ingest)

- **Route:** `/app/upload`
- **Action:** Multipart `POST /ingest/csv` — **Assumption:** template columns per backend ingest router.

---

*End of Part 3.*
