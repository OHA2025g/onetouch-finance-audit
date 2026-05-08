# One Touch Audit AI — Procedural + Explainer

This document is the “how to run it” + “how it works” guide for the One Touch Audit AI repo.

## What this project is

One Touch Audit AI is an AI-assisted audit platform with:

- **Backend**: FastAPI (Python) + MongoDB
- **Frontend**: React (Create React App) + Tailwind/UI components
- **Focus**: Continuous controls monitoring, exceptions/cases, drill-downs, governance workflows, and an AI copilot/insights layer that **degrades gracefully** when no LLM key is configured.

## High-level architecture (mental model)

- The **frontend** calls the **backend** over HTTP.
- The **backend** stores state in **MongoDB** and serves APIs under a `/api` prefix (see backend `app/main.py` composition referenced in the architecture doc).
- On startup, the backend can **seed synthetic demo data** (Phase 1 and Phase 2 packs) so the app is usable immediately.

## Repository layout (what lives where)

Top-level:

- `backend/`: FastAPI app + tests
- `frontend/`: React app
- `docker-compose.yml`: Dockerized run (Mongo + API + Nginx-served web)
- `LOCAL_SETUP.md`: local dev setup steps
- `memory/PRD.md`: living spec / product notes

Backend (key roles, summarized from `backend/DEVELOPER_ARCHITECTURE.md`):

- **Entry points**
  - `backend/server.py`: stable Uvicorn entry (`server:app`)
  - `backend/app/main.py`: creates FastAPI app, mounts routers under `/api`, configures middleware + lifecycle
- **HTTP layer**: `backend/app/routers/`
  - Validation, status codes, dependency wiring (`Depends`)
- **Domain orchestration**: `backend/app/services/`
- **Data access (incremental)**: `backend/app/repositories/`
- **Cross-cutting**: `backend/app/core/`, `backend/app/middleware/`, `backend/app/lifecycle.py`, `backend/app/deps.py`

Frontend (typical):

- `frontend/src/pages/`: page-level views (dashboards, cases, copilot, drill views)
- `frontend/src/lib/api.js`: API client helpers
- `frontend/src/lib/auth.jsx`: auth/session helpers
- `frontend/src/lib/theme.jsx`: theming (dark/light)
- `frontend/src/components/`: UI building blocks and panels

## Core user flows (what the app “does”)

These are the common end-to-end flows you’ll see when running the demo.

### Login → role-based experience

- Users log in (see demo credentials in `LOCAL_SETUP.md`).
- The frontend stores session/auth state and calls backend endpoints to authorize and fetch content.

### Dashboards → exceptions → cases

- Dashboards show KPIs/aggregations.
- Exceptions (anomalies/violations) can be reviewed and escalated into cases.
- Cases move through lifecycle states; sensitive ops should be audit-logged server-side.

### Drill-downs and evidence

- Drill views provide “why this happened” context using specific drill renderers on the frontend and supporting endpoints on the backend.

### Governance / retention / legal hold (controls around controls)

- Retention policies, legal holds, and WORM-like behaviors are implemented in backend services/routers (see architecture doc’s governance section).

### Copilot / AI insights

- The app includes a Copilot and per-section insights.
- If `EMERGENT_LLM_KEY` is not configured, AI features should **degrade gracefully** (fallback to heuristic behavior where implemented).

## Environment variables (source of truth)

### Backend (`backend/.env` for local dev)

From `LOCAL_SETUP.md`:

```
MONGO_URL=mongodb://localhost:27017
DB_NAME=onetouch_audit
CORS_ORIGINS=http://localhost:3000
EMERGENT_LLM_KEY=<optional>
```

Notes:

- **`EMERGENT_LLM_KEY`** is optional; keep it out of git and rotate if exposed.

### Frontend (`frontend/.env` for local dev)

From `LOCAL_SETUP.md`:

```
REACT_APP_BACKEND_URL=http://localhost:8001
WDS_SOCKET_PORT=0
```

Notes:

- CRA requires `REACT_APP_*` prefix for build-time env variables.

### Docker (`docker-compose.yml`)

Key settings (summarized):

