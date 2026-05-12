# Budget & forecast API — SRS vs implemented paths

All routes are under the API prefix **`/api`**. Authenticated users must send **`Authorization: Bearer <token>`** unless noted.

## Budget vs actual

| SRS-style path | Implemented | Notes |
|----------------|---------------|--------|
| `GET /api/budget-vs-actual` | **Yes** — `GET /api/budget-vs-actual` | Alias router; same payload as below. |
| `GET /api/budget/budget-vs-actual` | **Yes** | Primary nested path; includes `as_of`, `data` (FPA dashboard). |
| `GET /api/budget/vs-actual` | **Yes** | Same analytics source; slightly different top-level keys. |

Query parameters supported on all three: `entity_code`, `period_ym`, `department_id`, `cost_center_id` (subject to entity-scope RBAC).

## Forecast vs actual

| SRS-style path | Implemented | Notes |
|----------------|---------------|--------|
| `GET /api/forecast-vs-actual` | **Yes** — `GET /api/forecast-vs-actual` | Alias router; delegates to `GET /api/forecast/vs-actual`. |
| `GET /api/forecast/vs-actual` | **Yes** | Canonical nested path. |

Query parameters: `entity_code`, `period_ym`.

## Related (unchanged) paths

- `GET /api/forecast/accuracy` — forecast accuracy / bias summary.
- `POST /api/forecast/upload`, `GET /api/forecast` — forecast versions.
- `POST /api/budget/upload`, `GET /api/budget`, `GET /api/budget/{id}`, variance routes — see OpenAPI export in CI artifact **`openapi-schema`**.

## Integrator guidance

1. Prefer **nested** paths (`/api/budget/...`, `/api/forecast/...`) for new clients.
2. Use **SRS top-level** aliases only when matching external specs; responses may include `canonical_paths` on the budget alias for discoverability.
3. CI contract tests assert both nested and SRS alias where applicable (`test_phase13_budget_vs_actual_l4_http.py`, `test_phase14_forecast_accuracy_l4_http.py`).
