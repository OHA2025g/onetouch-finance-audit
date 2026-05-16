# Part 6 — AI, admin, business rules, notifications

## 12. AI, automation & insight

| AI feature | Location | Input | Output | Business value | Risk |
|------------|----------|-------|--------|----------------|------|
| Copilot workspace | `/app/copilot` | User prompts / context | Model-assisted text | Accelerates analysis | Hallucination — human review |
| Copilot 2.0 | `/app/copilot/copilot-2-dashboard` | Structured tasks | Dashboards/cards | Phase 37 surface | Same |
| Insight panel | CFO cockpit (`InsightPanel`) | Section key | `GET /insights/:section` | Narrative insights | Depends on backend quality |
| Run all controls | CFO cockpit | Button | `POST /controls/run-all` | Batch control evaluation | Load on systems |

**Governance checklist:** Link insight to source data where possible; capture feedback **Needs Clarification** in UI; confidence scores **Not observed** globally — mark gap if required for compliance.

---

## 13. Admin, settings & configuration

| Configuration area | Route | Purpose | Who |
|--------------------|-------|---------|-----|
| User management | `/app/super-admin` | CRUD users (UI-level) | Super Admin |
| Admin console | `/app/admin` | Org settings | Super Admin |
| Security | `/app/admin/security` | Security posture | Super Admin |
| System health | `/app/admin/system-health` | Ops status | Super Admin |
| Audit logs | `/app/admin/audit-logs` | Platform audit | Super Admin |
| Org backfill | `/app/admin/org-backfill` | Data repair | Super Admin |
| Master audit trail | `/app/admin/master-audit` | Master data changes | Super Admin |
| Master DQ | `/app/admin/master-dq` | DQ metrics | Super Admin |
| Governance | `/app/governance` | Retention / legal hold | Super Admin |
| Connectors | `/app/connectors` | Bank/ERP connectors | Super Admin / CFO |
| Approvals | `/app/approvals` | Approval queue | Super Admin |
| CSV ingest | `/app/upload` | File upload | Super Admin |

---

## 15. Business rules catalogue (sample — extend from code)

| Rule ID | Rule | Evidence | Impact |
|---------|------|----------|--------|
| BR-01 | CFO hero KPI severity colors | `CFOCockpit.jsx` hero useMemo | Visual triage |
| BR-02 | 401 clears session | `api.js` interceptor | Security |
| BR-03 | KPI drill maps `close_task` to MEC URL | `KpiDrilldownPage.jsx` | Correct navigation |
| BR-04 | SoD demo data in access router | backend `access_router.py` | Demo conflicts |

Mine additional rules from backend routers per compliance need.

---

## 16. Notification & alert catalogue

| Notification | Trigger | Channel | Location |
|----------------|---------|---------|----------|
| Login success | Successful auth | Toast (Sonner) | Top-right |
| Login failure | Bad creds | Toast | Top-right |
| CFO load failure | API error | Toast + `cfo-error` | Cockpit |
| Run-all result | POST completes | Toast with counts | Cockpit |
| Export success/fail | Blob download | Toast | Cockpit |
| KPI drill failure | API error | Toast + `kpi-drill-error` | KPI page |

Email/SMS **Not Applicable** in current UI inventory — **Gap** if required for enterprise.

---

*End of Part 6.*
