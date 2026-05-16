# Part 5 — KPI, chart, table, form, report & data dictionary

## 7. Dashboard & KPI dictionary

### CFO Cockpit (primary dashboard)

| Dashboard | Purpose | Target user | Key KPIs | Charts | Filters | Drill-downs |
|-----------|---------|-------------|----------|--------|---------|-------------|
| CFO Cockpit | Assurance & exposure | CFO | Hero band (6), heatmap | Line/area from payload | Masters + process | KPI slug, `drill_path`, links |

### KPI rows (hero band)

| KPI name | Meaning | Inferred formula / source | Unit | Target user | Action |
|----------|---------|----------------------------|------|---------------|--------|
| Audit readiness | Overall readiness index | From `/dashboard/cfo` + `/kpi/cfo-summary` | % | CFO | Improve controls / resolve exceptions |
| Unresolved exposure | High-risk monetary exposure | API field `unresolved_high_risk_exposure` | USD | CFO | Drill to open cases |
| High/critical cases | Open severity cases | Count | Count | CFO | Triage cases |
| Repeat findings | Recurrence of issues | Rate | % | CFO | Root-cause reviews |
| Evidence completeness | Documentation coverage | % | % | CFO | Request evidence |
| Remediation SLA | Timely remediation | % | % | CFO | Escalate overdue |

**Directionality:** Severity coloring in UI (`success` / `warning` / `critical`) per `CFOCockpit.jsx` hero useMemo.

---

## 8. Chart dictionary (CFO cockpit)

| Chart | Type | Data | Interpretation |
|-------|------|------|----------------|
| Trend charts | Line / area | `data` timeseries from CFO dashboard | Directional trend of exceptions/readiness |
| Heatmap | Custom `ReadinessHeatmap` | `data.heatmap` | Process × entity/status |

Other dashboards use Recharts or similar in their respective pages — **Partially Explored** without per-chart catalog.

---

## 9. Table dictionary (patterns)

| Table pattern | Example screens | Typical columns |
|---------------|-----------------|-----------------|
| Exception list | Evidence explorer | Severity, control, entity, dates |
| Action queue | CFO cockpit / queue page | Title, owner, due, actions |
| Workbench grids | GL, journals, vendor risk, etc. | Domain-specific IDs, amounts, status |
| Cases | Cases list | Case id, status, severity |

**Standard behaviors:** Pagination where implemented; sorting **Needs Clarification** per table; row click → detail or drill.

---

## 10. Form & field dictionary (high-touch)

| Form | Location | Purpose | Key fields | Submit |
|------|----------|---------|------------|--------|
| Login | `/login` | Auth | email, password | `login()` |
| New engagement | `/audit-planning/new` | Create engagement | Per `AuditEngagementNew.jsx` | `POST` engagement |
| CSV upload | `/upload` | Ingest | file | `POST /ingest/csv` |
| CARO generate | Report studio | Generate annexure | engagement scoped | `POST .../caro/generate` |
| BvA variance | Budget vs actual | Commentary | text | `POST /budget/variance/.../comment` |
| Governance | `/app/governance` | Retention / legal hold | Actor, toggles | Per page |

**Full field-level:** extract prop names during UAT from each `*Page.jsx`.

---

## 11. Reports & export documentation

| Report / export | Location | Format | Filters | API |
|-----------------|----------|--------|---------|-----|
| Audit committee pack | CFO Cockpit | PDF, PPTX | Masters params | `GET /reports/audit-committee-pack.{fmt}` blob |
| CFO export XLSX | CFO Cockpit | XLSX | UI handler | **Needs Clarification** — verify button wiring to backend |
| Engagement report preview | Report studio | HTML/PDF view | Engagement | `GET /audit-engagements/:id/report` |

**Missing recommended reports (idea backlog):** SOC bridge letter pack; data-lineage certification; customizable board pack wizard — **Assumption** product backlog.

---

## 14. UI-based data dictionary (partial)

| Entity | Field | Description | Type guess | Example | Screen |
|--------|-------|-------------|------------|---------|--------|
| User | email | Login id | string | `cfo@onetouch.ai` | Login |
| User | full_name | Display | string | Marion Acheson | Header |
| User | role | RBAC label | string | CFO | Auth payload |
| KPI | audit_readiness_pct | Readiness | number | 82 | CFO Cockpit |
| Exception | id | Exception key | string | EX-… | Evidence |
| Case | id | Case key | string | CASE-… | Cases |
| Engagement | id | UUID | string | from list | Audit planning |

Expand with each API response schema from OpenAPI or backend models when available.

---

*End of Part 5.*
