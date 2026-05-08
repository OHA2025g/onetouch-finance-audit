"""Case management: create from exception, list, detail, update, comments."""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.deps import db, audit_log, iso
from app.models import CaseOut, CaseUpdate, CommentCreate, CommentOut
from app.services.case_service import case_from_exception, merge_cases_master_filters

router = APIRouter(tags=["cases"])


@router.post("/cases/from-exception")
async def case_from_exception_endpoint(exception_id: str = Query(...), owner_email: Optional[str] = Query(None),
                                       current=Depends(get_current_user)):
    ex = await db.exceptions.find_one({"id": exception_id}, {"_id": 0})
    if not ex:
        raise HTTPException(404, "Exception not found")
    existing = await db.cases.find_one({"exception_id": exception_id}, {"_id": 0})
    if existing:
        return existing
    owner = owner_email or current["email"]
    owner_user = await db.users.find_one({"email": owner}, {"_id": 0})
    case = case_from_exception(ex, owner, owner_user["full_name"] if owner_user else None)
    await db.cases.insert_one(dict(case))
    await db.exceptions.update_one({"id": exception_id}, {"$set": {"status": "in_progress"}})
    await db.case_status_history.insert_one({
        "id": str(uuid.uuid4()), "case_id": case["id"],
        "old_status": None, "new_status": "open",
        "changed_by_user_email": current["email"], "changed_at": iso(datetime.now(timezone.utc)),
    })
    await audit_log(current["email"], "create_case", "case", case["id"], {"exception_id": exception_id})
    return case


@router.get("/cases", response_model=List[CaseOut])
async def cases_list(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    owner_email: Optional[str] = None,
    engagement_id: Optional[str] = None,
    entity_code: Optional[str] = Query(None, description="Phase 5 — scope cases to legal entity"),
    period_ym: Optional[str] = Query(None, description="YYYY-MM — case opened_at prefix"),
    department_id: Optional[str] = Query(None, description="Phase 9 — scope cases by org slice (denormalized from exception)"),
    cost_center_id: Optional[str] = Query(None, description="Phase 9 — scope cases by cost center (denormalized from exception)"),
    limit: int = 200,
    current=Depends(get_current_user),
):
    q: Dict[str, Any] = {}
    if status:
        q["status"] = status
    if severity:
        q["severity"] = severity
    if owner_email:
        q["owner_email"] = owner_email
    if engagement_id:
        q["engagement_id"] = engagement_id
    q = merge_cases_master_filters(
        q,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    mat_doc = None
    if engagement_id:
        mat_doc = await db.ca_materiality.find_one({"engagement_id": engagement_id}, {"_id": 0})
    fm = float(mat_doc.get("final_materiality") or 0) if mat_doc else 0.0
    trivial = float(mat_doc.get("trivial_threshold") or 0) if mat_doc else 0.0
    out: List[Dict[str, Any]] = []
    async for c in db.cases.find(q, {"_id": 0}).sort("due_date", 1).limit(limit):
        row = dict(c)
        if engagement_id and (fm or trivial):
            ex = await db.exceptions.find_one({"id": row.get("exception_id")}, {"_id": 0})
            fe = float(ex.get("financial_exposure") or 0) if ex else 0.0
            row["material_impact"] = bool(fm and fe >= fm)
            row["material_watch"] = bool(trivial and fe >= trivial and (not fm or fe < fm))
        out.append(row)
    return out


@router.get("/cases/{case_id}")
async def case_detail(case_id: str, current=Depends(get_current_user)):
    case = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not case:
        raise HTTPException(404, "Case not found")
    from app.services import legal_hold_service as ghs
    comments = [c async for c in db.case_comments.find({"case_id": case_id}, {"_id": 0}).sort("created_at", 1)]
    history = [h async for h in db.case_status_history.find({"case_id": case_id}, {"_id": 0}).sort("changed_at", 1)]
    exception = await db.exceptions.find_one({"id": case["exception_id"]}, {"_id": 0})
    governance = await ghs.governance_flags_for_case(db, case_id)
    return {
        "case": case, "comments": comments, "history": history, "exception": exception, "governance": governance,
    }


@router.patch("/cases/{case_id}")
async def case_update(
    case_id: str, body: CaseUpdate,
    current=Depends(get_current_user),
    force_override: bool = Query(False, description="Policy override (CFO/IA) for WORM-locked case"),
):
    from app.services import worm_service as wsv

    case = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not case:
        raise HTTPException(404, "Case not found")
    await wsv.require_case_mutable(db, case, current, force_override=force_override)
    update = {k: v for k, v in body.model_dump().items() if v is not None}
    if "status" in update and update["status"] != case.get("status"):
        await db.case_status_history.insert_one({
            "id": str(uuid.uuid4()), "case_id": case_id,
            "old_status": case["status"], "new_status": update["status"],
            "changed_by_user_email": current["email"], "changed_at": iso(datetime.now(timezone.utc)),
        })
        if update["status"] == "closed":
            update["closed_at"] = iso(datetime.now(timezone.utc))
            await db.exceptions.update_one({"id": case["exception_id"]}, {"$set": {"status": "closed"}})
            await wsv.lock_case_on_close(db, case_id, current["email"])
    if "owner_email" in update:
        u = await db.users.find_one({"email": update["owner_email"]}, {"_id": 0})
        if u:
            update["owner_name"] = u["full_name"]
    await db.cases.update_one({"id": case_id}, {"$set": update})
    await audit_log(current["email"], "update_case", "case", case_id, {**update, "force_override": force_override})
    return await db.cases.find_one({"id": case_id}, {"_id": 0})


@router.post("/cases/{case_id}/comments", response_model=CommentOut)
async def case_comment(
    case_id: str, body: CommentCreate,
    current=Depends(get_current_user),
    force_override: bool = Query(False, description="Policy override (CFO/IA) to comment on WORM-locked case"),
):
    from app.services import worm_service as wsv

    case0 = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not case0:
        raise HTTPException(404, "Case not found")
    await wsv.require_case_mutable(db, case0, current, force_override=force_override)
    user = await db.users.find_one({"id": current["user_id"]}, {"_id": 0})
    doc = {
        "id": str(uuid.uuid4()),
        "case_id": case_id,
        "user_email": current["email"],
        "user_name": user["full_name"] if user else current["email"],
        "comment": body.comment,
        "created_at": iso(datetime.now(timezone.utc)),
    }
    await db.case_comments.insert_one(dict(doc))
    await audit_log(current["email"], "comment", "case", case_id)
    return doc
