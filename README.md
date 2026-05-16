# One Touch Audit

AI-assisted audit platform: FastAPI backend and React frontend. See `docs/setup/LOCAL_SETUP.md` for development setup.

Repository: [OHA2025g/onetouch-audit](https://github.com/OHA2025g/onetouch-audit).

## CA-grade audit modules (added)

The platform keeps all existing modules and routes. New **audit engagement** data is the parent for statutory / internal audit workflows.

### Backend (MongoDB collections, prefix `ca_` + `audit_engagements`)

| Area | Collections / notes |
|------|------------------------|
| Engagement & planning | `audit_engagements` (milestones, team, planning notes embedded) |
| Materiality | `ca_materiality` |
| RACM | `ca_risks`, `ca_risk_control_map` |
| Financial statement audit | `ca_trial_balance`, `ca_trial_balance_lines`, `ca_fs_snapshots`, `ca_audit_adjustments` |
| Schedule audit | `ca_schedule_audit` |
| IFC & control testing | `ca_control_library`, `ca_control_tests`, `ca_control_deficiencies`, `ca_control_certifications` |
| Working papers | `ca_wp_folders`, `ca_working_papers`, `ca_wp_review_notes`, `ca_wp_signoffs`, `ca_sampling_plans`, `ca_sample_transactions`, `ca_vouching_items` |
| India compliance | `ca_compliance_results`, `ca_gst_rec`, `ca_tds_rec`, `ca_caro_state`, `ca_tax44_state`, `ca_caro_responses` |
| Reporting | `ca_audit_observations`, `ca_audit_opinions`, `ca_final_reports`, `ca_management_letters`, `ca_mgmt_repr` |

### Key API groups (all under `/api`)

- **Engagements:** `POST/GET/PUT/DELETE /audit-engagements`, `POST .../milestones`, `POST .../team`, `POST .../planning-notes`, `GET .../summary`
- **Materiality:** `POST/GET .../materiality`, `PUT /materiality/{id}`, `POST /materiality/{id}/approve`
- **RACM:** `POST/GET .../risks`, `GET/PUT/DELETE /risks/{id}`, `POST .../controls`, `POST .../procedures`, `GET .../risk-heatmap`, `GET .../risks/export.xlsx`
- **FS:** trial balance upload (row-level validation; empty `account_code` rows skipped), `POST .../financial-statements/generate`, `GET .../financial-statements/latest` (snapshot + `validation` + `issues`), balance sheet / P&amp;L / cash flow, audit adjustments
- **Schedules:** `GET .../schedules/{assets|revenue|expenses|inventory|liabilities}`, conclusions &amp; exceptions
- **IFC:** `/control-library`, engagement control tests &amp; deficiencies
- **Working papers:** folders, CRUD, sampling, vouching, review notes, sign-offs
- **Compliance:** `/compliance/library`, `POST .../compliance/checklist` (rows from India template: Companies Act, IT Act, GST, TDS, CARO, 44AB-style), GST/TDS/CARO/44AB tools, compliance calendar
- **Reporting:** observations, opinion, CARO, final report, management letter
- **Executive / CFO (per engagement):** `GET .../ca-dashboard` (tiles, six-pillar continuous assurance scores, integration map, rule-based advisory bundle, workflow deep links), `GET .../executive-summary` (headline, scores, integration + advisory preview), `GET .../audit-committee-pack` (pack JSON + compliance snapshot + materiality snapshot), `GET .../continuous-assurance-score` (overall + `components` for audit readiness, control effectiveness, compliance, evidence completeness, fraud risk, FS risk), `GET .../advisory-insights` (key risks, control improvements, cost optimization, management letter draft, findings in CFO language), legacy `.../ca-command-center` tiles, `.../management-action-summary`

### Frontend routes

| Route | Purpose |
|-------|---------|
| `/app/audit` | **Audit workspace** (Finance Operations) — 23-rule control testing, KPIs, trends, batch run, scoped exceptions (not IFC engagement control library) |
| `/app/audit-planning` | Engagement list |
| `/app/audit-planning/new` | Create engagement |
| `/app/audit-planning/engagements/:engagementId` | Engagement hub (`?tab=` for deep link, e.g. `wp`, `financial`); Evidence graph **working paper** nodes open here with `?tab=wp` |
| `/app/audit-planning/engagements/:engagementId/team` | Team assignment |
| `/app/audit-planning/calendar` | Milestones across engagements |
| `/app/ca-command-center` | CA command center: prefers `ca-dashboard` API; fallback `ca-command-center`; `?engagement_id=` |
| `/app/audit-committee` | CFO / audit committee dashboard: executive summary + committee pack preview + engagement selector |
| `/app/executive-review` | CFO & committee hub: tabs for summary, continuous assurance, committee pack, management letter generator, advisory AI (`?engagement_id=`, `?tab=`) |

Sidebar groups: **Planning**, **Risk & controls**, **Financial audit**, **Compliance**, **Working papers**, **Reporting**, **Executive review** (CFO hub, continuous assurance tab, cockpit, committee, CA command center), **Operations** (legacy modules unchanged).

### Demo workflow

1. Start backend — first boot runs Phase 1 seed; CA demo is added when `audit_engagements` is empty (`ENG-DEMO-IN-2025` + materiality + RACM + linked cases + demo WP linked to cases + seeded compliance checklist).
2. Log in as `auditor@onetouch.ai` / `demo1234`.
3. Open **Audit Planning** → open `ENG-DEMO-IN-2025` → walk tabs (materiality, RACM export, compliance checklist, reporting generators).
4. **Cases** with materiality: `/app/cases?engagement_id=ENG-DEMO-IN-2025` shows **Material impact** when exposure ≥ approved materiality.
5. **AI Copilot** includes prompts for RACM / management letter style questions; embeddings indexer includes engagements, risks, and working papers when rebuilt.
6. **Evidence explorer:** for exceptions with a case on an engagement, the graph can include **working paper** nodes; click through to the engagement hub **Working papers** tab (`?tab=wp`).

### E2E smoke tests (Playwright)

Frontend includes a small Playwright suite for engagement deep links.

- Recommended Node: **22 LTS** (see `apps/frontend/.nvmrc`). CRA (`react-scripts`) and Playwright can behave unpredictably on very new Node versions.
- Install deps: `cd apps/frontend && yarn install`
- Install browsers: `cd apps/frontend && npx playwright install`
- Run (requires running frontend + backend): `cd apps/frontend && PLAYWRIGHT_BASE_URL=http://localhost:3000 yarn e2e`

Notes:
- The app must be able to reach the backend for login (`/api/auth/login`). If you run frontend separately, set `REACT_APP_BACKEND_URL` appropriately before `yarn start`.
