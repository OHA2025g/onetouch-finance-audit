# One Touch Audit AI — implementation report

This document tracks the enterprise hardening program and the modularization effort.

## Child prompt 1 — backend modularization (completed)

### Summary

- Replaced the monolithic `server.py` bootstrap with a thin re-export to `app.main:app` / `app.main.create_app()`.
- Moved startup and shutdown (seeding, scheduler, Mongo `client.close()`) to `app/lifecycle.py`. Global `AsyncIOScheduler` is assigned in `on_startup` for graceful shutdown.
- Introduced a **service layer** for case creation from exceptions: `app/services/case_service.py` (`case_from_exception`). The cases router imports this; `app.routers.cases_router.case_from_exception` remains a valid re-export for backward compatibility.
- **Core cross-cutting** modules under `app/core/`: `exceptions` (`ServiceError` + `register_exception_handlers` to attach `request_id` to JSON error bodies), `logging_config.configure_logging`, `pagination` (clamp + `PaginationParams`), `security.require_roles` for shared role `Depends` patterns.
- **Middleware**: `app/middleware/stack.py` — `CorrelationErrorMiddleware` (BaseHTTPMiddleware) sets `X-Request-ID` / `request.state.request_id`, returns 500 with `request_id` on unhandled errors, and delegates `RequestValidationError` to the standard handler. **CORS** is registered *after* correlation (last `add_middleware` = browser-facing **outer** layer, per Starlette).
- **Utilities**: `app/utils/timeutil.iso_utc` (DB-free) used by `case_service`; `app.deps.iso` is the same function via alias, preserving all existing call sites.
- **Repositories**: `app/repositories/` placeholder package for incremental extraction of data access.
- **Lazy imports**: `vector_store` (sklearn) and `anomaly` (numeric stack) are no longer imported at app startup from `lifecycle` or the copilot/vector endpoints; they load when those code paths run. `copilot.py` defers `vector_store` to `_retrieve_context`. This avoids pulling sklearn on `import app.main` when a compatible environment is used (e.g. Docker). Note: `app.copilot` still imports `emergentintegrations` at module import time (unchanged pre-requisite).

### Files added

| Path | Role |
|------|------|
| `backend/app/main.py` | `create_app()`, `app` export |
| `backend/app/lifecycle.py` | `on_startup`, `on_shutdown` |
| `backend/app/services/case_service.py` | `case_from_exception` |
| `backend/app/core/{exceptions,logging_config,pagination,security}.py` | Shared building blocks |
| `backend/app/middleware/stack.py` | Correlation + 500 handling |
| `backend/app/utils/timeutil.py` | UTC `iso_utc` |
| `backend/app/repositories/__init__.py` | Data-access home |
| `backend/DEVELOPER_ARCHITECTURE.md` | Module map |
| `backend/tests/test_core_pagination.py`, `test_case_service.py` | Unit tests |

### Files changed

- `backend/server.py` — thin re-export
- `backend/app/deps.py` — `iso` delegates to `iso_utc`
- `backend/app/routers/cases_router.py` — use `case_from_exception` from service
- `backend/app/routers/evidence_ai_router.py` — local imports for vector/anomaly
- `backend/app/copilot.py` — local `vector_store` in `_retrieve_context`
- `backend/app/lifecycle.py` — local imports for vector/anomaly

### Backward compatibility

- Uvicorn target remains **`server:app`**.
- All existing **HTTP routes and prefixes** (`/api/...`) unchanged in structure; response bodies for errors may now include an extra **`request_id`** field in addition to `detail`.
- `case_from_exception` importable from `app.routers.cases_router` as before.

### Known limitations / follow-ups

- **Child prompts 3–5** (connectors, embeddings + approval governance, mobile CFO) remain; see checklist.
- Routers still use `db` directly in many places; `repositories/**` is ready for incremental move.
- Local dev without `emergentintegrations` or with NumPy/sklearn version skew may still fail `import app.main`; use the Dockerized backend for full stack.

---

## Child prompt 2 — rollups, retention, legal hold, WORM (completed)

### Summary

