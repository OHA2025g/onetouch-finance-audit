"""Multi-entity rollups, drilldown, and snapshot persistence."""
from __future__ import annotations
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from app.analytics import compute_readiness
from app.utils.timeutil import iso_utc


def _ent_filter(entity_codes: Optional[Set[str]]) -> Dict[str, Any]:
    if not entity_codes:
        return {}
    return {"entity": {"$in": list(entity_codes)}}


async def compute_rollup_metrics(
    db,
    entity_codes: Optional[Set[str]],
    process: Optional[str] = None,
) -> Dict[str, Any]:
    """Aggregate governance KPIs for a set of legal entity codes (None = all)."""
    ef = _ent_filter(entity_codes)
    exq: Dict[str, Any] = {**ef}
    if process:
        exq["process"] = process
    exq_open = {**exq, "status": {"$ne": "closed"}}

    high_exposure = 0.0
    async for e in db.exceptions.find(
        {**exq_open, "severity": {"$in": ["critical", "high"]}}, {"_id": 0, "financial_exposure": 1}
    ):
        high_exposure += float(e.get("financial_exposure", 0))

    cq: Dict[str, Any] = {**ef}
    if process:
        cq["process"] = process
    open_cases = await db.cases.count_documents({**cq, "status": {"$ne": "closed"}})
    crit_open = await db.cases.count_documents(
        {**cq, "status": {"$ne": "closed"}, "severity": "critical"}
    )

    procs: Set[str] = set()
    async for e in db.exceptions.find(exq, {"_id": 0, "process": 1}):
        procs.add(e.get("process", ""))
    if not procs:
        procs = {c["process"] async for c in db.controls.find({}, {"_id": 0, "process": 1})}
    passed = 0
    ran = 0
    for p in procs:
        if not p:
            continue
        passed += await db.controls.count_documents({"process": p, "last_run_pass": True})
        ran += await db.controls.count_documents({"process": p, "last_run_pass": {"$ne": None}})
    pass_rate = (passed / ran) if ran else 0.6
    control_failure_rate = round(1.0 - pass_rate, 4)

    per_control: Dict[str, int] = defaultdict(int)
    async for ex in db.exceptions.find(exq, {"_id": 0, "control_code": 1}):
        per_control[ex["control_code"]] += 1
    total_findings = sum(per_control.values()) or 1
    repeat = sum(v for v in per_control.values() if v > 1)
    repeat_finding_rate_pct = round(100.0 * repeat / total_findings, 1)

    total_ex = await db.exceptions.count_documents(exq)
    evidenced = await db.exceptions.count_documents({**exq, "status": "closed"})
    evidence_completeness_pct = round(100.0 * evidenced / total_ex, 1) if total_ex else 85.0

    sla_total = 0
    sla_met = 0
    async for ca in db.cases.find({**cq, "status": "closed", "closed_at": {"$ne": None}}, {"_id": 0}):
        try:
            opened = datetime.fromisoformat(ca["opened_at"])
            closed = datetime.fromisoformat(ca["closed_at"])
            sla_total += 1
            if (closed - opened).days <= 7:
                sla_met += 1
        except Exception:
            pass
    remediation_sla_pct = round(100.0 * sla_met / sla_total, 1) if sla_total else 92.5

    readiness_rows = await compute_readiness(db)
    if entity_codes:
        rows = [r for r in readiness_rows if r["entity"] in entity_codes]
    else:
        rows = readiness_rows
    if process:
        rows = [r for r in rows if r["process"] == process]
    audit_readiness_pct = (
        round(sum(r["readiness"] for r in rows) / max(1, len(rows)), 1) if rows else 0.0
    )

    return {
        "audit_readiness_pct": audit_readiness_pct,
        "unresolved_high_risk_exposure": round(high_exposure, 2),
        "open_critical_cases": crit_open,
        "open_cases": open_cases,
        "control_failure_rate": control_failure_rate,
        "repeat_finding_rate_pct": repeat_finding_rate_pct,
        "remediation_sla_pct": remediation_sla_pct,
        "evidence_completeness_pct": evidence_completeness_pct,
    }


async def get_hierarchy_tree(db) -> List[Dict[str, Any]]:
    return [n async for n in db.organization_hierarchy.find({}, {"_id": 0}).sort("path", 1)]


async def get_node(db, node_id: str) -> Optional[Dict[str, Any]]:
    n = await db.organization_hierarchy.find_one({"id": node_id}, {"_id": 0})
    if n:
        return n
    return await db.organization_hierarchy.find_one({"entity_code": node_id}, {"_id": 0})


