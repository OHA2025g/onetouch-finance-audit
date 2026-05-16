"""Multi-entity rollups, drilldown, and snapshot persistence."""
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from app.analytics import compute_readiness
from app.services.rollup_metric_catalog import (
    BOUNDARIES_COPY,
    DRILL_PATH_META,
    METRIC_DEFINITIONS,
    ROLLUP_SCHEMA_VERSION,
    ROLLUP_TARGETS,
)
from app.utils.timeutil import iso_utc

_CASE_SLA_FALLBACK_DAYS = {"critical": 3, "high": 7, "medium": 14, "low": 30}

# Functional currency aligned with finance seed (`bank_accounts.currency` mapping).
_ENTITY_FUNCTIONAL_CCY: Dict[str, str] = {
    "US-HQ": "USD",
    "UK-OPS": "GBP",
    "IN-SVC": "INR",
    "SG-APAC": "USD",
}

# USD value of one unit of quote currency when DB rates are missing (USD base convention).
_FALLBACK_USD_PER_UNIT: Dict[str, float] = {
    "USD": 1.0,
    "EUR": 0.92,
    "INR": 0.012,
    "SGD": 0.74,
    "GBP": 1.27,
}

DEFAULT_REPORTING_CCY = "USD"


def _rollup_envelope() -> Dict[str, Any]:
    return {
        "schema_version": ROLLUP_SCHEMA_VERSION,
        "metric_definitions": METRIC_DEFINITIONS,
        "rollup_targets": ROLLUP_TARGETS,
        "boundaries": BOUNDARIES_COPY,
        "drill_path": DRILL_PATH_META,
    }


def functional_currency_for_entity(entity_code: Optional[str]) -> str:
    if not entity_code:
        return "USD"
    return _ENTITY_FUNCTIONAL_CCY.get(str(entity_code), "USD")


def exposure_currency_for_exception(exc: Dict[str, Any]) -> str:
    for key in ("exposure_currency", "currency", "ccy"):
        v = exc.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip().upper()
    return functional_currency_for_entity(exc.get("entity"))


async def load_usd_per_unit_rates(db) -> Dict[str, float]:
    """USD value of one unit of quote currency (rates stored as base USD → quote)."""
    out: Dict[str, float] = dict(_FALLBACK_USD_PER_UNIT)
    try:
        cur = db.reporting_currency_rates.find({"base": "USD"}, {"_id": 0, "quote": 1, "rate": 1})
        async for doc in cur:
            q = doc.get("quote")
            if not q:
                continue
            try:
                out[str(q).upper()] = float(doc["rate"])
            except (TypeError, ValueError, KeyError):
                continue
    except Exception:
        pass
    out.setdefault("USD", 1.0)
    return out


def convert_amount_to_reporting_usd(amount: float, from_ccy: str, rates: Dict[str, float]) -> float:
    code = (from_ccy or "USD").strip().upper()
    mult = rates.get(code)
    if mult is None:
        mult = _FALLBACK_USD_PER_UNIT.get(code, 1.0)
    try:
        return float(amount) * float(mult)
    except (TypeError, ValueError):
        return 0.0


def _median_num(vals: List[float]) -> Optional[float]:
    if not vals:
        return None
    s = sorted(vals)
    n = len(s)
    mid = n // 2
    if n % 2:
        return float(s[mid])
    return (s[mid - 1] + s[mid]) / 2.0


def _parse_iso_dt(val: Optional[str]) -> Optional[datetime]:
    if not val or not isinstance(val, str):
        return None
    try:
        return datetime.fromisoformat(val.replace("Z", "+00:00"))
    except Exception:
        return None


def _case_is_past_due(case: Dict[str, Any], *, now: datetime) -> bool:
    due = _parse_iso_dt(case.get("due_date"))
    if due:
        return now > due.astimezone(timezone.utc) if due.tzinfo else now > due.replace(tzinfo=timezone.utc)
    op = _parse_iso_dt(case.get("opened_at"))
    if not op:
        return False
    if op.tzinfo is None:
        op = op.replace(tzinfo=timezone.utc)
    sev = str(case.get("severity") or "").lower()
    days = _CASE_SLA_FALLBACK_DAYS.get(sev, 14)
    return (now - op).days > days


