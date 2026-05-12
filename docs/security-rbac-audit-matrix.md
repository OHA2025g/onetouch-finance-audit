# RBAC & audit logging matrix (critical mutations)

This matrix summarizes **role gates** (`require_roles` / `enforce_entity_scope` / service asserts) and whether **`audit_log`** is written for high-risk **POST** (and selected PATCH) operations. It is a review artifact, not a guarantee of completeness—extend when adding routes.

## Legend

- **RBAC**: FastAPI `Depends(require_roles(...))` or equivalent service enforcement.
- **Audit**: `await audit_log(actor, action, object_type, object_id, detail)` in the success path (or on mutation).

## Matrix

| Area | Route (method) | RBAC / scope | Audit action (representative) |
|------|----------------|--------------|--------------------------------|
| CFO actions | `POST /api/cfo/action/{id}/approve` | CFO-like roles | `cfo_action_approve` |
| CFO actions | `POST /api/cfo/action/{id}/reject` | CFO-like | `cfo_action_reject` |
| CFO actions | `POST /api/cfo/action/{id}/escalate` | CFO-like | `cfo_action_escalate` |
| CFO actions | `POST /api/cfo/action/{id}/comment` | CFO-like | `cfo_action_comment` |
| Close | `POST /api/close/cycles` | CFO / Controller / Super Admin | `close_cycle_create` |
| Close | `POST /api/close/tasks/.../submit` | CFO / Controller / Super Admin | `close_task_submit` |
| Close | `POST /api/close/tasks/.../approve` | CFO / Controller / Super Admin | `close_task_approve` |
| Close | `POST /api/close/signoff` | CFO / Controller / Super Admin | (see `close_router`) |
| Budget | `POST /api/budget/upload` | Authenticated + entity scope | `budget_upload` |
| Budget | `POST /api/budget/{id}/approve` | Authenticated + scope | `budget_approve` |
| Budget | `POST /api/budget/{id}/lock` | Authenticated + scope | `budget_lock` |
| Budget | `POST /api/budget/{id}/unlock` | Authenticated + scope | `budget_unlock` |
| Budget variance | `POST /api/budget/variance/{id}/comment` | Authenticated + scope | `budget_variance_comment` |
| Budget variance | `POST /api/budget/variance/{id}/approve-explanation` | Authenticated + scope | `budget_variance_approve_explanation` |
| Forecast | `POST /api/forecast/upload` | Authenticated + scope | `forecast_upload` |
| Forecast | `POST /api/forecast/variance/{id}/comment` | Authenticated + scope | `forecast_variance_comment` |
| Reconciliations | `POST /api/reconciliations` | Authenticated | `reconciliation_create` |
| Reconciliations | `POST /api/reconciliations/{id}/submit` | Authenticated | `reconciliation_submit` |
| Reconciliations | `POST /api/reconciliations/{id}/approve` | Authenticated | `reconciliation_approve` |
| Reconciliations | `POST /api/reconciliations/{id}/reopen` | Authenticated | `reconciliation_reopen` |
| Reconciliations | `POST /api/reconciliations/{id}/create-case` | Authenticated | `reconciliation_create_case` |
| Cases | `POST /api/cases` | Authenticated | `create_case` |
| Cases | `PATCH /api/cases/{id}` | Authenticated | `update_case` |
| Copilot | `POST /api/copilot/ask` | Authenticated + rate limit | `copilot_ask` |
| Copilot | `POST /api/copilot/rebuild-index` | Authenticated + governance approval | `rebuild_index` |
| System | `POST /api/system/security-config` | Super Admin | `security_config_update` |
| System | `POST /api/system/org-backfill/run` | Super Admin | `org_backfill_run` |
| Reports | `POST /api/reports/generate` | CFO / audit roles | `report_generate` |
| Reports | `POST /api/reports/{id}/signoff` | CFO / Super Admin | `report_signoff` |
| Continuous audit | `POST /api/continuous-audit/rules` | Authenticated | `continuous_audit_rule_create` |
| Continuous audit | `PATCH /api/continuous-audit/rules/{id}` | Authenticated | `continuous_audit_rule_update` |
| Continuous audit | `POST /api/continuous-audit/rules/{id}/run` | Authenticated | `continuous_audit_rule_run` |
| Continuous audit | `POST /api/continuous-audit/exceptions/{id}/case` | Authenticated | `continuous_audit_exception_case_create` |
| GL | `POST /api/gl/signoff` | Authenticated | `gl_signoff` |
| Masters | `POST /api/masters/{type}` | Role-gated in router | `master_*` (see `masters_router`) |

## Gaps / follow-ups

- Any **new POST/PATCH/DELETE** should add a row here and register the `action_type` in `app/core/audit_actions.py` when using `AUDIT_ACTION_STRICT=1`.
- **Entity scope**: enforced via `rbac_service.enforce_entity_scope` on many finance routes; verify new routers call it before writes.
- **Read paths** (GET) generally do not emit audit logs unless security-sensitive (e.g. bulk export).

## CI

L4 HTTP tests (`tests/test_phase*_l4_http.py`) exercise auth + happy-path contracts when **`REACT_APP_BACKEND_URL`** is set (see `docker-compose.yml` `api` service and `tests/l4_http_common.py` for local `.env` resolution).