def _descendant_entity_codes(nodes: List[Dict[str, Any]], root_id: str) -> Set[str]:
    by_parent: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for n in nodes:
        by_parent[n.get("parent_id") or ""].append(n)
    out: Set[str] = set()
    stack = [root_id]
    while stack:
        cur = stack.pop()
        for ch in by_parent.get(cur, []):
            stack.append(ch["id"])
            if ch.get("type") == "legal_entity" and ch.get("entity_code"):
                out.add(ch["entity_code"])
    return out


async def entity_codes_for_node(db, node_id: str) -> Set[str]:
    node = await get_node(db, node_id)
    if not node:
        return set()
    if node.get("type") == "legal_entity" and node.get("entity_code"):
        return {node["entity_code"]}
    tree = await get_hierarchy_tree(db)
    return _descendant_entity_codes(tree, node["id"])


async def list_children_for_parent(db, parent_id: str) -> List[Dict[str, Any]]:
    ch = [c async for c in db.organization_hierarchy.find({"parent_id": parent_id}, {"_id": 0}).sort("order", 1)]
    rows = []
    for n in ch:
        eids = await entity_codes_for_node(db, n["id"])
        m = await compute_rollup_metrics(db, eids if eids else set(), None)
        rows.append({"hierarchy": n, "entity_codes": sorted(eids), "metrics": m})
    return rows


async def rollup_summary(db) -> Dict[str, Any]:
    now = iso_utc(datetime.now(timezone.utc))
    root = await db.organization_hierarchy.find_one({"type": "organization"}, {"_id": 0})
    if not root:
        return {"as_of": now, "reporting_ccy": "USD", "error": "hierarchy not seeded", "metrics": {}}
    eids = await entity_codes_for_node(db, root["id"])
    metrics = await compute_rollup_metrics(db, eids if eids else None, None)
    children = await list_children_for_parent(db, root["id"])
    return {
        "as_of": now, "reporting_ccy": "USD", "node": root, "entity_codes": sorted(eids), "metrics": metrics, "children": children,
    }


async def rollup_hierarchy_with_metrics(db) -> Dict[str, Any]:
    return await rollup_summary(db)


async def get_entity_rollup(db, entity_id: str) -> Dict[str, Any]:
    n = await get_node(db, entity_id)
    if not n:
        return {"error": "not_found", "message": f"No hierarchy node for {entity_id}"}
    eids = await entity_codes_for_node(db, n["id"])
    m = await compute_rollup_metrics(db, eids, None)
    return {
        "hierarchy": n, "entity_codes": sorted(eids), "metrics": m, "as_of": iso_utc(datetime.now(timezone.utc)),
    }


async def drilldown(
    db,
    node_id: str,
    process_filter: Optional[str] = None,
) -> Dict[str, Any]:
    node = await get_node(db, node_id)
    if not node:
        return {"error": "not_found", "message": f"Node {node_id} not found"}
    eids = await entity_codes_for_node(db, node["id"])
    has_children = await db.organization_hierarchy.count_documents({"parent_id": node["id"]}) > 0

    if has_children and not process_filter:
        ch = await list_children_for_parent(db, node["id"])
        return {
            "node": node, "drill": "hierarchy", "rows": ch, "as_of": iso_utc(datetime.now(timezone.utc)),
        }

    exf = {**_ent_filter(eids if eids else None)}
    proc_set: Set[str] = set()
    async for c in db.cases.find(exf, {"_id": 0, "process": 1}):
        p = c.get("process")
        if p:
            proc_set.add(p)
    procs = sorted(proc_set)
    if not process_filter:
        proc_rows = []
        for p in procs:
            m = await compute_rollup_metrics(db, eids if eids else None, p)
            proc_rows.append({"process": p, "metrics": m})
        return {
            "node": node, "drill": "process", "rows": proc_rows, "as_of": iso_utc(datetime.now(timezone.utc)),
        }

    m = await compute_rollup_metrics(db, eids if eids else None, process_filter)
    case_q = {**exf, "process": process_filter}
    cases = [c async for c in db.cases.find(case_q, {"_id": 0}).sort("due_date", 1).limit(200)]
    return {
        "node": node, "drill": "case", "process": process_filter, "metrics": m, "cases": cases,
        "as_of": iso_utc(datetime.now(timezone.utc)),
    }


async def recompute_snapshots(db) -> Dict[str, Any]:
    now = iso_utc(datetime.now(timezone.utc))
    count = 0
    async for n in db.organization_hierarchy.find({}, {"_id": 0, "id": 1}):
        eids = await entity_codes_for_node(db, n["id"])
        m = await compute_rollup_metrics(db, eids if eids else None, None)
        await db.rollup_snapshots.update_one(
            {"node_id": n["id"]},
            {
                "$set": {
                    "id": n["id"] + "-snap", "node_id": n["id"], "as_of": now, "reporting_ccy": "USD",
                    "metrics": m, "version": 1,
                }
            },
            upsert=True,
        )
        count += 1
    return {"snapshots_upserted": count, "as_of": now}
