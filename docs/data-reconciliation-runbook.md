# Data reconciliation runbook (OneTouch Finance Audit AI)

This runbook explains how CFO / WC / treasury KPIs relate to **seed data** versus **connector-backed** feeds, and how to verify consistency after a sync.

## Sources of truth

| Surface | Primary API | Default data source | Notes |
|--------|-------------|---------------------|--------|
| CFO command center | `/dashboard/cfo`, `/kpi/*` | Seed + analytics aggregations | KPI drill-down uses the same scoped filters as masters. |
| Working capital | `/dashboard/working-capital`, `/working-capital/*` | Seed (`bank_transactions`, AR/AP proxies) | Phase 9–10 routes use dedicated WC slices where present. |
| Treasury | `/dashboard/treasury`, `/treasury/*` | Seed + treasury endpoints | 13-week cash uses `/treasury/forecast-13-week` contracts. |
| Budget vs actual | `/budget/vs-actual`, `/budget/variance` | `budget_versions` / synthesized variances | Uploaded budget `lines` are validated on POST `/budget/upload`. |
| Connectors | `/integrations/connectors`, `/integrations/connectors/{id}/sync` | `source_connectors` + `connector_runs` | Mock adapters record runs; use `/sync-logs` and per-connector `/health` for reconciliation. |

## Reconciliation checklist (post-sync)

1. Run **POST** `/integrations/connectors/{id}/sync` (or `/backfill`) and capture `run_id` from the response.
2. Open **GET** `/integrations/connectors/{id}/runs` and confirm `status` completed and error counts match expectations.
3. Pull **GET** `/integrations/connectors/sync-logs?limit=50` and align timestamps with ETL windows.
4. Cross-check a sampled KPI on the CFO dashboard against the underlying master collection (e.g. vendors, bank accounts) for the same `entity_code` and period.
5. For DQ findings, use **POST** `/master-data-quality/{finding_id}/create-case` so exceptions are traceable to remediation.

## When numbers disagree

- Confirm **entity scope** (`entity_code`) and **period** filters match between UI and API.
- If entity RBAC is enforced, verify the user’s `users.entity` aligns with the connector’s `config.entity_code`.
- Prefer connector run logs over cached dashboard responses when investigating stale KPIs.
