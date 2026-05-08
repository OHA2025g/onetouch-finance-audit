# Backend layout (One Touch Audit AI)

## Entry points

- **`server.py`**: Uvicorn compatibility shim (`from app.main import app`). Keeps the stable import path `server:app`.
- **`app/main.py`**: `create_app()` builds the FastAPI instance, registers exception handlers, composes middleware (correlation/500 **first**, CORS **second** so CORS is the browser-facing outer layer), mounts `/api` routers, and registers startup/shutdown from `app.lifecycle`.

## Package roles

| Area | Role |
|------|------|
| `app/routers/` | HTTP: validation, status codes, `Depends` wiring only. Call services or `db` today; prefer services + repositories as the codebase grows. |
| `app/services/` | Domain rules and orchestration (e.g. `case_service` builds case dicts for lifecycle and the cases router). |
| `app/repositories/` | **Incremental** data access. Centralize `find`/`update` patterns here to simplify testing. |
| `app/models/`, Pydantic in routers | API schemas. |
| `app/core/` | `exceptions` (e.g. `ServiceError` + `request_id` on JSON errors), `pagination`, `security` (`require_roles`), `logging_config`. |
| `app/middleware/` | `CorrelationErrorMiddleware` sets `X-Request-ID`, attaches `request.state.request_id`, maps unexpected exceptions to 500. |
| `app/lifecycle.py` | `on_startup` / `on_shutdown`: seeding, scheduler, Mongo client close. |
| `app/deps.py` | Global Mongo client, logger, `audit_log`, `iso` helper. |
| `app/jobs/`, `app/jobs/background` | (If present) scheduled/background work; APScheduler is currently started in lifecycle. |

## Conventions

- **Backward compatible imports**: `case_from_exception` remains importable as `app.routers.cases_router.case_from_exception` (re-exported via the service).
- **Governance / audit**: continue using `audit_log` for sensitive operations.
- **Error responses**: unhandled server errors return `500` with `request_id` when the correlation middleware can attach it. `ServiceError` and `HTTPException` add `request_id` to the JSON body via `register_exception_handlers` where applicable.

## Governance (Child prompt 2)

- **`app/governance/ensure_baseline.py`**: seeds hierarchy, FX, retention policies on startup when collections are empty.
- **`app/services/rollup_service.py`**: entity-scoped KPIs and drilldown; uses `compute_readiness` from `analytics`.
- **`app/services/retention_service.py`**: policy CRUD helpers, eligible scan, purge job (respects legal hold; blocks case/audit in-app delete).
- **`app/services/legal_hold_service.py`**: hold lifecycle + `is_held` checks.
- **`app/services/worm_service.py`**: WORM records; `require_case_mutable` for closed cases.
- **Routers**: `rollups_router`, `retention_router`, `legal_holds_router` (mounted in `app/main.py`).

## Testing

- `tests/test_core_*.py` and `test_case_service.py` run without a live server (no Mongo required for pure unit tests).
- `tests/test_governance_child2.py` — governance helpers without Mongo.
- `tests/test_refactor_regression.py` and similar integration tests require `REACT_APP_BACKEND_URL` to point at a running API.
