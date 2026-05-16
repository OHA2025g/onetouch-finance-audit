# Part 4 — End-to-end workflows & role-based documentation

## 5. Workflow library

### Workflow 1: CFO morning assurance

| Step | Actor | Screen | Action | System response | Output |
|------|-------|--------|--------|-----------------|--------|
| 1 | CFO | Login | Sign in | JWT stored; redirect `/app/cfo` | Session |
| 2 | CFO | CFO Cockpit | Review hero KPIs | Loads `/dashboard/cfo`, `/kpi/cfo-summary` | KPI values |
| 3 | CFO | CFO Cockpit | Apply entity filter | Query params updated | Scoped dashboards |
| 4 | CFO | KPI drill | Click KPI | Navigate `/app/kpi/:id` | Trend + contributors |
| 5 | CFO | Drill row | Open related journal/case | Route per `pathForRelatedType` | Detail surface |
| 6 | CFO | Cockpit | Approve action queue item | `POST /cfo/action/:id/approve` | Item cleared / refreshed |

**Decision points:** If KPI below threshold → escalate or assign case (outside app **Needs Clarification** if not implemented).

**Exceptions:** API failure → error surface + toast; **Observed:** prolonged loading on `/dashboard/cfo` in automated run — treat as performance gap.

---

### Workflow 2: Exception to evidence to drill

| Step | Actor | Screen | Action | Result |
|------|-------|--------|--------|--------|
| 1 | Auditor | Evidence | Open `/app/evidence` | Exception list |
| 2 | Auditor | Evidence | Filter / paginate | `/exceptions` calls |
| 3 | Auditor | Row / graph | Open exception | `/app/evidence/:id` or graph drill |
| 4 | Auditor | Related | Navigate to invoice/vendor/etc. | `/app/drill/...` per type |

---

### Workflow 3: Audit engagement → working papers → report

| Step | Actor | Screen | Action |
|------|-------|--------|--------|
| 1 | Auditor | `/app/audit-planning` | Select engagement |
| 2 | Auditor | Engagement detail | Confirm scope, team |
| 3 | Auditor | `/.../working-papers` | Create / open paper |
| 4 | Auditor | Sampling / vouching routes | Execute procedures (UI-specific) |
| 5 | Auditor | `/.../report-studio/preview` | Generate preview (`GET .../report`) |

**Note:** Exact field validations live in each page component — capture during UAT.

---

### Workflow 4: Super Admin ingestion

| Step | Actor | Screen | Action | API |
|------|-------|--------|--------|-----|
| 1 | Super Admin | `/app/upload` | Choose CSV | `POST /ingest/csv` |
| 2 | Super Admin | `/app/admin/audit-logs` | Verify outcome | Log APIs |

---

### Workflow 5: Budget vs actual commentary

| Step | Actor | Screen | Action | API |
|------|-------|--------|--------|-----|
| 1 | CFO | BvA dashboard | Select variance | UI |
| 2 | CFO | Row action | Add comment / approve explanation | `POST /budget/variance/:id/comment`, `.../approve-explanation` |

---

## 6. Role-based deep documentation

### Role: CFO

| Module | Access | Allowed | Restricted |
|--------|--------|---------|------------|
| CFO Command Center | Full | KPIs, exports, run-all, approvals | Super-admin-only routes |
| Finance ops | Full (nav) | All linked screens | — |
| Admin | No | — | `/app/admin*`, `/app/super-admin` (Not Accessible unless role changed) |

**Daily journey:** Login → cockpit → filters → KPI drill or cases → export pack → logout.

---

### Role: Super Admin

| Module | Access |
|--------|--------|
| Admin & integrations nav | Users, admin console, master audit/DQ, integrations, connectors, approvals, upload |
| Platform | Rollups, governance |
| Command previews | Shortcut links into CFO/risk surfaces |

---

### Role: Internal / External Auditor & bundle

**Bundle roles:** External Auditor, Internal Auditor, Controller, Compliance Head, Process Owner (`AUDITOR_BUNDLE` in `routeConfig.jsx`).

- **Pinned first item** varies: Internal/External → Audit workspace; Controller → Controller; Compliance → Compliance; Process Owner → My cases.
- **Additional hubs:** CFO command center previews, financial audit hub, FS hub shortcuts, board reporting, evidence, AI, WC/treasury/risk hubs.

**Access caveats:** Route existence ≠ write permission — backend must enforce **Assumption** unless verified per endpoint.

---

### Role: Compliance Head

Landing `/app/compliance`; nav emphasizes compliance + IFC + India compliance shortcuts.

---

### Role: Process Owner

Landing `/app/my-cases`; operational case handling.

---

### Role: Controller

Landing `/app/controller`; overlaps with CFO nav for operational dashboards.

---

*End of Part 4.*
