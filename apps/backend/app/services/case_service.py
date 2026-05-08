"""Case domain helpers shared by routers and application lifecycle (startup seeding)."""
from __future__ import annotations
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from app.utils.timeutil import iso_utc


def merge_cases_master_filters(
    base: Dict[str, Any],
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Merge URL master filters into a MongoDB case query (Phase 9 — dept/cc match exception field aliases)."""
    from app.analytics import _exception_dept_cc_clause

    q: Dict[str, Any] = dict(base)
    if entity_code:
        q["entity"] = entity_code
    if period_ym:
        q["opened_at"] = {"$regex": f"^{period_ym}"}
    dc = _exception_dept_cc_clause(department_id, cost_center_id)
    if not dc:
        return q
    if not q:
        return dc
    return {"$and": [q, dc]}


def case_from_exception(ex: dict, owner_email: str, owner_name: Optional[str]) -> dict[str, Any]:
    """Build a new case document from a control exception (idempotent only at insert site)."""
    now = datetime.now(timezone.utc)
    due = now + timedelta(days=7 if ex["severity"] in ("critical", "high") else 14)
    case: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "exception_id": ex["id"],
        "control_code": ex["control_code"],
        "control_name": ex["control_name"],
        "title": ex["title"],
        "summary": ex["summary"],
        "severity": ex["severity"],
        "status": "open",
        "priority": "P1" if ex["severity"] == "critical" else "P2" if ex["severity"] == "high" else "P3",
        "owner_email": owner_email,
        "owner_name": owner_name,
        "due_date": iso_utc(due),
        "financial_exposure": ex["financial_exposure"],
        "entity": ex["entity"],
        "process": ex["process"],
        "detected_at": ex["detected_at"],
        "opened_at": iso_utc(now),
        "closed_at": None,
        "root_cause_category": None,
    }
    if ex.get("engagement_id"):
        case["engagement_id"] = ex["engagement_id"]
    dept = ex.get("department_id") or ex.get("dept_id")
    cc = ex.get("cost_center_id") or ex.get("cc_id")
    if dept:
        case["department_id"] = dept
    if cc:
        case["cost_center_id"] = cc
    return case


async def backfill_cases_org_from_exceptions(db, *, limit: int = 10000) -> Dict[str, Any]:
    """Phase 9 — set ``department_id`` / ``cost_center_id`` on existing cases from linked exceptions."""
    scanned = 0
    updated = 0
    cur = db.cases.find(
        {
            "exception_id": {"$exists": True, "$ne": ""},
            "$or": [
                {"department_id": {"$exists": False}},
                {"department_id": None},
                {"cost_center_id": {"$exists": False}},
                {"cost_center_id": None},
            ],
        },
        {"_id": 1, "exception_id": 1},
    ).limit(limit)
    async for c in cur:
        scanned += 1
        ex = await db.exceptions.find_one({"id": c.get("exception_id")}, {"_id": 0, "department_id": 1, "dept_id": 1, "cost_center_id": 1, "cc_id": 1})
        if not ex:
            continue
        dept = ex.get("department_id") or ex.get("dept_id")
        cc = ex.get("cost_center_id") or ex.get("cc_id")
        patch: Dict[str, Any] = {}
        if dept:
            patch["department_id"] = dept
        if cc:
            patch["cost_center_id"] = cc
        if patch:
            await db.cases.update_one({"_id": c["_id"]}, {"$set": patch})
            updated += 1
    return {"scanned": scanned, "updated": updated}


async def backfill_cases_required_fields(db, *, limit: int = 5000) -> Dict[str, Any]:
    """Hardening: ensure ad-hoc cases satisfy `CaseOut` required fields.

    Some modules may create cases without linking to an exception yet (e.g., AR collection cases).
    The `/cases` list uses `response_model=List[CaseOut]` so missing required keys can cause 500s.
    """
    from app.services.kpi_service import as_of_now

    scanned = 0
    updated = 0
    cur = db.cases.find(
        {
            "$or": [
                {"exception_id": {"$exists": False}},
                {"exception_id": None},
                {"control_code": {"$exists": False}},
                {"control_code": None},
                {"control_name": {"$exists": False}},
                {"control_name": None},
                {"title": {"$exists": False}},
                {"title": None},
                {"summary": {"$exists": False}},
                {"summary": None},
                {"severity": {"$exists": False}},
                {"severity": None},
                {"status": {"$exists": False}},
                {"status": None},
                {"priority": {"$exists": False}},
                {"priority": None},
                {"owner_email": {"$exists": False}},
                {"owner_email": None},
                {"due_date": {"$exists": False}},
                {"due_date": None},
                {"financial_exposure": {"$exists": False}},
                {"financial_exposure": None},
                {"entity": {"$exists": False}},
                {"entity": None},
                {"process": {"$exists": False}},
                {"process": None},
                {"detected_at": {"$exists": False}},
                {"detected_at": None},
                {"opened_at": {"$exists": False}},
                {"opened_at": None},
            ]
        },
        {
            "_id": 1,
            "id": 1,
            "exception_id": 1,
            "control_code": 1,
            "control_name": 1,
            "title": 1,
            "summary": 1,
            "severity": 1,
            "status": 1,
            "priority": 1,
            "owner_email": 1,
            "due_date": 1,
            "financial_exposure": 1,
            "entity": 1,
            "process": 1,
            "detected_at": 1,
            "opened_at": 1,
        },
    ).limit(limit)
    async for c in cur:
        scanned += 1
        now = as_of_now()
        patch: Dict[str, Any] = {}
        if not c.get("exception_id"):
            patch["exception_id"] = c.get("id") or str(uuid.uuid4())
        if not c.get("control_code"):
            patch["control_code"] = "ADHOC-CASE"
        if not c.get("control_name"):
            patch["control_name"] = "Ad hoc case"
        if not c.get("title"):
            patch["title"] = "Ad hoc case"
        if not c.get("summary"):
            patch["summary"] = (c.get("title") or patch.get("title") or "Ad hoc case") + " — created outside exception workflow."
        if not c.get("severity"):
            patch["severity"] = "medium"
        if not c.get("status"):
            patch["status"] = "open"
        if not c.get("priority"):
            patch["priority"] = "P2"
        if not c.get("owner_email"):
            patch["owner_email"] = "system"
        if not c.get("due_date"):
            patch["due_date"] = now
        if c.get("financial_exposure") is None:
            patch["financial_exposure"] = 0.0
        if not c.get("entity"):
            patch["entity"] = "US-HQ"
        if not c.get("process"):
            patch["process"] = "General"
        if not c.get("detected_at"):
            patch["detected_at"] = c.get("opened_at") or now
        if not c.get("opened_at"):
            patch["opened_at"] = now
        if patch:
            await db.cases.update_one({"_id": c["_id"]}, {"$set": patch})
            updated += 1
    return {"scanned": scanned, "updated": updated}


async def backfill_missing_exceptions_for_cases(db, *, limit: int = 5000) -> Dict[str, Any]:
    """Hardening: create placeholder exceptions for cases that reference a missing exception.

    Some ad-hoc cases use an `exception_id` that doesn't map to an existing exception document,
    but parts of the UI/tests expect `case_detail.exception` to be present.
    """
    from app.services.kpi_service import as_of_now

    scanned = 0
    created = 0
    cur = db.cases.find(
        {"exception_id": {"$exists": True, "$ne": ""}},
        {"_id": 0, "exception_id": 1, "control_code": 1, "control_name": 1, "title": 1, "summary": 1, "severity": 1, "entity": 1, "process": 1, "financial_exposure": 1, "detected_at": 1},
    ).limit(limit)
    async for c in cur:
        scanned += 1
        ex_id = c.get("exception_id")
        if not ex_id:
            continue
        exists = await db.exceptions.find_one({"id": ex_id}, {"_id": 1})
        if exists:
            continue
        now = as_of_now()
        await db.exceptions.insert_one(
            {
                "id": ex_id,
                "control_id": "adhoc-backfill",
                "control_code": c.get("control_code") or "ADHOC-CASE",
                "control_name": c.get("control_name") or "Ad hoc case",
                "process": c.get("process") or "General",
                "entity": c.get("entity") or "US-HQ",
                "severity": c.get("severity") or "medium",
                "status": "open",
                "materiality_score": 0.0,
                "anomaly_score": 0.0,
                "financial_exposure": float(c.get("financial_exposure") or 0.0),
                "source_record_type": "case",
                "source_record_id": c.get("id") or ex_id,
                "detected_at": c.get("detected_at") or now,
                "title": c.get("title") or "Ad hoc case exception",
                "summary": c.get("summary") or c.get("title") or "Backfilled exception placeholder.",
            }
        )
        created += 1
    return {"scanned": scanned, "created": created}
