"""Slice 3 — CFO Action Queue aggregation + lifecycle.

We materialize actionable items into a collection so they can be:
- approved/rejected/escalated/commented
- audited
- stable across refreshes

Items are generated from existing signals: cases, exceptions, controls, approvals, connectors.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.analytics import _scope_exceptions
from app.services.case_service import merge_cases_master_filters
from app.utils.timeutil import iso_utc


def _now() -> str:
    return iso_utc(datetime.now(timezone.utc))


def _stable_id(key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return f"aq-{h}"


def _priority_score(priority: str) -> int:
    return {"P0": 0, "P1": 10, "P2": 20, "P3": 30}.get(priority, 30)


def _derive_priority_for_case(case: Dict[str, Any]) -> str:
    sev = (case.get("severity") or "").lower()
    if sev == "critical":
        return "P0"
    if sev == "high":
        return "P1"
    if (case.get("priority") or "").upper() == "P1":
        return "P1"
    return "P2"


def _derive_priority_for_exception(ex: Dict[str, Any]) -> str:
    sev = (ex.get("severity") or "").lower()
    if sev == "critical":
        return "P0"
    if sev == "high":
        return "P1"
    return "P2"


async def _candidate_actions(
    db,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    # 1) Overdue open cases (highest)
    cq = merge_cases_master_filters(
        {"status": {"$ne": "closed"}},
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    now = datetime.now(timezone.utc)
    cases = [c async for c in db.cases.find(cq, {"_id": 0}).sort("due_date", 1).limit(limit)]
    for c in cases:
        overdue = False
        try:
            due = datetime.fromisoformat(c.get("due_date"))
            overdue = due < now
        except Exception:
            overdue = False
        if not overdue:
            continue
        priority = _derive_priority_for_case(c)
        key = f"case_overdue::{c.get('id')}"
        out.append(
            {
                "id": _stable_id(key),
                "action_key": key,
                "type": "case_overdue",
                "status": "open",
                "priority": priority,
                "score": _priority_score(priority),
                "title": f"Overdue case: {c.get('title', '')}",
                "detail": {
                    "case_id": c.get("id"),
                    "owner_email": c.get("owner_email"),
                    "due_date": c.get("due_date"),
                    "severity": c.get("severity"),
                    "entity": c.get("entity"),
                    "exposure": c.get("financial_exposure"),
                },
                "drill": {"route": f"/app/cases/{c.get('id')}"},
                "created_at": _now(),
                "updated_at": _now(),
            }
        )

    # 2) Top unresolved high/critical exceptions by exposure
    ex_q = _scope_exceptions(
        {"status": {"$ne": "closed"}, "severity": {"$in": ["critical", "high"]}},
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    exc = [e async for e in db.exceptions.find(ex_q, {"_id": 0}).sort("financial_exposure", -1).limit(12)]
    for e in exc:
        priority = _derive_priority_for_exception(e)
        key = f"exception_highrisk::{e.get('id')}"
        out.append(
            {
                "id": _stable_id(key),
                "action_key": key,
                "type": "exception_highrisk",
                "status": "open",
                "priority": priority,
                "score": _priority_score(priority),
                "title": f"High-risk exception: {e.get('title', '')}",
                "detail": {
                    "exception_id": e.get("id"),
                    "control_code": e.get("control_code"),
                    "severity": e.get("severity"),
                    "entity": e.get("entity"),
                    "process": e.get("process"),
                    "exposure": e.get("financial_exposure"),
                },
                "drill": {"route": f"/app/evidence/{e.get('id')}"},
                "created_at": _now(),
                "updated_at": _now(),
            }
        )

    # 3) Pending governance approvals
    apr = [r async for r in db.approval_requests.find({"status": "pending"}, {"_id": 0}).sort("requested_at", -1).limit(15)]
    for r in apr:
        key = f"approval_pending::{r.get('id')}"
        out.append(
            {
                "id": _stable_id(key),
                "action_key": key,
                "type": "approval_pending",
                "status": "open",
                "priority": "P2",
                "score": _priority_score("P2"),
                "title": f"Approval pending: {r.get('request_type')} · {r.get('subject_type')}",
                "detail": r,
                "drill": {"route": "/app/approvals"},
                "created_at": _now(),
                "updated_at": _now(),
            }
        )

    # 4) Connector runs failed recently
    runs = [rr async for rr in db.connector_runs.find({"status": {"$in": ["failed", "error"]}}, {"_id": 0}).sort("started_at", -1).limit(10)]
    for rr in runs:
        key = f"connector_failed::{rr.get('id')}"
        out.append(
            {
                "id": _stable_id(key),
                "action_key": key,
                "type": "connector_failed",
                "status": "open",
                "priority": "P2",
                "score": _priority_score("P2"),
                "title": f"Connector run failed: {rr.get('connector_id')}",
                "detail": rr,
                "drill": {"route": "/app/connectors"},
                "created_at": _now(),
                "updated_at": _now(),
            }
        )

    # Cap
    out.sort(key=lambda x: (x.get("score", 999), x.get("updated_at", "")))
    return out[:limit]


async def refresh_action_queue(
    db,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Compute current candidates and upsert them into collection."""
    items = await _candidate_actions(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    upserted = 0
    for it in items:
        # Preserve terminal status if already decided/escalated, but update title/detail if needed.
        existing = await db.cfo_action_queue.find_one({"id": it["id"]}, {"_id": 0, "status": 1})
        if existing and existing.get("status") in ("approved", "rejected"):
            continue
        await db.cfo_action_queue.update_one({"id": it["id"]}, {"$set": it}, upsert=True)
        upserted += 1
    total = await db.cfo_action_queue.count_documents({})
    return {"items": items, "upserted": upserted, "total_materialized": total}


async def list_queue(db, *, limit: int = 100, offset: int = 0, status: Optional[str] = None) -> Dict[str, Any]:
    q: Dict[str, Any] = {}
    if status:
        q["status"] = status
    total = await db.cfo_action_queue.count_documents(q)
    cur = (
        db.cfo_action_queue.find(q, {"_id": 0})
        .sort([("score", 1), ("updated_at", -1)])
        .skip(offset)
        .limit(limit)
    )
    return {"items": [r async for r in cur], "total": total, "limit": limit, "offset": offset}


async def get_action(db, action_id: str) -> Optional[Dict[str, Any]]:
    return await db.cfo_action_queue.find_one({"id": action_id}, {"_id": 0})


async def _update_status(db, action_id: str, *, status: str, actor: str, note: str = "") -> Dict[str, Any]:
    now = _now()
    patch = {"status": status, "updated_at": now, "updated_by": actor}
    if note:
        patch["last_note"] = note
    await db.cfo_action_queue.update_one({"id": action_id}, {"$set": patch})
    await db.cfo_action_queue.update_one(
        {"id": action_id},
        {"$push": {"events": {"at": now, "actor": actor, "type": status, "note": note}}},
    )
    return await db.cfo_action_queue.find_one({"id": action_id}, {"_id": 0})


async def approve(db, action_id: str, *, actor: str, note: str = "") -> Dict[str, Any]:
    return await _update_status(db, action_id, status="approved", actor=actor, note=note)


async def reject(db, action_id: str, *, actor: str, note: str = "") -> Dict[str, Any]:
    return await _update_status(db, action_id, status="rejected", actor=actor, note=note)


async def escalate(db, action_id: str, *, actor: str, note: str = "") -> Dict[str, Any]:
    return await _update_status(db, action_id, status="escalated", actor=actor, note=note)


async def comment(db, action_id: str, *, actor: str, comment_text: str) -> Dict[str, Any]:
    now = _now()
    await db.cfo_action_queue.update_one(
        {"id": action_id},
        {"$push": {"comments": {"at": now, "actor": actor, "text": comment_text}}},
    )
    await db.cfo_action_queue.update_one({"id": action_id}, {"$set": {"updated_at": now, "updated_by": actor}})
    return await db.cfo_action_queue.find_one({"id": action_id}, {"_id": 0})

