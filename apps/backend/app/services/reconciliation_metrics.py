"""Shared reconciliation enrichment, overdue logic, and summary KPIs (Phase 17)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from motor.motor_asyncio import AsyncIOMotorDatabase

_OPEN_CASE_STATUSES = {"open", "in_progress", "escalated", "pending"}


def parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:  # noqa: BLE001
        return None


def recon_query(entity_code: Optional[str], period_ym: Optional[str]) -> Dict[str, Any]:
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    if period_ym and str(period_ym).strip():
        q["period"] = str(period_ym).strip()
    return q


def workflow_status(rec: Dict[str, Any]) -> str:
    st = str(rec.get("status") or "open").lower()
    if st in ("open", "submitted", "approved"):
        return st
    if st in ("closed",):
        return "approved"
    if st == "overdue":
        return "open"
    return st


def is_overdue(rec: Dict[str, Any], *, now: Optional[datetime] = None) -> bool:
    now = now or datetime.now(timezone.utc)
    if workflow_status(rec) in ("approved",):
        return False
    if str(rec.get("status") or "").lower() == "overdue":
        return True
    due = parse_dt(rec.get("due_date"))
    return bool(due and due < now)


def outside_tolerance(rec: Dict[str, Any]) -> bool:
    tol = float(rec.get("tolerance") if rec.get("tolerance") is not None else 5000)
    return abs(float(rec.get("variance_amount") or 0.0)) > tol


def enrich_reconciliation(rec: Dict[str, Any], *, now: Optional[datetime] = None) -> Dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    evidence = rec.get("evidence") or []
    return {
        **rec,
        "workflow_status": workflow_status(rec),
        "is_overdue": is_overdue(rec, now=now),
        "outside_tolerance": outside_tolerance(rec),
        "evidence_count": len(evidence),
        "has_evidence": len(evidence) > 0,
    }


def days_to_approve(rec: Dict[str, Any]) -> Optional[float]:
    sub = parse_dt(rec.get("submitted_at"))
    appr = parse_dt(rec.get("approved_at"))
    if not sub or not appr or appr < sub:
        return None
    return round((appr - sub).total_seconds() / 86400.0, 2)


def build_reconciliation_summary(
    items: List[Dict[str, Any]],
    total: int,
    *,
    case_stats: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    enriched = [enrich_reconciliation(r, now=now) for r in items]
    case_stats = case_stats or {}

    open_c = sum(1 for r in enriched if r["workflow_status"] == "open")
    submitted_c = sum(1 for r in enriched if r["workflow_status"] == "submitted")
    approved_c = sum(1 for r in enriched if r["workflow_status"] == "approved")
    overdue_c = sum(1 for r in enriched if r["is_overdue"])
    outside_c = sum(1 for r in enriched if r["outside_tolerance"])
    no_evidence_c = sum(
        1 for r in enriched if not r["has_evidence"] and r["workflow_status"] in ("open", "submitted")
    )

    abs_variance_total = round(sum(abs(float(r.get("variance_amount") or 0.0)) for r in enriched), 2)
    outside_variance = round(
        sum(abs(float(r.get("variance_amount") or 0.0)) for r in enriched if r["outside_tolerance"]),
        2,
    )

    approve_days = [
        d for r in enriched if r["workflow_status"] == "approved" and (d := days_to_approve(r)) is not None
    ]
    avg_days_to_approve = round(sum(approve_days) / len(approve_days), 2) if approve_days else None

    by_type: Dict[str, Dict[str, float]] = defaultdict(lambda: {"count": 0, "abs_variance": 0.0})
    by_entity: Dict[str, Dict[str, float]] = defaultdict(lambda: {"count": 0, "abs_variance": 0.0, "overdue_count": 0})

    for r in enriched:
        t = str(r.get("reconciliation_type") or "Other")
        ent = str(r.get("entity") or "—")
        av = abs(float(r.get("variance_amount") or 0.0))
        by_type[t]["count"] += 1
        by_type[t]["abs_variance"] += av
        by_entity[ent]["count"] += 1
        by_entity[ent]["abs_variance"] += av
        if r["is_overdue"]:
            by_entity[ent]["overdue_count"] += 1

    by_type_rows = [
        {
            "type": k,
            "count": int(v["count"]),
            "abs_variance": round(v["abs_variance"], 2),
        }
        for k, v in sorted(by_type.items(), key=lambda kv: -kv[1]["count"])
    ]
    by_entity_rows = [
        {
            "entity": k,
            "count": int(v["count"]),
            "abs_variance": round(v["abs_variance"], 2),
            "overdue_count": int(v["overdue_count"]),
        }
        for k, v in sorted(by_entity.items(), key=lambda kv: -kv[1]["abs_variance"])
    ]

    top_entities_by_variance = sorted(by_entity_rows, key=lambda x: -x["abs_variance"])[:5]

    top_by_overdue_entity = sorted(
        [row for row in by_entity_rows if row["overdue_count"] > 0],
        key=lambda x: (-x["overdue_count"], -x["abs_variance"]),
    )[:5]

    escalated_in_scan = sum(1 for r in enriched if r.get("case_id"))
    recon_ids_with_case = {r["id"] for r in enriched if r.get("case_id")}

    return {
        "kpis": {
            "total_reconciliations": total,
            "scanned": len(enriched),
            "open_count": open_c,
            "submitted_count": submitted_c,
            "approved_count": approved_c,
            "overdue_count": overdue_c,
            "outside_tolerance_count": outside_c,
            "no_evidence_count": no_evidence_c,
            "abs_variance_total": abs_variance_total,
            "outside_tolerance_variance": outside_variance,
            "pct_overdue": round(100.0 * overdue_c / len(enriched), 1) if enriched else 0.0,
            "pct_outside_tolerance": round(100.0 * outside_c / len(enriched), 1) if enriched else 0.0,
            "avg_days_to_approve": avg_days_to_approve,
            "escalated_to_case_count": int(case_stats.get("escalated_total") or escalated_in_scan),
            "escalated_in_scan_count": escalated_in_scan,
            "open_linked_cases_count": int(case_stats.get("open_linked_cases") or 0),
            "reconciliations_with_open_case_count": int(case_stats.get("recons_with_open_case") or 0),
        },
        "by_type": by_type_rows,
        "by_entity": by_entity_rows,
        "top_entities_by_variance": top_entities_by_variance,
        "top_entities_by_overdue": top_by_overdue_entity,
        "recon_ids_with_case": sorted(recon_ids_with_case),
    }


async def count_overdue_reconciliations(
    db: AsyncIOMotorDatabase,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    scan_limit: int = 5000,
) -> Tuple[int, int]:
    """Return (overdue_count, total_count) using computed overdue logic."""
    q = recon_query(entity_code, period_ym)
    total = await db.reconciliations.count_documents(q or {})
    cur = db.reconciliations.find(q or {}, {"_id": 0, "status": 1, "due_date": 1}).limit(scan_limit)
    now = datetime.now(timezone.utc)
    overdue = 0
    async for doc in cur:
        if is_overdue(doc, now=now):
            overdue += 1
    return overdue, total


async def case_linkage_stats(
    db: AsyncIOMotorDatabase,
    recon_ids: List[str],
    *,
    entity_code: Optional[str] = None,
    items: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, int]:
    """Counts for reconciliations escalated / with open linked cases."""
    q_esc: Dict[str, Any] = {"case_id": {"$exists": True, "$ne": None}}
    if entity_code:
        q_esc["entity"] = entity_code
    escalated_total = await db.reconciliations.count_documents(q_esc)

    if not recon_ids:
        return {"escalated_total": escalated_total, "open_linked_cases": 0, "recons_with_open_case": 0}

    ex_ids = [f"rec-{rid}" for rid in recon_ids]
    case_ids = [str(r.get("case_id")) for r in (items or []) if r.get("case_id")]
    or_clauses: List[Dict[str, Any]] = [{"exception_id": {"$in": ex_ids}}]
    if case_ids:
        or_clauses.append({"id": {"$in": case_ids}})

    case_q: Dict[str, Any] = {"$or": or_clauses, "status": {"$in": list(_OPEN_CASE_STATUSES)}}
    if entity_code:
        case_q["entity"] = entity_code

    open_cases = [
        c async for c in db.cases.find(case_q, {"_id": 0, "id": 1, "exception_id": 1}).limit(5000)
    ]

    linked_recon_ids: set[str] = set()
    for c in open_cases:
        ex_id = str(c.get("exception_id") or "")
        if ex_id.startswith("rec-"):
            linked_recon_ids.add(ex_id[4:])

    for r in items or []:
        if r.get("case_id") and r.get("id") in recon_ids:
            linked_recon_ids.add(str(r["id"]))

    return {
        "escalated_total": escalated_total,
        "open_linked_cases": len(open_cases),
        "recons_with_open_case": len(linked_recon_ids.intersection(set(recon_ids))),
    }


async def fetch_reconciliation_summary(
    db: AsyncIOMotorDatabase,
    *,
    entity_code: Optional[str],
    period_ym: Optional[str],
    scan_limit: int,
) -> Dict[str, Any]:
    q = recon_query(entity_code, period_ym)
    cur = db.reconciliations.find(q, {"_id": 0}).sort("due_date", -1).limit(scan_limit)
    raw = [r async for r in cur]
    total = await db.reconciliations.count_documents(q or {})
    now = datetime.now(timezone.utc)
    items = [enrich_reconciliation(r, now=now) for r in raw]
    recon_ids = [r["id"] for r in items if r.get("id")]
    stats = await case_linkage_stats(db, recon_ids, entity_code=entity_code, items=items)
    summary = build_reconciliation_summary(items, total, case_stats=stats)
    return summary


async def load_linked_case(db: AsyncIOMotorDatabase, reconciliation_id: str, rec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    cid = rec.get("case_id")
    if cid:
        case = await db.cases.find_one({"id": cid}, {"_id": 0, "id": 1, "title": 1, "status": 1, "severity": 1, "financial_exposure": 1})
        if case:
            return case
    ex_id = f"rec-{reconciliation_id}"
    case = await db.cases.find_one({"exception_id": ex_id}, {"_id": 0, "id": 1, "title": 1, "status": 1, "severity": 1, "financial_exposure": 1})
    return case
