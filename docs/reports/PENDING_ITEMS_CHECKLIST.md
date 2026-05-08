# Pending items — enterprise program checklist

Legend: [x] done, [~] partial / scaffolded, [ ] not started.

## Child prompt 1 — backend modularization

- [x] App factory, thin `server.py`, lifecycle, services/core/middleware, docs, unit tests

## Child prompt 2 — rollups, retention, legal hold, WORM

- [x] Organizational hierarchy + `entity_group_map` + FX rates baseline
- [x] Rollup metrics + drilldown + snapshots + `/rollups/*` APIs
- [~] Full drill path “BU” as distinct level (process used as proxy)
- [~] Currency conversion on rolled-up exposure (rates present; conversion not applied)
- [x] Retention policies + eligible scan + purge job (dry-run + limited live delete)
- [x] Legal holds + links + release + attach APIs
- [x] WORM records + closed-case immutability + override audit
- [x] UI: rollups page, governance console, case/evidence badges
- [x] Tests: `test_governance_child2.py`

## Child prompts 3–5 (remaining)

- [x] Connector framework + SAP/Oracle adapters (mock) + data trust UI/APIs
- [x] Semantic embeddings + hybrid retrieval (fallback) + copilot index admin endpoints
- [x] Governance approvals (connector activation, retention policy change, legal-hold release, copilot reindex)
- [x] Mobile-responsive CFO cockpit
- [~] Final E2E regression pass + polish (unit tests pass; integration tests require env/containers)

## Global backlog (from master spec)

- [~] Multi-entity rollups (implemented core; extend BU + FX on exposure as needed)
- [~] Retention engine (policies + job; case/audit purge out-of-band by design)
- [x] Legal hold enforcement (API + purge skip + UI flags)
- [x] WORM for closed cases / evidence (with override path)
- [ ] External ERP connectors (SAP, Oracle) + monitoring + schema validation + lineage
- [x] Connector run monitoring + schema validation + ingestion health visibility (via `/dq/*` + connectors UI)
- [ ] Semantic copilot retrieval upgrade
- [ ] Governance hardening (approval workflows beyond WORM override)
- [ ] Data trust (ingestion health, schema validation, lineage) — partial overlap with Child 3
- [ ] Mobile CFO cockpit

## Documentation

- [x] `IMPLEMENTATION_PENDING_ITEMS_REPORT.md`
- [x] `PENDING_ITEMS_CHECKLIST.md`
