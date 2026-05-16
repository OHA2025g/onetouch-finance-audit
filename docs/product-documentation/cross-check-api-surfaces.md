# Cross-check: UI ↔ API (mock vs live)

All calls use Axios instance `http` with base `/api` (or configured backend). **Live data** when MongoDB is seeded and routers return DB-backed JSON; some surfaces may return **synthetic/demo** payloads if services short-circuit (e.g. missing `EMERGENT_LLM_KEY` for optional AI — see [`infra/docker-compose.yml`](../../infra/docker-compose.yml)).

## Global masters (filters)

| UI surface | HTTP | Notes |
|------------|------|--------|
| Entity filter | `GET /masters/entities` | [`EntityFilter.jsx`](../../apps/frontend/src/components/filters/EntityFilter.jsx) |
| Department filter | `GET /masters/departments` | Params include entity |
| Cost center filter | `GET /masters/cost-centers` | Params include entity |

## CFO command center

| UI surface | HTTP | Notes |
|------------|------|--------|
| CFO Cockpit body | `GET /dashboard/cfo` | Params: `useDashboardFilterParams` (entity, period, dept, cost center) |
| KPI catalog | `GET /kpi/definitions` | CFO + KPI drill |
| CFO hero band | `GET /kpi/cfo-summary` | Fallback hero tiles coded in `CFOCockpit.jsx` |
| Action queue strip | `GET /cfo/action-queue?refresh=true&limit=6` | Refresh materialized items |
| Run all controls | `POST /controls/run-all` | Toast with run counts |
| Audit committee pack | `GET /reports/audit-committee-pack.{fmt}` | `fmt` = `pdf` \| `pptx`; blob download |
| Approve / escalate (inline) | `POST /cfo/action/:id/approve` · `POST /cfo/action/:id/escalate` | From cockpit cards |

## KPI drill-down

| UI surface | HTTP |
|------------|------|
| Page | `GET /kpi/definitions`, `GET /kpi/trend/:kpiId`, `GET /kpi/drilldown/:kpiId` |

## Evidence & exceptions

| UI surface | HTTP |
|------------|------|
| Evidence explorer | `GET /exceptions`, `GET /exceptions/count` |

## Drill view

| UI surface | HTTP |
|------------|------|
| Generic drill | `GET /drill/:type/:id` |

## Representative workbenches (pattern: summary + list)

| Module page | Typical endpoints |
|-------------|---------------------|
| GL audit | `/gl/summary`, `/gl/accounts`, `/gl/transactions` |
| Journal risk | `/journals/risk-rules`, `/journals` |
| Three-way match | `/three-way-match/tolerances`, `/three-way-match/summary`, `/three-way-match/exceptions` |
| Vendor risk | `/vendor-risk/summary`, `/vendor-risk/vendors` |
| O2C | `/o2c/summary`, `/o2c/customers` |
| Credit notes | `/credit-notes/summary`, `/credit-notes` |
| Forex | `/forex/summary`, `/forex/exposures` |
| Treasury debt | `/treasury/summary`, `/treasury/debt` |
| Inventory | `/inventory-audit/summary`, `/inventory-audit/valuation-exceptions` |
| Fixed assets | `/fixed-assets-audit/summary`, `/fixed-assets-audit/assets` |
| Physical verification | `/physical-verification/:id/variance` (pattern) |
| Related party | `/rpt/audit-committee-report`, `/rpt/transactions` |
| Legal | `/legal/exposure-report`, `/legal/notices` |
| DoA | `/doa/matrix`, `/doa/rules`, `/doa/breaches` |
| Policy compliance | `/policies`, `/policies/attestations`, `/policies/breaches` |
| Access SoD | `/access/users`, `/access/roles`, `/access/sod-rules`, `/access/sod-conflicts`, `/access/dormant-users`, `/access/privileged-users` |
| Evidence intelligence | `/evidence-intelligence/quality-issues`, `/exceptions/count` |
| Continuous audit rules | `/continuous-audit/rules`, `/continuous-audit/exceptions`, `/continuous-audit/rule-performance` |
| Risk scoring | `/risk-intelligence/summary`, `/risk-intelligence/scores`, `/risk-intelligence/heatmap` |

## Admin / ingest

| UI surface | HTTP |
|------------|------|
| CSV upload | `POST /ingest/csv` (multipart) |

## Insights / AI panels

| UI surface | HTTP |
|------------|------|
| Insight panel sections | `GET /insights/:section` |

**Verification note:** If the UI shows indefinite loading, check browser network for 4xx/5xx on the endpoints above and correlate with backend logs.
