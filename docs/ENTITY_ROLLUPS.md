# Entity rollups — API & data contract

## Scope

Multi-entity governance rollups (organization → regions/legal entities → processes → cases) with extended KPIs, snapshot history, and chart payloads.

## Collections

| Collection | Purpose |
|------------|---------|
| `organization_hierarchy` | Org tree nodes (`type`: organization / region / legal_entity). |
| `rollup_snapshots` | Latest metrics per `node_id` (updated on recompute). |
| `rollup_snapshot_history` | Append-only history per recompute for sparklines / deltas. |

Indexes: see `app/db_indexes.py` (`rollup_snapshots.node_id`, `rollup_snapshot_history.node_id + as_of`).

## HTTP routes (`/api/rollups`)

| Method | Path | Notes |
|--------|------|--------|
| GET | `/summary`, `/hierarchy` | Returns `schema_version`, `metric_definitions`, `rollup_targets`, `boundaries`, `executive_framing`, `root` (+ `node`). |
| GET | `/drilldown?node_id=&process=` | Adds `selected_node_metrics`, `executive_framing`, envelope keys. |
| GET | `/snapshots/history?node_id=&limit=` | Ascending `series`, `sparklines`, `deltas_latest_pair`. |
| GET | `/chart/hierarchy?node_id=&metric=` | Treemap/bar payload: children `value`. |
| GET | `/chart/scatter?node_id=` | Leaf entities under node: readiness vs exposure. |
| POST | `/recompute` | Upserts `rollup_snapshots`, inserts `rollup_snapshot_history`. |

## Metrics

Core metrics remain backward compatible; extended keys include median ages, severity mixes, queue linkage, concentration HHI, recon-open proxy, etc. Definitions live in `app/services/rollup_metric_catalog.py`.

## Frontend

`/app/rollups` reads deep links `?node_id=` and `?rollup_process=` (maps to drilldown `process`). CFO cockpit shortcut preserves masters via `hrefWithMasterParams`.