def _merge_exec_metrics(rows: List[Dict[str, Any]]) -> Dict[str, float]:
    """Approximate combined exposure / readiness from child metric dicts (treemap parents)."""
    exp = 0.0
    read_vals: List[float] = []
    crit = 0
    for r in rows:
        m = r.get("metrics") or {}
        exp += float(m.get("unresolved_high_risk_exposure") or 0)
        if m.get("audit_readiness_pct") is not None:
            read_vals.append(float(m["audit_readiness_pct"]))
        crit += int(m.get("open_critical_cases") or 0)
    readiness = round(sum(read_vals) / max(1, len(read_vals)), 1) if read_vals else 0.0
    return {"exposure": exp, "readiness": readiness, "critical_cases": float(crit)}


def build_executive_framing(
    *,
    metrics: Dict[str, Any],
    reporting_ccy: str,
    worst_segments: Optional[List[Dict[str, Any]]] = None,
    node_name: Optional[str] = None,
) -> Dict[str, Any]:
    worst_segments = worst_segments or []
    readiness = float(metrics.get("audit_readiness_pct") or 0)
    exp = float(metrics.get("unresolved_high_risk_exposure") or 0)
    crit = int(metrics.get("open_critical_cases") or 0)
    label = node_name or "Rollup"
    headline = (
        f"{label}: {readiness:.1f}% readiness · {reporting_ccy} {exp:,.0f} high-severity exposure · "
        f"{crit} open critical cases."
    )
    worst_lines = []
    for seg in worst_segments[:3]:
        worst_lines.append(
            {
                "label": seg.get("name") or seg.get("process") or seg.get("label") or "?",
                "id": seg.get("id"),
                "exposure": seg.get("exposure"),
                "readiness": seg.get("readiness"),
                "kind": seg.get("kind"),
            }
        )
    return {"headline": headline, "worst_segments": worst_lines}


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
    rates = await load_usd_per_unit_rates(db)
    ef = _ent_filter(entity_codes)
    exq: Dict[str, Any] = {**ef}
    if process:
        exq["process"] = process
    exq_open = {**exq, "status": {"$ne": "closed"}}

    exposure_by_ent: Dict[str, float] = defaultdict(float)
    async for e in db.exceptions.find(
        {**exq_open, "severity": {"$in": ["critical", "high"]}},
        {"_id": 0, "financial_exposure": 1, "entity": 1, "exposure_currency": 1, "currency": 1, "ccy": 1},
    ):
        amt = float(e.get("financial_exposure") or 0)
        ccy = exposure_currency_for_exception(e)
        conv = convert_amount_to_reporting_usd(amt, ccy, rates)
        ent_key = str(e["entity"]) if e.get("entity") else "__unassigned__"
        exposure_by_ent[ent_key] += conv
    high_exposure = round(sum(exposure_by_ent.values()), 2)

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

    base_metrics = {
        "audit_readiness_pct": audit_readiness_pct,
        "unresolved_high_risk_exposure": round(high_exposure, 2),
        "exposure_reporting_ccy": DEFAULT_REPORTING_CCY,
        "open_critical_cases": crit_open,
        "open_cases": open_cases,
        "control_failure_rate": control_failure_rate,
        "repeat_finding_rate_pct": repeat_finding_rate_pct,
        "remediation_sla_pct": remediation_sla_pct,
        "evidence_completeness_pct": evidence_completeness_pct,
    }
    ext = await _rollup_extended_metrics(
        db,
        ef=ef,
        cq=cq,
        exq=exq,
        exq_open=exq_open,
        entity_codes=entity_codes,
        _process=process,
        exposure_by_ent_reporting=dict(exposure_by_ent),
    )
    base_metrics.update(ext)
    return base_metrics