- **Mongo collections** (also added to `COLLECTIONS` for `seed --force`): `organization_hierarchy`, `entity_group_map`, `reporting_currency_rates`, `rollup_snapshots`, `retention_policies`, `artifact_retention_map` (reserved), `purge_jobs`, `legal_holds`, `hold_artifact_links`, `worm_protected_records`.
- **Baseline seed** (`app/governance/ensure_baseline.py`): idempotent hierarchy (org → region → legal entity for US-HQ, UK-OPS, IN-SVC, SG-APAC), FX rates, default retention policies. Invoked from `on_startup` after `seed_database`.
- **Rollups** (`app/services/rollup_service.py`, `app/routers/rollups_router.py`): KPIs aligned with CFO metrics (readiness %, high-risk exposure, open critical cases, control failure rate, repeat finding rate, remediation SLA %, evidence completeness %) scoped by entity subtree; drill hierarchy → process → cases; `POST /rollups/recompute` persists `rollup_snapshots`; `GET /rollups/currency-rates`.
- **Retention** (`retention_service`, `retention_router`): policy CRUD, `GET /retention/eligible`, `POST /retention/run` with `dry_run` (live purge limited to **copilot_sessions** and **ingestion_runs** with `action=purge`; **audit_log** and **case** deletes are blocked in-app with explicit messages).
- **Legal hold** (`legal_hold_service`, `legal_holds_router`): create/list/detail/release/attach; `is_held` respects direct links, entity-wide, and global active holds; retention skips held cases when applicable.
- **WORM** (`worm_service`): on case close, upserts `worm_protected_records` for case + linked exception evidence; closed cases are treated as immutable; `PATCH /cases/{id}` and comments require `?force_override=true` for CFO/IA/Controller/Compliance roles with `audit_log` entry.
- **API responses**: `GET /cases/{id}` includes `governance`; `GET /evidence/{id}` adds optional `governance` on `EvidenceGraph` model.
- **Frontend**: `/app/rollups` (`EntityRollup.jsx`), `/app/governance` (`GovernanceConsole.jsx`), nav entries; **Case detail** and **Evidence explorer** show WORM / legal-hold badges when applicable.

### New routes (all under `/api`)

| Method | Path |
|--------|------|
| GET | `/rollups/summary`, `/rollups/hierarchy`, `/rollups/entity/{entity_id}`, `/rollups/drilldown`, `/rollups/currency-rates` |
| POST | `/rollups/recompute` |
| GET/POST/PUT | `/retention/policies`, `/retention/policies/{id}`, `/retention/eligible`, `/retention/run` |
| POST/GET | `/legal-holds/`, `/legal-holds`, `/legal-holds/{id}`, `/legal-holds/{id}/release`, `/legal-holds/{id}/attach-artifacts` |

### Tests

- `backend/tests/test_governance_child2.py` — hierarchy shape, entity filter helper, retention age helper.

### Known limitations

- No separate **business_unit** collection; drill at process level uses existing `cases.process`.
- **Currency conversion** on exposure is not applied in rollup metrics (rates stored for future use).
- **Global legal hold** blocks retention broadly by design when any active global hold exists.

---

*Append new phases below as they complete.*

---

## Child prompt 3 — connector framework + SAP/Oracle + data trust (completed)

### Summary

- Added **pluggable connector framework** under `backend/app/connectors/`:
  - Adapter interface: `BaseConnectorAdapter`
  - Registry: `connectors/registry.py` (currently wired to mock SAP + mock Oracle ERP)
  - Minimal schema validation: `connectors/validation.py`
- Added **connector orchestration + run monitoring** in `backend/app/services/connector_service.py`:
  - `source_connectors` CRUD
  - `connector_runs` (status, pulled/loaded, failures, schema validation report)
  - `connector_errors` (per-domain stage errors)
  - `connector_schemas` (expected schema + last validation summary)
  - Ingestion health endpoints: `/dq/health`, `/dq/schema-validations`
- Implemented **SAP + Oracle ERP mock adapters**:
  - `MockSapAdapter` supports: vendors, invoices, payments, journals, purchase_orders, goods_receipts
  - `MockOracleErpAdapter` supports: customers, employees, bank_transactions, fixed_assets, tax_records (and scaffolds schema for additional domains)
- Implemented **Admin APIs**:
  - `POST /connectors`, `GET /connectors`, `GET /connectors/{id}`
  - `POST /connectors/{id}/test`, `/sync`, `/backfill`
  - `GET /connectors/{id}/runs`, `/errors`, `/health`
  - `GET /dq/health`, `GET /dq/schema-validations`
- **Security**: connector credentials are stored as a **reference** (e.g. env var key) in `credentials_ref`; no raw secrets are persisted.
- **Frontend**: added `/app/connectors` (`ConnectorsConsole.jsx`) with create/test/sync/backfill + run history/errors/schema validation + health view.

