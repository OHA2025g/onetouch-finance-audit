"""Phase 29 — Regulatory Notice & Litigation Management (seed-friendly)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.deps import audit_log, db
from app.services.kpi_service import as_of_now
from app.services.rbac_service import enforce_entity_scope


router = APIRouter(prefix="/legal", tags=["legal"])


async def _ensure_seed_legal(entity_code: Optional[str] = None) -> Dict[str, int]:
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code

    out = {"legal_notices": 0, "legal_litigations": 0, "legal_hearings": 0}
    now = datetime.now(timezone.utc)

    if await db.legal_notices.count_documents(q) == 0:
        docs = []
        for i in range(12):
            nid = f"NTC-{10000+i}"
            due = now + timedelta(days=(-10 if i % 5 == 0 else 15 + i * 2))
            amount = round(150_000 * (1 + (i % 6) * 0.7), 2)
            docs.append(
                {
                    "id": nid,
                    "entity": entity_code or ["IN-SVC", "UK-OPS", "SG-APAC"][i % 3],
                    "notice_type": ["GST", "Income Tax", "Customs", "SEBI", "Labour", "ROC"][i % 6],
                    "authority": ["GST Dept", "IT Dept", "Customs", "SEBI", "Labour Office", "ROC"][i % 6],
                    "reference_no": f"REF-{nid}",
                    "issued_date": (now - timedelta(days=20 + i * 4)).date().isoformat(),
                    "response_due_date": due.date().isoformat(),
                    "disputed_amount": amount,
                    "status": "overdue" if due.date() < now.date() else ("pending" if i % 4 else "responded"),
                    "owner_email": "legal@onetouch.ai",
                    "created_at": as_of_now(),
                    "created_by": "controller@onetouch.ai",
                }
            )
        await db.legal_notices.insert_many(docs)
        out["legal_notices"] = len(docs)

    if await db.legal_litigations.count_documents(q) == 0:
        docs = []
        for i in range(10):
            lid = f"LIT-{11000+i}"
            amount = round(400_000 * (1 + (i % 5) * 1.1), 2)
            stage = ["pre-trial", "trial", "appeal", "settlement"][i % 4]
            docs.append(
                {
                    "id": lid,
                    "entity": entity_code or ["IN-SVC", "UK-OPS", "SG-APAC"][i % 3],
                    "case_title": f"Litigation matter #{i}",
                    "forum": ["Tribunal", "High Court", "District Court", "Arbitration"][i % 4],
                    "case_no": f"CASE-{lid}",
                    "stage": stage,
                    "disputed_amount": amount,
                    "risk_level": "high" if i % 5 == 0 else ("medium" if i % 2 == 0 else "low"),
                    "provision_amount": round(amount * (0.4 if i % 3 == 0 else 0.1), 2),
                    "provision_assessment": None,
                    "status": "open",
                    "owner_email": "legal@onetouch.ai",
                    "created_at": as_of_now(),
                    "created_by": "controller@onetouch.ai",
                }
            )
        await db.legal_litigations.insert_many(docs)
        out["legal_litigations"] = len(docs)

    if await db.legal_hearings.count_documents(q) == 0:
        lits = [l async for l in db.legal_litigations.find(q, {"_id": 0}).limit(50)]
        docs = []
        for i, l in enumerate(lits[:10]):
            hid = f"HRG-{l['id']}-{i}"
            when = now + timedelta(days=7 + i * 9)
            docs.append(
                {
                    "id": hid,
                    "entity": l.get("entity"),
                    "litigation_id": l["id"],
                    "hearing_date": when.date().isoformat(),
                    "hearing_time": "11:00",
                    "location": l.get("forum"),
                    "status": "scheduled",
                    "notes": None,
                    "created_at": as_of_now(),
                }
            )
        if docs:
            await db.legal_hearings.insert_many(docs)
            out["legal_hearings"] = len(docs)

    return out


@router.get("/notices")
async def legal_notices(entity_code: Optional[str] = Query(None), status: Optional[str] = Query(None), limit: int = Query(200, ge=1, le=5000), offset: int = Query(0, ge=0), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_legal(entity_code=entity_code)
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    if status:
        q["status"] = status
    cur = db.legal_notices.find(q, {"_id": 0}).sort("response_due_date", 1).skip(offset).limit(limit)
    items = [x async for x in cur]
    total = await db.legal_notices.count_documents(q)
    return {"items": items, "total": total, "limit": limit, "offset": offset, "as_of": as_of_now()}


@router.post("/notices")
async def legal_notice_create(body: Dict[str, Any], current=Depends(get_current_user)):
    nid = f"NTC-{__import__('uuid').uuid4().hex[:10]}"
    ent = await enforce_entity_scope(
        db,
        current=current,
        requested_entity_code=(body.get("entity") or body.get("entity_code")),
    )
    doc = {
        "id": nid,
        "entity": ent or body.get("entity") or "US-HQ",
        "notice_type": body.get("notice_type") or "GST",
        "authority": body.get("authority") or "Authority",
        "reference_no": body.get("reference_no") or f"REF-{nid}",
        "issued_date": body.get("issued_date") or datetime.now(timezone.utc).date().isoformat(),
        "response_due_date": body.get("response_due_date") or (datetime.now(timezone.utc) + timedelta(days=14)).date().isoformat(),
        "disputed_amount": float(body.get("disputed_amount") or 0.0),
        "status": body.get("status") or "pending",
        "owner_email": body.get("owner_email") or "legal@onetouch.ai",
        "created_at": as_of_now(),
        "created_by": current.get("email"),
    }
    await db.legal_notices.insert_one(dict(doc))
    await audit_log(current["email"], "legal_notice_create", "legal_notice", nid, {"notice_type": doc["notice_type"], "authority": doc["authority"]})
    return {"status": "ok", "notice_id": nid, "as_of": as_of_now()}


@router.get("/litigations")
async def legal_litigations(entity_code: Optional[str] = Query(None), status: Optional[str] = Query(None), risk_level: Optional[str] = Query(None), limit: int = Query(200, ge=1, le=5000), offset: int = Query(0, ge=0), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_legal(entity_code=entity_code)
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    if status:
        q["status"] = status
    if risk_level:
        q["risk_level"] = risk_level
    cur = db.legal_litigations.find(q, {"_id": 0}).sort("risk_level", 1).skip(offset).limit(limit)
    items = [x async for x in cur]
    total = await db.legal_litigations.count_documents(q)
    return {"items": items, "total": total, "limit": limit, "offset": offset, "as_of": as_of_now()}


@router.post("/litigations")
async def legal_litigation_create(body: Dict[str, Any], current=Depends(get_current_user)):
    lid = f"LIT-{__import__('uuid').uuid4().hex[:10]}"
    disputed = float(body.get("disputed_amount") or 0.0)
    prov = float(body.get("provision_amount") or round(disputed * 0.1, 2))
    ent = await enforce_entity_scope(
        db,
        current=current,
        requested_entity_code=(body.get("entity") or body.get("entity_code")),
    )
    doc = {
        "id": lid,
        "entity": ent or body.get("entity") or "US-HQ",
        "case_title": body.get("case_title") or "Litigation matter",
        "forum": body.get("forum") or "Tribunal",
        "case_no": body.get("case_no") or f"CASE-{lid}",
        "stage": body.get("stage") or "pre-trial",
        "disputed_amount": disputed,
        "risk_level": body.get("risk_level") or "medium",
        "provision_amount": prov,
        "provision_assessment": None,
        "status": body.get("status") or "open",
        "owner_email": body.get("owner_email") or "legal@onetouch.ai",
        "created_at": as_of_now(),
        "created_by": current.get("email"),
    }
    await db.legal_litigations.insert_one(dict(doc))
    await audit_log(current["email"], "legal_litigation_create", "legal_litigation", lid, {"forum": doc["forum"], "risk_level": doc["risk_level"]})
    return {"status": "ok", "litigation_id": lid, "as_of": as_of_now()}


@router.get("/hearings")
async def legal_hearings(entity_code: Optional[str] = Query(None), litigation_id: Optional[str] = Query(None), from_date: Optional[str] = Query(None), to_date: Optional[str] = Query(None), limit: int = Query(200, ge=1, le=5000), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_legal(entity_code=entity_code)
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    if litigation_id:
        q["litigation_id"] = litigation_id
    # date filter is best-effort (string ISO dates)
    if from_date or to_date:
        dt_q: Dict[str, Any] = {}
        if from_date:
            dt_q["$gte"] = from_date
        if to_date:
            dt_q["$lte"] = to_date
        q["hearing_date"] = dt_q
    cur = db.legal_hearings.find(q, {"_id": 0}).sort("hearing_date", 1).limit(limit)
    items = [x async for x in cur]
    total = await db.legal_hearings.count_documents(q)
    return {"items": items, "total": total, "as_of": as_of_now()}


@router.post("/{case_id}/response")
async def legal_response(case_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    """Attach a response note/workflow update to a notice or litigation."""
    n0 = await db.legal_notices.find_one({"id": case_id}, {"_id": 0, "entity": 1})
    l0 = await db.legal_litigations.find_one({"id": case_id}, {"_id": 0, "entity": 1}) if not n0 else None
    ent0 = (n0 or l0 or {}).get("entity")
    if ent0:
        await enforce_entity_scope(db, current=current, requested_entity_code=ent0)
    rid = f"resp-{__import__('uuid').uuid4().hex[:10]}"
    item = {"id": rid, "text": body.get("text") or "", "by": current.get("email"), "at": as_of_now(), "meta": body.get("meta") or {}}
    # Try notice first, then litigation
    res_n = await db.legal_notices.update_one({"id": case_id}, {"$push": {"responses": item}, "$set": {"updated_at": as_of_now(), "status": body.get("status") or "responded"}})
    if res_n.matched_count == 0:
        res_l = await db.legal_litigations.update_one({"id": case_id}, {"$push": {"responses": item}, "$set": {"updated_at": as_of_now()}})
        if res_l.matched_count == 0:
            raise HTTPException(404, "Notice/Litigation not found")
    await audit_log(current["email"], "legal_response", "legal_case", case_id, {"response_id": rid})
    return {"status": "ok", "response_id": rid, "as_of": as_of_now()}


@router.post("/{case_id}/provision-assessment")
async def legal_provision_assessment(case_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    """Record a provision assessment on a litigation or notice."""
    n0 = await db.legal_notices.find_one({"id": case_id}, {"_id": 0, "entity": 1})
    l0 = await db.legal_litigations.find_one({"id": case_id}, {"_id": 0, "entity": 1}) if not n0 else None
    ent0 = (n0 or l0 or {}).get("entity")
    if ent0:
        await enforce_entity_scope(db, current=current, requested_entity_code=ent0)
    assessment = {
        "assessed_by": current.get("email"),
        "assessed_at": as_of_now(),
        "likelihood": body.get("likelihood") or "possible",  # remote/possible/probable
        "recommended_provision": float(body.get("recommended_provision") or 0.0),
        "notes": body.get("notes"),
        "basis": body.get("basis") or "management_estimate",
    }
    # Prefer updating litigation; if it's a notice, update there instead
    res_l = await db.legal_litigations.update_one(
        {"id": case_id},
        {"$set": {"provision_assessment": assessment, "provision_amount": assessment["recommended_provision"], "updated_at": as_of_now()}},
    )
    if res_l.matched_count == 0:
        res_n = await db.legal_notices.update_one({"id": case_id}, {"$set": {"provision_assessment": assessment, "updated_at": as_of_now()}})
        if res_n.matched_count == 0:
            raise HTTPException(404, "Notice/Litigation not found")
    await audit_log(current["email"], "legal_provision_assessment", "legal_case", case_id, {"likelihood": assessment["likelihood"]})
    return {"status": "ok", "as_of": as_of_now()}


@router.get("/exposure-report")
async def legal_exposure_report(entity_code: Optional[str] = Query(None), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_legal(entity_code=entity_code)
    q: Dict[str, Any] = {"entity": entity_code} if entity_code else {}
    notices = [n async for n in db.legal_notices.find(q, {"_id": 0}).limit(5000)]
    lits = [l async for l in db.legal_litigations.find(q, {"_id": 0}).limit(5000)]

    total_notice = sum(float(n.get("disputed_amount") or 0.0) for n in notices)
    total_lit = sum(float(l.get("disputed_amount") or 0.0) for l in lits)
    total_prov = sum(float(l.get("provision_amount") or 0.0) for l in lits)
    overdue_notices = [n for n in notices if n.get("status") == "overdue"]
    high_risk = [l for l in lits if l.get("risk_level") == "high"]

    return {
        "as_of": as_of_now(),
        "entity_code": entity_code,
        "headline": {
            "notice_count": len(notices),
            "litigation_count": len(lits),
            "total_disputed_notice_amount": round(total_notice, 2),
            "total_disputed_litigation_amount": round(total_lit, 2),
            "total_provision_amount": round(total_prov, 2),
            "overdue_notices": len(overdue_notices),
            "high_risk_litigations": len(high_risk),
        },
        "top_overdue_notices": sorted(overdue_notices, key=lambda x: str(x.get("response_due_date") or ""))[:25],
        "top_high_risk_litigations": sorted(high_risk, key=lambda x: -float(x.get("disputed_amount") or 0.0))[:25],
        "note": "Exposure report is based on legal registers; integrate statutory provisioning policy for enterprise use.",
    }