async def _rollup_extended_metrics(
    db,
    *,
    ef: Dict[str, Any],
    cq: Dict[str, Any],
    exq: Dict[str, Any],
    exq_open: Dict[str, Any],
    entity_codes: Optional[Set[str]],
    _process: Optional[str],
    exposure_by_ent_reporting: Dict[str, float],
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    case_open_q = {**cq, "status": {"$ne": "closed"}}
    ages_case: List[float] = []
    past_due = 0
    n_open_cases_iter = 0
    sev_mix: Dict[str, int] = defaultdict(int)
    async for ca in db.cases.find(case_open_q, {"_id": 0, "opened_at": 1, "due_date": 1, "severity": 1}):
        n_open_cases_iter += 1
        sev = str(ca.get("severity") or "unknown").lower()
        sev_mix[sev] += 1
        op = _parse_iso_dt(ca.get("opened_at"))
        if op:
            if op.tzinfo is None:
                op = op.replace(tzinfo=timezone.utc)
            ages_case.append((now - op).total_seconds() / 86400.0)
        if _case_is_past_due(ca, now=now):
            past_due += 1
    median_open_case_age_days = (
        round(float(_median_num(ages_case) or 0.0), 1) if ages_case else None
    )
    pct_open_cases_past_due = (
        round(100.0 * past_due / max(1, n_open_cases_iter), 1) if n_open_cases_iter else 0.0
    )

    ages_ex: List[float] = []
    ex_sev_mix: Dict[str, int] = defaultdict(int)
    async for ex in db.exceptions.find(exq_open, {"_id": 0, "severity": 1, "detected_at": 1}):
        sv = str(ex.get("severity") or "unknown").lower()
        ex_sev_mix[sv] += 1
        dt = _parse_iso_dt(ex.get("detected_at"))
        if dt:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            ages_ex.append((now - dt).total_seconds() / 86400.0)
    median_open_exception_age_days = (
        round(float(_median_num(ages_ex) or 0.0), 1) if ages_ex else None
    )

    pc_open: Dict[str, int] = defaultdict(int)
    async for ex in db.exceptions.find(exq_open, {"_id": 0, "control_code": 1}):
        cc = ex.get("control_code")
        if cc:
            pc_open[str(cc)] += 1
    distinct_controls_with_open_exceptions = len(pc_open)
    top_repeat_control_codes = [
        {"control_code": k, "count": v}
        for k, v in sorted(pc_open.items(), key=lambda kv: -kv[1])
        if v > 1
    ][:5]

    b_le_7 = b_8_30 = b_gt_30 = 0
    async for ca in db.cases.find(
        {**cq, "status": "closed", "closed_at": {"$ne": None}}, {"_id": 0, "opened_at": 1, "closed_at": 1}
    ):
        op = _parse_iso_dt(ca.get("opened_at"))
        cl = _parse_iso_dt(ca.get("closed_at"))
        if not op or not cl:
            continue
        if op.tzinfo is None:
            op = op.replace(tzinfo=timezone.utc)
        if cl.tzinfo is None:
            cl = cl.replace(tzinfo=timezone.utc)
        days = max(0, (cl - op).days)
        if days <= 7:
            b_le_7 += 1
        elif days <= 30:
            b_8_30 += 1
        else:
            b_gt_30 += 1
    remediation_close_buckets = {"within_7d": b_le_7, "days_8_to_30": b_8_30, "over_30d": b_gt_30}

    assigned_exposure = {k: v for k, v in exposure_by_ent_reporting.items() if k != "__unassigned__"}
    total_exp = sum(assigned_exposure.values())
    top_entities_by_exposure = sorted(
        [{"entity_code": k, "exposure": round(v, 2)} for k, v in assigned_exposure.items()],
        key=lambda x: -x["exposure"],
    )[:8]
    if total_exp > 0:
        shares = [v / total_exp for v in assigned_exposure.values()]
        exposure_concentration_hhi = round(sum(s * s for s in shares), 4)
    else:
        exposure_concentration_hhi = 0.0

    aq_q: Dict[str, Any] = {"status": {"$nin": ["approved", "rejected"]}}
    if entity_codes:
        aq_q["entity"] = {"$in": list(entity_codes)}
    action_queue_open_count = await db.cfo_action_queue.count_documents(aq_q)
    aq_exp = 0.0
    async for doc in db.cfo_action_queue.find(aq_q, {"_id": 0, "detail": 1, "exposure": 1}):
        det = doc.get("detail") if isinstance(doc.get("detail"), dict) else {}
        v = det.get("exposure") if isinstance(det, dict) else None
        if v is None:
            v = det.get("financial_exposure") if isinstance(det, dict) else None
        if v is None:
            v = doc.get("exposure")
        if v is not None:
            try:
                aq_exp += float(v)
            except (TypeError, ValueError):
                pass

    close_readiness_items_open = await db.reconciliations.count_documents({**ef, "status": {"$ne": "closed"}})

    return {
        "median_open_case_age_days": median_open_case_age_days,
        "median_open_exception_age_days": median_open_exception_age_days,
        "pct_open_cases_past_due": pct_open_cases_past_due,
        "case_severity_mix": dict(sev_mix),
        "exception_severity_mix_open": dict(ex_sev_mix),
        "distinct_controls_with_open_exceptions": distinct_controls_with_open_exceptions,
        "top_repeat_control_codes": top_repeat_control_codes,
        "remediation_close_buckets": remediation_close_buckets,
        "exposure_concentration_hhi": exposure_concentration_hhi,
        "top_entities_by_exposure": top_entities_by_exposure,
        "action_queue_open_count": action_queue_open_count,
        "action_queue_open_exposure_usd": round(aq_exp, 2),
        "close_readiness_items_open": close_readiness_items_open,
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
        return {
            **_rollup_envelope(),
            "as_of": now,
            "reporting_ccy": "USD",
            "error": "hierarchy not seeded",
            "metrics": {},
            "children": [],
            "executive_framing": build_executive_framing(
                metrics={}, reporting_ccy="USD", node_name="Organization"
            ),
        }
    eids = await entity_codes_for_node(db, root["id"])
    metrics = await compute_rollup_metrics(db, eids if eids else None, None)
    children = await list_children_for_parent(db, root["id"])
    worst_src = [
        {
            "name": row["hierarchy"].get("name"),
            "id": row["hierarchy"].get("id"),
            "exposure": float((row.get("metrics") or {}).get("unresolved_high_risk_exposure") or 0),
            "readiness": float((row.get("metrics") or {}).get("audit_readiness_pct") or 0),
            "kind": row["hierarchy"].get("type") or "segment",
        }
        for row in children
    ]
    worst_src.sort(key=lambda x: -x["exposure"])
    framing = build_executive_framing(
        metrics=metrics,
        reporting_ccy="USD",
        worst_segments=worst_src,
        node_name=root.get("name"),
    )
    return {
        **_rollup_envelope(),
        "as_of": now,
        "reporting_ccy": "USD",
        "node": root,
        "root": root,
        "entity_codes": sorted(eids),
        "metrics": metrics,
        "children": children,
        "executive_framing": framing,
    }


async def rollup_summary_scoped_to_user_entity(db, user_entity: str) -> Dict[str, Any]:
    """Org rollup restricted to one legal entity (Phase 40 RBAC — entity_scope_enforced)."""
    now = iso_utc(datetime.now(timezone.utc))
    tree = await get_hierarchy_tree(db)
    node: Optional[Dict[str, Any]] = None
    for n in tree:
        if n.get("type") == "legal_entity" and n.get("entity_code") == user_entity:
            node = dict(n)
            break
    if not node:
        node = {
            "id": f"scoped-{user_entity}",
            "type": "legal_entity",
            "entity_code": user_entity,
            "name": user_entity,
        }
    eids: Set[str] = {user_entity}
    metrics = await compute_rollup_metrics(db, eids, None)
    root = await db.organization_hierarchy.find_one({"type": "organization"}, {"_id": 0})
    children_raw = await list_children_for_parent(db, root["id"]) if root else []
    filtered: List[Dict[str, Any]] = []
    for row in children_raw:
        ec = set(row.get("entity_codes") or [])
        if ec and ec.issubset({user_entity}):
            filtered.append(row)
    worst_src = [
        {
            "name": row["hierarchy"].get("name"),
            "id": row["hierarchy"].get("id"),
            "exposure": float((row.get("metrics") or {}).get("unresolved_high_risk_exposure") or 0),
            "readiness": float((row.get("metrics") or {}).get("audit_readiness_pct") or 0),
            "kind": row["hierarchy"].get("type") or "segment",
        }
        for row in filtered
    ]
    worst_src.sort(key=lambda x: -x["exposure"])
    framing = build_executive_framing(
        metrics=metrics,
        reporting_ccy="USD",
        worst_segments=worst_src,
        node_name=node.get("name"),
    )
    return {
        **_rollup_envelope(),
        "as_of": now,
        "reporting_ccy": "USD",
        "node": node,
        "root": node,
        "entity_codes": sorted(eids),
        "metrics": metrics,
        "children": filtered,
        "entity_scope_applied": True,
        "executive_framing": framing,
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
        **_rollup_envelope(),
        "hierarchy": n,
        "entity_codes": sorted(eids),
        "metrics": m,
        "as_of": iso_utc(datetime.now(timezone.utc)),
        "executive_framing": build_executive_framing(
            metrics=m, reporting_ccy="USD", worst_segments=[], node_name=n.get("name")
        ),
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
    node_metrics = await compute_rollup_metrics(db, eids if eids else None, process_filter)
    env = _rollup_envelope()
    has_children = await db.organization_hierarchy.count_documents({"parent_id": node["id"]}) > 0
    base_ts = iso_utc(datetime.now(timezone.utc))

    if has_children and not process_filter:
        ch = await list_children_for_parent(db, node["id"])
        worst_src = [
            {
                "name": row["hierarchy"].get("name"),
                "id": row["hierarchy"].get("id"),
                "exposure": float((row.get("metrics") or {}).get("unresolved_high_risk_exposure") or 0),
                "readiness": float((row.get("metrics") or {}).get("audit_readiness_pct") or 0),
                "kind": row["hierarchy"].get("type") or "segment",
            }
            for row in ch
        ]
        worst_src.sort(key=lambda x: -x["exposure"])
        framing = build_executive_framing(
            metrics=node_metrics,
            reporting_ccy="USD",
            worst_segments=worst_src,
            node_name=node.get("name"),
        )
        return {
            **env,
            "node": node,
            "drill": "hierarchy",
            "rows": ch,
            "selected_node_metrics": node_metrics,
            "executive_framing": framing,
            "as_of": base_ts,
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
        worst_src = [
            {
                "process": row["process"],
                "name": row["process"],
                "exposure": float((row.get("metrics") or {}).get("unresolved_high_risk_exposure") or 0),
                "readiness": float((row.get("metrics") or {}).get("audit_readiness_pct") or 0),
                "kind": "process",
            }
            for row in proc_rows
        ]
        worst_src.sort(key=lambda x: -x["exposure"])
        framing = build_executive_framing(
            metrics=node_metrics,
            reporting_ccy="USD",
            worst_segments=worst_src,
            node_name=node.get("name"),
        )
        return {
            **env,
            "node": node,
            "drill": "process",
            "rows": proc_rows,
            "selected_node_metrics": node_metrics,
            "executive_framing": framing,
            "as_of": base_ts,
        }

    m = await compute_rollup_metrics(db, eids if eids else None, process_filter)
    case_q = {**exf, "process": process_filter}
    cases = [c async for c in db.cases.find(case_q, {"_id": 0}).sort("due_date", 1).limit(200)]
    framing = build_executive_framing(
        metrics=m, reporting_ccy="USD", worst_segments=[], node_name=node.get("name")
    )
    return {
        **env,
        "node": node,
        "drill": "case",
        "process": process_filter,
        "metrics": m,
        "selected_node_metrics": m,
        "cases": cases,
        "executive_framing": framing,
        "as_of": base_ts,
    }


async def rollup_chart_hierarchy(
    db,
    node_id: str,
    metric_key: str = "unresolved_high_risk_exposure",
) -> Dict[str, Any]:
    node = await get_node(db, node_id)
    if not node:
        return {"error": "not_found", "message": f"Node {node_id} not found"}
    rows = await list_children_for_parent(db, node["id"])
    children: List[Dict[str, Any]] = []
    for r in rows:
        h = r["hierarchy"]
        mv = (r.get("metrics") or {}).get(metric_key)
        try:
            val = float(mv) if mv is not None else 0.0
        except (TypeError, ValueError):
            val = 0.0
        children.append({"id": h["id"], "name": h.get("name"), "type": h.get("type"), "value": val})
    return {"metric_key": metric_key, "node_id": node["id"], "children": children}


async def rollup_chart_scatter_entities(db, parent_node_id: str) -> Dict[str, Any]:
    node = await get_node(db, parent_node_id)
    if not node:
        return {"error": "not_found", "message": f"Node {parent_node_id} not found"}
    eids_list = sorted(await entity_codes_for_node(db, node["id"]))
    pts: List[Dict[str, Any]] = []
    for ec in eids_list:
        m = await compute_rollup_metrics(db, {ec}, None)
        pts.append(
            {
                "entity_code": ec,
                "readiness": m.get("audit_readiness_pct"),
                "exposure": m.get("unresolved_high_risk_exposure"),
                "open_critical_cases": m.get("open_critical_cases"),
            }
        )
    return {"node_id": node["id"], "points": pts}


async def rollup_snapshot_history(
    db,
    node_id: str,
    *,
    limit: int = 48,
) -> Dict[str, Any]:
    lim = max(2, min(limit, 120))
    cur = db.rollup_snapshot_history.find({"node_id": node_id}, {"_id": 0}).sort("as_of", -1).limit(lim)
    rows_desc = [r async for r in cur]
    rows_asc = list(reversed(rows_desc))
    deltas: Dict[str, Any] = {}
    if len(rows_desc) >= 2:
        newest = rows_desc[0].get("metrics") or {}
        prior = rows_desc[1].get("metrics") or {}
        for key in ("audit_readiness_pct", "unresolved_high_risk_exposure", "open_critical_cases", "open_cases"):
            a = newest.get(key)
            b = prior.get(key)
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                deltas[key] = {"delta": round(float(a) - float(b), 4), "baseline_as_of": rows_desc[1].get("as_of")}
    span_days = None
    if rows_asc and len(rows_asc) >= 2:
        t0 = _parse_iso_dt(str(rows_asc[0].get("as_of") or ""))
        t1 = _parse_iso_dt(str(rows_asc[-1].get("as_of") or ""))
        if t0 and t1:
            span_days = abs((t1 - t0).days)
    sparkline_keys = ("audit_readiness_pct", "unresolved_high_risk_exposure", "open_critical_cases")
    sparklines: Dict[str, List[Dict[str, Any]]] = {k: [] for k in sparkline_keys}
    for snap in rows_asc:
        ao = snap.get("as_of")
        mm = snap.get("metrics") or {}
        for k in sparkline_keys:
            if k in mm and isinstance(mm[k], (int, float)):
                sparklines[k].append({"as_of": ao, "value": float(mm[k])})
    return {
        "node_id": node_id,
        "series": rows_asc,
        "points_count": len(rows_asc),
        "deltas_latest_pair": deltas,
        "span_days_approx": span_days,
        "sparklines": sparklines,
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
                    "id": n["id"] + "-snap",
                    "node_id": n["id"],
                    "as_of": now,
                    "reporting_ccy": "USD",
                    "metrics": m,
                    "version": ROLLUP_SCHEMA_VERSION,
                }
            },
            upsert=True,
        )
        await db.rollup_snapshot_history.insert_one(
            {
                "id": str(uuid.uuid4()),
                "node_id": n["id"],
                "as_of": now,
                "reporting_ccy": "USD",
                "metrics": m,
                "version": ROLLUP_SCHEMA_VERSION,
            }
        )
        count += 1
    return {"snapshots_upserted": count, "history_events_inserted": count, "as_of": now}