### Schema / collections

Added to the managed collection list in `seed.py`:

- `source_connectors`
- `connector_runs`
- `connector_errors`
- `connector_schemas`
- `connector_credentials_ref` (reserved; current UI uses `credentials_ref` inline)
- `tax_records` (for Oracle mock domain)

### Tests

- `backend/tests/test_connectors_child3.py` (schema validation + mock adapter smoke tests)

### Known limitations

- Real SAP/Oracle connectivity is **not** implemented yet; adapters are mock but conform to the interface so real adapters can be added without changing APIs.
- Incremental cursoring is scaffolded (`cursor` fields) but not persisted yet (cursor_out is stored per run; no resume logic yet).
- Domain normalization currently writes directly into existing collections via upsert by `id`. A future hardening pass can add staging/raw tables and lineage links into controls.

---

## Child prompt 4 — semantic embeddings + governance hardening (completed)

### Part A: Semantic embeddings upgrade

- Added `backend/app/embeddings/`:
  - `providers.py`: `EmbeddingProvider` interface + `HashEmbeddingProvider` deterministic fallback (no external credentials required).
  - `indexer.py`: corpus build (controls/exceptions/cases/policies), chunking, and rebuild into Mongo (`embedding_chunks`, `embedding_index_runs`).
  - `retrieval.py`: cosine similarity retrieval over stored vectors (bounded scan; replaceable later with a real vector index).
- Copilot retrieval (`backend/app/copilot.py`) now **prefers semantic embeddings** when `embedding_chunks` exists, and falls back to legacy TF‑IDF otherwise.
- Copilot admin endpoints:
  - `POST /copilot/rebuild-index` now rebuilds the **semantic** index (and is approval-gated).
  - `POST /copilot/reindex-scope` supports scoped rebuilds (`{"scope":{"entity":"US-HQ","process":"Treasury"}}`).
  - `GET /copilot/index-status` returns semantic index status (chunks + last run).
  - `GET /copilot/retrieval-configs` lists `retrieval_config_versions` (storage scaffold).

### Part B: Governance hardening (approvals)

- Added governance policy + approval workflow:
  - Collections: `approval_requests`, `approval_decisions`, `governance_policy_versions`.
  - `backend/app/services/governance_approval_service.py`:
    - policy singleton (`requires_approval` matrix)
    - create/list approval requests
    - approve/reject decisions
    - `require_approval_or_raise()` guard used by sensitive routes
  - `backend/app/routers/governance_router.py`:
    - `GET/POST /governance/policies`
    - `GET /governance/approvals`
    - `POST /governance/approvals`
    - `POST /governance/approvals/{id}/approve|reject`
- Enforcement added:
  - Connector activation via `POST /connectors/{id}/activate` requires approval (`connector_activation`)
  - Retention policy create/update requires approval (`retention_policy_change`)
  - Legal hold release requires approval (`legal_hold_release`)
  - Copilot semantic index rebuild/reindex requires approval (`copilot_rebuild_index`)

### Frontend

- Added `/app/approvals` (`ApprovalsQueue.jsx`) to view and approve/reject requests.

### Tests

- `backend/tests/test_embeddings_child4.py` (deterministic embedding + cosine sanity).

### Known limitations

- The current semantic provider is a deterministic **hash** embedding fallback; it is designed to enable governed indexing and retrieval flows now, and be replaced by a real embedding provider later without changing APIs.

---

## Child prompt 5 — mobile CFO cockpit + final QA + docs (completed)

### Mobile-responsive CFO cockpit

- Updated `frontend/src/pages/CFOCockpit.jsx` to be mobile-usable:
  - Header actions wrap on small screens
  - Added **mobile filter drawer** (entity + process) and desktop filter controls
  - Heatmap and top risks now respect filters
  - Top risks renders as a **touch-friendly list** on mobile (table remains for desktop)

### Final QA / regression

- Backend unit suites for Child prompts 1–4 continue to pass.
- Some existing backend integration tests require `REACT_APP_BACKEND_URL` and container paths (e.g. `/app/frontend/.env`) and are intended to run inside the dockerized environment; they are not executed in this local-only pass.

### Final documentation

- `IMPLEMENTATION_PENDING_ITEMS_REPORT.md` and `PENDING_ITEMS_CHECKLIST.md` updated through Child prompt 5.