- API service uses:
  - `MONGO_URL=mongodb://mongo:27017`
  - `DB_NAME=onetouch_audit`
  - `CORS_ORIGINS=*`
  - `JWT_SECRET=...` (demo secret in compose; change for real deployments)
  - `ENABLE_PHASE2=true`
  - `EMERGENT_LLM_KEY=` (optional)

## Procedures (step-by-step)

### Procedure A — Run locally (recommended for development)

#### 1) Start MongoDB

You can run MongoDB locally (native install) or via Docker. If using Docker just for Mongo:

```bash
docker run --name onetouch-mongo -p 27017:27017 -d mongo:7
```

#### 2) Backend setup + run

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install emergentintegrations --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

First boot behavior:

- Backend auto-seeds synthetic Phase 1 + Phase 2 demo data (see `LOCAL_SETUP.md`).

#### 3) Frontend setup + run

```bash
cd frontend
yarn install
yarn start
```

Open:

- Frontend: `http://localhost:3000`
- Backend (local): `http://localhost:8001`

#### 4) Demo login accounts

From `LOCAL_SETUP.md`:

- CFO: `cfo@onetouch.ai` / `demo1234`
- Controller: `controller@onetouch.ai` / `demo1234`
- Internal Auditor: `auditor@onetouch.ai` / `demo1234`
- Compliance: `compliance@onetouch.ai` / `demo1234`
- Process Owner: `owner@onetouch.ai` / `demo1234`
- External Auditor (read-only): `external.auditor@bigfour.example` / `demo1234`

### Procedure B — Run everything with Docker Compose (closest to “production-like” locally)

```bash
docker compose up --build
```

Services:

- `mongo`: MongoDB on `localhost:27017`
- `web`: Nginx-served frontend on `http://localhost:5715`
- `api`: backend service (internal to compose; exposed to `web` via reverse proxy/config)

If login appears to fail in Docker:

- Confirm the Nginx reverse-proxy is routing `/api` correctly (see `docker/nginx.conf`).

### Procedure C — Run backend tests

From `LOCAL_SETUP.md`:

```bash
cd backend
pytest
```

Testing notes (from backend architecture doc):

- Many tests run **without Mongo** (pure unit tests).
- Some integration tests may require a running API depending on configuration.

## Operational guidelines (how to work safely)

### Secrets and credentials

- Do not commit secrets (LLM keys, JWT secrets, vendor credentials).
- Prefer `.env` files locally and environment variables in deployments.
- If a secret is ever pasted into chat or committed, **revoke/rotate immediately**.

### API + router/service layering

Keep these boundaries:

- **Routers**: request/response models, validation, status codes, `Depends`, minimal logic
- **Services**: orchestration + domain rules
- **Repositories** (incrementally): centralize database access patterns as the codebase grows

### Error handling + request correlation

Backend includes correlation/error middleware so:

- Each request can get an `X-Request-ID`
- Unexpected errors can return a 500 with `request_id` for support/debugging

## Troubleshooting playbook

### CORS issues in local dev

Symptoms:

- Browser blocks requests from `localhost:3000` → `localhost:8001`

Fix:

- Ensure backend `.env` has `CORS_ORIGINS=http://localhost:3000`
- Restart backend after changes

### Frontend is pointing to the wrong backend

Symptoms:

- Login works in one environment but not another

Fix:

- Local dev: set `frontend/.env` `REACT_APP_BACKEND_URL=http://localhost:8001`
- Docker: let Nginx route `/api` (compose build args/environment handle this)

### Mongo connection failures

Symptoms:

- Backend fails at startup with connection errors

Fix:

- Verify Mongo is running and `MONGO_URL` is correct:
  - local: `mongodb://localhost:27017`
  - docker compose: `mongodb://mongo:27017`

### “AI features not working”

Expected behavior:

- Without `EMERGENT_LLM_KEY`, AI features should degrade gracefully where implemented.

Fix:

- Provide `EMERGENT_LLM_KEY` via backend environment if you want full AI behavior.

## Glossary (project terms)

- **Control**: a continuous monitoring rule/check over process data
- **Exception**: a detected anomaly/violation that needs review
- **Case**: a managed investigation workflow created from exceptions or audit findings
- **Drill-down**: detailed view that explains or traces a KPI/exception
- **Governance**: policies/approvals/retention/legal hold around data and audit artifacts

