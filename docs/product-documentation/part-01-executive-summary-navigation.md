# Part 1 — Executive summary, login & access, navigation map

## 1. Executive summary

### Narrative

**OneTouch Audit AI** is a web application for **finance control and audit assurance**: continuous monitoring of controls, evidence-backed exceptions, CFO dashboards, treasury and working-capital analytics, compliance and risk-intelligence workbenches, statutory (India) audit tracks, and engagement lifecycle tooling (planning, RACM, working papers, report studio). Primary users are **CFOs and finance leadership**, **controllers**, **internal and external auditors**, **compliance**, **process owners**, and **platform super administrators**. The UI is a React single-page app with role-scoped navigation; the backend exposes REST APIs consumed under `/api`.

**Main modules** align with sidebar groups: CFO Command Center, Finance Operations, Financial Audit, Continuous Audit, Working Capital, Treasury, Compliance, Risk Intelligence, Evidence & Cases, Board Reporting, AI Copilot, Integrations / Enterprise hardening, Admin, and deep **Audit planning** trees (engagements, IFC, India compliance, report studio).

**Workflows** span monitoring (dashboards → drill-downs → lists), remediation (cases, action queue approvals), close and FP&A cycles, audit engagement documentation, and exports (e.g. audit committee pack).

**Strengths (architecture):** Broad route coverage for phased delivery; explicit drill path builders; masters-based scoping on many dashboards; Playwright E2E coverage per phase.

**Limitations / risks:** Full depth of every control was not exercised in a single live session; CFO cockpit depended on `/dashboard/cfo` responsiveness during verification. Some hubs are **module maps** (`ModuleHubPage`) rather than full analytical pages. Optional LLM features may degrade when API keys are unset.

**Maturity (high level):** Strong **navigation and route completeness** for a multi-phase product; **client-readiness** depends on deployment configuration, seed data, and completing per-screen QA on customer environments.

### Summary table

| Item | Summary |
|------|---------|
| Application name | OneTouch Audit AI |
| Application type | B2E web SPA — finance audit & continuous controls assurance |
| Business domain | Audit readiness, controls monitoring, treasury/WC, compliance, risk, statutory reporting |
| Primary users | CFO; Controller; Internal/External Auditor; Compliance Head; Process Owner; Super Admin |
| Key modules | CFO cockpit & action queue; finance ops; financial & continuous audit workbenches; WC/treasury; compliance & risk; evidence/cases; board reporting; AI copilot; admin; audit planning |
| Key workflows | Login → role home; CFO KPI → drill or linked list; exception → evidence → drill entity; engagement → working papers → report studio; exports & approvals |
| Reporting capability | Audit committee pack (PDF/PPTX), board/report studio artefacts, many workbench summaries |
| AI / automation capability | Copilot workspaces, insights API, optional LLM (`EMERGENT_LLM_KEY`); rules engine & `run-all` controls |
| Overall maturity | Multi-phase surface coverage; per-customer hardening needed |
| Top strengths | Role-aware nav; deep audit planning; many L4 HTTP-tested backend domains |
| Top gaps | CFO cockpit load SLA on slow API; full manual matrix per role not completed in this pass |

---

## 2. Login and access review

| Area | Details |
|------|---------|
| Login page URL | `/login` (full URL = `{ORIGIN}/login`) |
| Login method | Email + password → `POST /api/auth/login` (see [`auth.jsx`](../../apps/frontend/src/lib/auth.jsx)) |
| Fields available | Email, password, show/hide password, theme toggle, quick-login persona tiles |
| Mandatory fields | Email and password (required for manual submit) |
| Validation messages | Toast error with server `detail` message or generic “Login failed” |
| Forgot password | **Not Applicable** (no control in `Login.jsx`) |
| Sign up | **Not Applicable** |
| Captcha / MFA | **Not Applicable** in current UI |
| Error handling | Non-2xx → toast; 401 clears token and redirects `/login` via axios interceptor |
| Successful login | Toast “Welcome, {full_name}”; navigate `roleToPath(role)` |
| Failed login | Toast error; remain on login |
| Landing after login | `/app` redirects to same `roleToPath` as direct success |
| Logout | **Yes** — header control; clears storage; `/` |
| User profile visible | **Yes** — name/email in header (Layout) |
| Role visible | **Assumption** — role shown if present on user object from `/auth/me` |
| Tenant / organization | **Partially** — entity masters scope filters; org name depends on API payload |

**Example success:** CFO persona quick-login → `/app/cfo`.  
**Example failure:** Wrong password → toast, stay on `/login`.

---

## 3. Complete navigation inventory and map

### 3.1 Checklist reference

See [exploration-checklist.md](./exploration-checklist.md) for the exhaustive **Item Type | Name | Location | Status | Notes** table and QA seed IDs.

### 3.2 Navigation map (Level 1–3)

