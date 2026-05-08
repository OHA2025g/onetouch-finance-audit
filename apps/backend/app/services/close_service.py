"""Slice 4 — Month-end close cycles and tasks."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from app.utils.timeutil import iso_utc


def _now() -> str:
    return iso_utc(datetime.now(timezone.utc))


DEFAULT_TEMPLATES: List[Dict[str, Any]] = [
    {"code": "CLOSE-01", "title": "Bank reconciliations completed", "category": "Treasury", "sla_days": 2, "critical": True},
    {"code": "CLOSE-02", "title": "AR ageing reviewed + provisions updated", "category": "Working Capital", "sla_days": 3, "critical": True},
    {"code": "CLOSE-03", "title": "AP ageing reviewed + payment holds cleared", "category": "Working Capital", "sla_days": 3, "critical": True},
    {"code": "CLOSE-04", "title": "Revenue cutoff review (O2C)", "category": "Revenue", "sla_days": 4, "critical": True},
    {"code": "CLOSE-05", "title": "Journal entry review complete", "category": "R2R", "sla_days": 4, "critical": True},
    {"code": "CLOSE-06", "title": "Tax accruals and filings checklist", "category": "Tax", "sla_days": 5, "critical": False},
]


async def ensure_close_templates(db) -> Dict[str, Any]:
    if await db.close_task_templates.count_documents({}) > 0:
        return {"status": "already_present"}
    now = _now()
    docs = []
    for t in DEFAULT_TEMPLATES:
        docs.append({**t, "id": f"tmpl-{uuid.uuid4().hex[:10]}", "created_at": now})
    await db.close_task_templates.insert_many(docs)
    return {"status": "seeded", "count": len(docs)}


async def list_cycles(db) -> List[Dict[str, Any]]:
    return [c async for c in db.close_cycles.find({}, {"_id": 0}).sort("period_ym", -1).limit(60)]


async def create_cycle(db, *, period_ym: str, name: str, created_by: str) -> Dict[str, Any]:
    period_ym = (period_ym or "").strip()
    if not period_ym or len(period_ym) < 7:
        raise HTTPException(400, "period_ym must be YYYY-MM")
    existing = await db.close_cycles.find_one({"period_ym": period_ym}, {"_id": 0})
    if existing:
        return existing

    now = _now()
    cid = f"cyc-{uuid.uuid4().hex[:10]}"
    cycle = {
        "id": cid,
        "period_ym": period_ym,
        "name": name or f"Month-end close {period_ym}",
        "status": "open",
        "created_at": now,
        "created_by": created_by,
        "signed_off_at": None,
        "signed_off_by": None,
        "override_reason": None,
    }
    await db.close_cycles.insert_one(dict(cycle))

    # instantiate tasks from templates
    tmpls = [t async for t in db.close_task_templates.find({}, {"_id": 0}).sort("code", 1)]
    tasks = []
    for idx, t in enumerate(tmpls):
        due = datetime.now(timezone.utc) + timedelta(days=int(t.get("sla_days") or 3))
        tasks.append(
            {
                "id": f"tsk-{uuid.uuid4().hex[:10]}",
                "cycle_id": cid,
                "template_code": t.get("code"),
                "title": t.get("title"),
                "category": t.get("category"),
                "critical": bool(t.get("critical")),
                "status": "draft",
                "owner_email": None,
                "due_date": iso_utc(due),
                "evidence": [],
                "notes": [],
                "created_at": now,
                "updated_at": now,
            }
        )
    if tasks:
        await db.close_tasks.insert_many(tasks)
    await db.close_events.insert_one({"id": str(uuid.uuid4()), "cycle_id": cid, "at": now, "actor": created_by, "type": "cycle_created"})
    return cycle


async def get_cycle(db, cycle_id: str) -> Dict[str, Any]:
    cyc = await db.close_cycles.find_one({"id": cycle_id}, {"_id": 0})
    if not cyc:
        raise HTTPException(404, "Close cycle not found")
    tasks = [t async for t in db.close_tasks.find({"cycle_id": cycle_id}, {"_id": 0}).sort("critical", -1)]
    return {**cyc, "tasks": tasks}


async def list_tasks(db, cycle_id: Optional[str] = None) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {}
    if cycle_id:
        q["cycle_id"] = cycle_id
    return [t async for t in db.close_tasks.find(q, {"_id": 0}).sort("due_date", 1).limit(500)]


async def patch_task(db, task_id: str, patch: Dict[str, Any], actor: str) -> Dict[str, Any]:
    allowed = {k: v for k, v in patch.items() if k in ("owner_email", "title", "due_date")}
    if not allowed:
        raise HTTPException(400, "No editable fields in patch")
    allowed["updated_at"] = _now()
    await db.close_tasks.update_one({"id": task_id}, {"$set": allowed})
    t = await db.close_tasks.find_one({"id": task_id}, {"_id": 0})
    if not t:
        raise HTTPException(404, "Task not found")
    await db.close_events.insert_one({"id": str(uuid.uuid4()), "cycle_id": t["cycle_id"], "at": _now(), "actor": actor, "type": "task_updated", "detail": {"task_id": task_id, "patch": list(allowed.keys())}})
    return t


async def add_evidence(db, task_id: str, evidence: Dict[str, Any], actor: str) -> Dict[str, Any]:
    if not evidence.get("type") or not evidence.get("uri"):
        raise HTTPException(400, "evidence requires type and uri")
    ev = {**evidence, "at": _now(), "by": actor, "id": f"ev-{uuid.uuid4().hex[:10]}"}
    await db.close_tasks.update_one({"id": task_id}, {"$push": {"evidence": ev}, "$set": {"updated_at": _now()}})
    t = await db.close_tasks.find_one({"id": task_id}, {"_id": 0})
    if not t:
        raise HTTPException(404, "Task not found")
    await db.close_events.insert_one({"id": str(uuid.uuid4()), "cycle_id": t["cycle_id"], "at": _now(), "actor": actor, "type": "evidence_added", "detail": {"task_id": task_id}})
    return t


async def _set_task_status(db, task_id: str, status: str, actor: str, note: str = "") -> Dict[str, Any]:
    if status not in ("draft", "submitted", "approved", "reopened"):
        raise HTTPException(400, "Invalid status")
    now = _now()
    await db.close_tasks.update_one({"id": task_id}, {"$set": {"status": status, "updated_at": now}})
    if note:
        await db.close_tasks.update_one({"id": task_id}, {"$push": {"notes": {"at": now, "by": actor, "text": note}}})
    t = await db.close_tasks.find_one({"id": task_id}, {"_id": 0})
    if not t:
        raise HTTPException(404, "Task not found")
    await db.close_events.insert_one({"id": str(uuid.uuid4()), "cycle_id": t["cycle_id"], "at": now, "actor": actor, "type": f"task_{status}", "detail": {"task_id": task_id}})
    return t


async def submit_task(db, task_id: str, actor: str) -> Dict[str, Any]:
    return await _set_task_status(db, task_id, "submitted", actor)


async def approve_task(db, task_id: str, actor: str) -> Dict[str, Any]:
    return await _set_task_status(db, task_id, "approved", actor)


async def reopen_task(db, task_id: str, actor: str, note: str = "") -> Dict[str, Any]:
    return await _set_task_status(db, task_id, "reopened", actor, note=note)


async def signoff(db, cycle_id: str, actor: str, *, override: bool = False, override_reason: str = "") -> Dict[str, Any]:
    cyc = await db.close_cycles.find_one({"id": cycle_id}, {"_id": 0})
    if not cyc:
        raise HTTPException(404, "Close cycle not found")
    tasks = [t async for t in db.close_tasks.find({"cycle_id": cycle_id}, {"_id": 0})]
    incomplete = [t for t in tasks if t.get("critical") and t.get("status") != "approved"]
    if incomplete and not override:
        raise HTTPException(409, f"Cannot sign off: {len(incomplete)} critical tasks not approved")
    now = _now()
    patch = {"status": "signed_off", "signed_off_at": now, "signed_off_by": actor}
    if override:
        patch["override_reason"] = override_reason or "override"
    await db.close_cycles.update_one({"id": cycle_id}, {"$set": patch})
    await db.close_events.insert_one({"id": str(uuid.uuid4()), "cycle_id": cycle_id, "at": now, "actor": actor, "type": "cycle_signed_off", "detail": {"override": override}})
    return await db.close_cycles.find_one({"id": cycle_id}, {"_id": 0})


async def bottlenecks(db, cycle_id: str) -> Dict[str, Any]:
    tasks = [t async for t in db.close_tasks.find({"cycle_id": cycle_id}, {"_id": 0})]
    pending = [t for t in tasks if t.get("status") in ("draft", "reopened", "submitted")]
    by_owner: Dict[str, int] = {}
    for t in pending:
        o = t.get("owner_email") or "unassigned"
        by_owner[o] = by_owner.get(o, 0) + 1
    return {"pending": len(pending), "by_owner": by_owner, "top": sorted(by_owner.items(), key=lambda kv: -kv[1])[:5]}


async def quality_score(db, cycle_id: str) -> Dict[str, Any]:
    tasks = [t async for t in db.close_tasks.find({"cycle_id": cycle_id}, {"_id": 0})]
    total = len(tasks) or 1
    approved = sum(1 for t in tasks if t.get("status") == "approved")
    critical_total = sum(1 for t in tasks if t.get("critical"))
    critical_approved = sum(1 for t in tasks if t.get("critical") and t.get("status") == "approved")
    pct = round(100.0 * approved / total, 1)
    crit_pct = round(100.0 * critical_approved / (critical_total or 1), 1)
    score = round(0.6 * pct + 0.4 * crit_pct, 1)
    return {"score": score, "approved_pct": pct, "critical_approved_pct": crit_pct, "total_tasks": total}

