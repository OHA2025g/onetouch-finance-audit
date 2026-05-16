# OneTouch Audit AI — Product documentation pack

This folder contains **client-ready application documentation** generated per the live-led documentation plan. Documents are split for readability; together they map navigation, modules, workflows, data surfaces, QA, and training.

| File | Contents (template mapping) |
|------|-----------------------------|
| [00-environment-and-sources.md](./00-environment-and-sources.md) | Where to run the app, how auth aligns with seed users, verification method |
| [exploration-checklist.md](./exploration-checklist.md) | Route and navigation inventory with exploration status |
| [cross-check-api-surfaces.md](./cross-check-api-surfaces.md) | UI ↔ API mapping (Part 6 / implementation cross-check) |
| [part-01-executive-summary-navigation.md](./part-01-executive-summary-navigation.md) | Sections 1–3: Executive summary, login/access, navigation map |
| [part-02-module-documentation.md](./part-02-module-documentation.md) | Section 4: Module-wise deep documentation (overview, screens, condensed field/control notes) |
| [part-03-screens-drilldowns.md](./part-03-screens-drilldowns.md) | Section 4 (screen-level detail samples), drill-down catalogue |
| [part-04-workflows-roles.md](./part-04-workflows-roles.md) | Sections 5–6: E2E workflows, role-based access |
| [part-05-dictionaries-reports-data.md](./part-05-dictionaries-reports-data.md) | Sections 7–11, 14: KPI/chart/table/form/report catalogues, UI data dictionary |
| [part-06-ai-admin-rules-notifications.md](./part-06-ai-admin-rules-notifications.md) | Sections 12–16: AI, admin, business rules, notifications |
| [part-07-ux-qa-training-maturity.md](./part-07-ux-qa-training-maturity.md) | Sections 17–24: UX, gaps, roadmap, QA cases, training, maturity |

**Primary code references:** [`apps/frontend/src/App.js`](../../apps/frontend/src/App.js), [`apps/frontend/src/lib/routeConfig.jsx`](../../apps/frontend/src/lib/routeConfig.jsx), [`apps/backend/app/seed.py`](../../apps/backend/app/seed.py).

**Do not commit** production passwords or customer URLs into this repository. Staging URLs may be recorded in internal runbooks outside git.