| Level | Menu / area | Submenu / screen | URL / route | Purpose | User role | Notes |
|-------|-------------|------------------|-------------|---------|-----------|-------|
| 0 | Public | Landing | `/` | Marketing / entry | Unauthenticated | Redirect if logged in |
| 0 | Public | Login | `/login` | Authenticate | All | |
| 1 | CFO Command Center | CFO Cockpit | `/app/cfo` | Executive KPIs, heatmap, actions | CFO | API-heavy |
| 1 | CFO Command Center | Action queue | `/app/cfo-action-queue` | CFO approvals | CFO | |
| 1 | CFO Command Center | Readiness | `/app/readiness` | Process readiness matrix | CFO | |
| 1 | CFO Command Center | Controller dashboard | `/app/controller` | Operational finance view | CFO, Controller | |
| 1 | CFO Command Center | Entity rollups | `/app/rollups` | Consolidations | CFO, Super Admin | |
| 1 | CFO Command Center | Executive review | `/app/executive-review` | Committee / assurance hub | CFO, auditors | |
| 1 | Finance Operations | Month-end close | `/app/finance-operations/month-end-close` | Close cycles | CFO | |
| 1 | Finance Operations | Team performance | `/app/finance-operations/team-performance` | People metrics | CFO | |
| 1 | Finance Operations | Budget / BvA / Forecast | `/app/finance-operations/budget-master` (etc.) | FP&A control | CFO | Aliases exist |
| 1 | Finance Operations | FP&A snapshot | `/app/finance-operations/fpa` | Composite FP&A | CFO | |
| 1 | Finance Operations | Audit workspace | `/app/audit` | Controls/tests | CFO, auditors | |
| 1 | Financial Audit | Workbenches (GL, journals, recon, bank, inventory, physical, FA) | `/app/financial-audit/*` | Substantive & recon analytics | CFO | Dashboard + hub alias |
| 1 | Financial Audit | Audit planning | `/app/audit-planning` | Engagements | CFO, auditors | Deep subtree |
| 1 | Financial Audit | Evidence | `/app/evidence` | Exceptions explorer | CFO, auditors | |
| 1 | Continuous Audit | Rules, vendor, TWM, O2C, credit notes | `/app/continuous-audit/*` | Monitoring | CFO | |
| 1 | Working Capital | Dashboard / AR / AP / CCC | `/app/working-capital*` | Liquidity & DSO/DPO | CFO | |
| 1 | Treasury | Hub, cash forecast, debt, forex | `/app/treasury*` | Cash & risk | CFO | |
| 1 | Compliance | Dashboard + RPT + legal | `/app/compliance*` | Compliance analytics | CFO, Compliance | |
| 1 | Risk Intelligence | Hub + scoring + DoA + policy + SoD + MDQ | `/app/risk-intelligence*` | Risk analytics | CFO | |
| 1 | Evidence & Cases | My / all cases + intelligence | `/app/my-cases`, `/app/cases`, `/app/evidence*` | Workflow | Multiple | |
| 1 | Board Reporting | Committee + automation | `/app/audit-committee`, `/app/board-reporting*` | Governance packs | CFO | |
| 1 | AI Copilot | Copilot + 2.0 | `/app/copilot*` | Assisted analysis | CFO | |
| 1 | Integrations | Hub + connectors | `/app/integrations*`, `/app/connectors` | Data plumbing | CFO, Super Admin | |
| 1 | Enterprise | Hardening dashboard | `/app/enterprise-hardening*` | Platform resilience | Super Admin–oriented | |
| 1 | Admin | Console, security, health, logs, masters | `/app/admin*` | Configuration | Super Admin | |
| 1 | Super Admin | User management | `/app/super-admin` | Users | Super Admin | |
| 1 | Other | Governance, approvals, upload | `/app/governance`, `/app/approvals`, `/app/upload` | Policy ops | Super Admin / ops | |
| 2 | Audit planning | Engagement detail subtree | `/app/audit-planning/engagements/:id/...` | IFC, FS, schedules, papers, India, report studio | Auditors | Many nested routes |

### 3.3 Hierarchy (outline)

```
Application
├── Login
├── Landing
└── /app (authenticated)
    ├── Role default (cfo | super-admin | controller | audit | compliance | my-cases | auditor)
    ├── Module hubs (command centers)
    ├── CFO Cockpit + KPI drill (/app/kpi/:kpiId)
    ├── Finance ops + audit workspace
    ├── Financial audit workbenches + audit planning + evidence + drill/:type/:id
    ├── Continuous audit workbenches
    ├── Working capital + treasury
    ├── Compliance + risk intelligence
    ├── Cases + evidence intelligence + copilot
    ├── Board reporting + executive review
    ├── Integrations + enterprise hardening
    ├── Admin + super-admin + governance + approvals + upload
    └── Auditor shortcuts (fs-hub, schedule, ifc, …)
```

---

*End of Part 1.*
