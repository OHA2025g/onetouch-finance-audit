# Environment and documentation sources

## Application identity

| Item | Value |
|------|--------|
| Application name | OneTouch Audit AI (branding on login: “Finance Control Command Center”) |
| Business domain | Continuous finance controls monitoring, audit readiness, statutory/IFC workflows, CFO assurance |
| Default local web entry | `http://localhost:5175` (Docker `web` service maps host `5175` → container `80`; see [`infra/docker-compose.yml`](../../infra/docker-compose.yml)) |
| Playwright default | `PLAYWRIGHT_BASE_URL` defaults to `http://localhost:5175` in [`apps/frontend/playwright.config.js`](../../apps/frontend/playwright.config.js) |
| API base (browser) | Relative `/api` when `REACT_APP_BACKEND_URL` is empty (nginx proxy in Docker); otherwise `${REACT_APP_BACKEND_URL}/api` per [`apps/frontend/src/lib/api.js`](../../apps/frontend/src/lib/api.js) |

## Seeded roles and accounts (local / demo)

Backend seed users are defined in [`apps/backend/app/seed.py`](../../apps/backend/app/seed.py) (`USERS_SEED`). Frontend navigation expects these **display role** strings (see [`apps/frontend/src/lib/routeConfig.jsx`](../../apps/frontend/src/lib/routeConfig.jsx) comments):

| Role | Example email (seed) |
|------|----------------------|
| Super Admin | `superadmin@onetouch.ai` |
| CFO | `cfo@onetouch.ai` |
| Controller | `controller@onetouch.ai` |
| Internal Auditor | `auditor@onetouch.ai` |
| Compliance Head | `compliance@onetouch.ai` (login quick-tile label may show “Compliance”; API returns role **Compliance Head**) |
| Process Owner | `owner@onetouch.ai` |
| External Auditor | `external.auditor@bigfour.example` |

**Credential policy for this documentation pack:** Do not store plaintext production passwords in markdown. For local demo verification, follow [`docs/setup/LOCAL_SETUP.md`](../setup/LOCAL_SETUP.md) (maintained project setup). Passwords for seeded demo users are documented there for **local development only**.

## Post-login landing (code contract)

[`roleToPath`](../../apps/frontend/src/App.js) determines the first screen after login when navigating to `/app` index:

| Role | Landing route |
|------|----------------|
| Super Admin | `/app/super-admin` |
| Controller | `/app/controller` |
| Internal Auditor | `/app/audit` |
| Compliance Head | `/app/compliance` |
| Process Owner | `/app/my-cases` |
| External Auditor | `/app/auditor` |
| CFO (default) | `/app/cfo` |

## How this pack was verified

| Method | Scope |
|--------|--------|
| Playwright E2E (subset) | `smoke.spec.js`, `cfo_kpi_drilldown.spec.js`, `cfo_command_center.spec.js` against `http://localhost:5175` — route shells and several CFO flows |
| Static analysis | Full route list from `App.js`, sidebar from `getSidebarNavGroups`, API usage from page components |
| Live observation | A running stack at `localhost:5175` returned HTTP 200 for `/login`; CFO cockpit **remained on “Loading command center…”** in failing smoke runs (API latency, version skew, or backend error — treat as **Partially Explored** until `/dashboard/cfo` responds within SLA) |

Re-run full verification after deployment upgrades:

```bash
cd apps/frontend && PLAYWRIGHT_BASE_URL=https://your-staging.example npx playwright test --reporter=list
```
