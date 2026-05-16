# One Touch Audit AI — Local Setup

## Prerequisites
- Python 3.11+
- Node.js 18+ with Yarn
- MongoDB 6+ running locally (or a cloud connection string)

## 1. Backend

```bash
cd apps/backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install emergentintegrations --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/
```

Create `apps/backend/.env`:
```
MONGO_URL=mongodb://localhost:27017
DB_NAME=onetouch_audit
CORS_ORIGINS=http://localhost:3000
EMERGENT_LLM_KEY=<optional — AI insights + copilot degrade gracefully to heuristic without it>
```

Start backend:
```bash
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

First boot auto-seeds Phase 1 + Phase 2 synthetic data (23 controls, 478+ exceptions,
15 collections for O2C/Payroll/Treasury/Tax/Fixed Assets).

## 2. Frontend

```bash
cd apps/frontend
yarn install
```

Create `apps/frontend/.env`:
```
REACT_APP_BACKEND_URL=http://localhost:8001
WDS_SOCKET_PORT=0
```

Start frontend:
```bash
yarn start
```

Open http://localhost:3000.

## 3. Demo login
- CFO: cfo@onetouch.ai / demo1234
- Controller: controller@onetouch.ai / demo1234
- Internal Auditor: auditor@onetouch.ai / demo1234
- Compliance: compliance@onetouch.ai / demo1234
- Process Owner: owner@onetouch.ai / demo1234
- External Auditor (read-only): external.auditor@bigfour.example / demo1234

## 4. Project layout (post-refactor)
```
apps/backend/
  server.py              # ~185 lines — FastAPI bootstrap + scheduler + startup seeds
  app/
    deps.py              # shared Mongo client + logger + audit_log helper
    auth.py              # JWT + bcrypt + get_current_user
    models.py            # Pydantic request/response models
    seed.py              # Phase 1 synthetic data + 12-control pack
    phase2.py            # Phase 2 synthetic data + 11-control pack
    controls_engine.py   # 12 runners
    controls_phase2.py   # 11 Phase 2 runners
    analytics.py         # Dashboard aggregations + evidence graph
    copilot.py           # RAG-based Copilot (Gemini 3 Flash)
    vector_store.py      # TF-IDF index
    anomaly.py           # IsolationForest + z-score
    training.py          # Anomaly training + model registry
    drill.py             # 14 drill types
    notifier.py          # SLA + Daily CFO Slack brief
    exports.py           # PDF / XLSX audit committee pack
    insights.py          # AI insight engine (heuristic + Gemini fallback)
    routers/             # Per-feature API routers:
      auth_router.py
      dashboards_router.py
      controls_router.py
      cases_router.py
      evidence_ai_router.py
      admin_router.py
  tests/                 # pytest regressions
apps/frontend/src/
  App.js
  index.css              # Dark + [data-theme="light"] overrides
  components/
    Layout.jsx           # Sidebar + topbar (theme toggle)
    InsightPanel.jsx     # AI insights per section
    StatCard.jsx / Badges.jsx
  lib/
    api.js / auth.jsx / theme.jsx / format.js
  pages/
    Login / CFOCockpit / ControllerDashboard / AuditWorkspace /
    ComplianceDashboard / MyCases / CasesList / CaseDetail /
    EvidenceExplorer / Copilot / AdminConsole / Upload / AuditorPortal /
    DrillView.jsx        # ~130 lines — thin dispatcher
    drill/               # 14 per-type renderers + shared.jsx
memory/
  PRD.md                 # Living spec + changelog
  test_credentials.md
```

## 5. What's inside
- 8 processes × 23 continuous controls (P2P, R2R, Access/SoD, O2C, Payroll, Treasury, Tax, Fixed Assets)
- 6 persona dashboards (CFO / Controller / Audit / Compliance / My Cases / External Auditor)
- 14 drill-down types with full lineage
- AI Copilot (Gemini 3 Flash + TF-IDF RAG)
- Isolation Forest anomaly model + training registry w/ approval workflow
- Per-section AI insight engine (7 dashboards)
- Global dark/light theme toggle
- SLA breach notifications + Daily CFO Slack brief
- PDF + XLSX audit committee pack export
- CSV ingestion for vendors/invoices
- Full audit logs + model + prompt registries

## 6. Run tests
```bash
cd apps/backend && pytest
```

## 7. CA audit modules (API & UI)

After backend startup, if `audit_engagements` is empty, a demo engagement **`ENG-DEMO-IN-2025`** is inserted (materiality, two RACM risks, working paper folder + sample WP, and up to five existing cases linked with `engagement_id`).

**Frontend routes:** `/app/audit-planning`, `/app/audit-planning/new`, `/app/audit-planning/calendar`, `/app/audit-planning/engagements/:id`, `/app/audit-planning/engagements/:id/team`, `/app/ca-command-center`, `/app/audit-committee`.

**Cases API:** `GET /api/cases?engagement_id=ENG-DEMO-IN-2025` returns cases for that engagement; when materiality exists, each case may include `material_impact: true` if exception `financial_exposure` ≥ `final_materiality`.

**Routers:** `app/routers/ca_audit_engagements.py`, `app/routers/ca_audit_modules.py` (included from `app/main.py`). Schemas: `app/schemas/ca_audit.py`. Domain helpers: `app/services/ca_audit_domain.py`. Seed: `app/ca_audit_seed.py` (called from `app/lifecycle.py`).

**Force-reset CA data:** wipe Mongo collections listed under “CA statutory” in `app/seed.py` `COLLECTIONS`, or drop DB and restart so Phase 1 + CA seed run again.
