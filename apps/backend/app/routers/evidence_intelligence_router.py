"""Phase 34 — Evidence OCR & Document Intelligence (mock extraction pipeline).

This provides stable, seed-friendly behavior without external OCR dependencies.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.core.entity_scope import entity_scope_enforced
from app.deps import audit_log, db
from app.services.kpi_service import as_of_now
from app.services.rbac_service import assert_exception_entity_scope, enforce_entity_scope


router = APIRouter(prefix="/evidence-intelligence", tags=["evidence-intelligence"])


async def _enforce_evidence_document_entity_scope(db, current: dict, doc: Dict[str, Any]) -> None:
    """Scope reads/writes on evidence documents: stamped ``entity`` must match user; legacy docs without it denied."""
    if doc.get("entity"):
        await enforce_entity_scope(db, current=current, requested_entity_code=doc.get("entity"))
        return
    if await entity_scope_enforced(db) and current.get("role") != "Super Admin":
        user = await db.users.find_one({"id": current.get("user_id")}, {"_id": 0, "entity": 1})
        if (user or {}).get("entity"):
            raise HTTPException(403, "Entity scope violation")


def _now() -> str:
    return as_of_now()


def _infer_doc_type(body: Dict[str, Any]) -> str:
    dt = (body.get("document_type") or "").strip().lower()
    name = (body.get("document_name") or "").strip().lower()
    if dt:
        return dt
    if "invoice" in name:
        return "invoice"
    if "bank" in name or "statement" in name:
        return "bank_statement"
    if "po" in name or "purchase" in name:
        return "purchase_order"
    if "contract" in name:
        return "contract"
    return "unknown"


def _mock_extract_fields(doc_type: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic extraction with minimal heuristics from provided text."""
    text = str(body.get("text") or "")
    entity = body.get("entity") or "US-HQ"

    def pick_first(prefixes: List[str]) -> Optional[str]:
        for p in prefixes:
            if p in text:
                # extremely small heuristic: token after prefix
                idx = text.find(p) + len(p)
                tail = text[idx : idx + 64].strip().split()
                if tail:
                    return tail[0].strip().strip(":").strip()
        return None

    if doc_type == "invoice":
        inv_no = body.get("invoice_number") or pick_first(["Invoice#", "Invoice No", "INV-"]) or "INV-MOCK-001"
        vendor = body.get("vendor_name") or pick_first(["Vendor", "Supplier"]) or "Vendor Mock"
        amount = float(body.get("amount") or 125000.0)
        return {"entity": entity, "invoice_number": inv_no, "vendor_name": vendor, "amount": amount, "currency": body.get("currency") or "INR"}
    if doc_type == "bank_statement":
        acct = body.get("account_number") or pick_first(["Account", "A/C"]) or "XXXX1234"
        period = body.get("period") or datetime.now(timezone.utc).date().strftime("%Y-%m")
        return {"entity": entity, "account_number_masked": acct, "period": period, "currency": body.get("currency") or "INR"}
    if doc_type == "purchase_order":
        po = body.get("po_number") or pick_first(["PO#", "PO No", "PO-"]) or "PO-MOCK-001"
        amount = float(body.get("amount") or 200000.0)
        return {"entity": entity, "po_number": po, "amount": amount, "currency": body.get("currency") or "INR"}
    if doc_type == "contract":
        counterparty = body.get("counterparty") or pick_first(["Counterparty", "Party"]) or "Counterparty Mock"
        return {"entity": entity, "counterparty": counterparty, "effective_date": body.get("effective_date") or datetime.now(timezone.utc).date().isoformat()}
    return {"entity": entity, "note": "unknown document type; provide document_type for richer extraction"}


def _quality_issues(doc_type: str, fields: Dict[str, Any]) -> List[Dict[str, Any]]:
    req = {
        "invoice": ["invoice_number", "vendor_name", "amount"],
        "bank_statement": ["account_number_masked", "period"],
        "purchase_order": ["po_number", "amount"],
        "contract": ["counterparty", "effective_date"],
    }.get(doc_type, [])
    issues = []
    for k in req:
        if fields.get(k) in (None, "", 0, 0.0):
            issues.append({"field": k, "issue": "missing", "severity": "warning"})
    score = max(0.0, 1.0 - (0.2 * len(issues))) if req else 0.6
    issues.append({"field": "__quality_score__", "issue": "computed", "severity": "info", "value": round(score, 2)})
    return issues


@router.post("/extract")
async def evidence_extract(body: Dict[str, Any], current=Depends(get_current_user)):
    did = f"DOC-{__import__('uuid').uuid4().hex[:10]}"
    doc_type = _infer_doc_type(body)
    ent_ctx = await enforce_entity_scope(
        db, current=current, requested_entity_code=(body.get("entity") or body.get("entity_code"))
    )
    body_for_mock = {**body, "entity": ent_ctx or body.get("entity") or "US-HQ"}
    fields = _mock_extract_fields(doc_type, body_for_mock)
    issues = _quality_issues(doc_type, fields)
    score = next((i.get("value") for i in issues if i.get("field") == "__quality_score__"), None)

    doc = {
        "id": did,
        "entity": fields.get("entity") or body_for_mock.get("entity") or "US-HQ",
        "document_name": body.get("document_name") or did,
        "document_type": doc_type,
        "source_uri": body.get("uri") or body.get("source_uri"),
        "text_provided": bool(body.get("text")),
        "created_at": _now(),
        "created_by": current.get("email"),
        "status": "extracted",
    }
    extraction = {
        "id": f"EXT-{did}",
        "document_id": did,
        "document_type": doc_type,
        "fields": fields,
        "quality_score": score,
        "issues": [i for i in issues if i.get("field") != "__quality_score__"],
        "extracted_at": _now(),
        "extracted_by": "mock_ocr",
    }
    await db.evidence_documents.insert_one(dict(doc))
    await db.evidence_extractions.insert_one(dict(extraction))

    if extraction["issues"]:
        for idx, iss in enumerate(extraction["issues"]):
            qid = f"QI-{did}-{idx}"
            await db.evidence_quality_issues.update_one(
                {"id": qid},
                {
                    "$setOnInsert": {
                        "id": qid,
                        "document_id": did,
                        "document_type": doc_type,
                        "field": iss.get("field"),
                        "issue": iss.get("issue"),
                        "severity": iss.get("severity") or "warning",
                        "status": "open",
                        "detected_at": _now(),
                        "entity": doc["entity"],
                    }
                },
                upsert=True,
            )

    await audit_log(current["email"], "evidence_extract", "evidence_document", did, {"document_type": doc_type, "quality_score": score})
    return {"status": "ok", "document_id": did, "document_type": doc_type, "quality_score": score, "fields": fields, "as_of": _now()}


@router.post("/{document_id}/link")
async def evidence_link(document_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    doc = await db.evidence_documents.find_one({"id": document_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Document not found")
    await _enforce_evidence_document_entity_scope(db, current, doc)
    link_id = f"LINK-{__import__('uuid').uuid4().hex[:10]}"
    target_type = body.get("target_type") or "exception"  # exception|case|control
    target_id = body.get("target_id")
    if not target_id:
        raise HTTPException(400, "target_id required")
    if target_type == "exception":
        ex = await db.exceptions.find_one({"id": target_id}, {"_id": 0})
        if ex:
            await assert_exception_entity_scope(db, current=current, exception=ex)
    elif target_type == "case":
        case = await db.cases.find_one({"id": target_id}, {"_id": 0})
        if case:
            if case.get("entity"):
                await enforce_entity_scope(db, current=current, requested_entity_code=case.get("entity"))
            elif await entity_scope_enforced(db) and current.get("role") != "Super Admin":
                user = await db.users.find_one({"id": current.get("user_id")}, {"_id": 0, "entity": 1})
                if (user or {}).get("entity"):
                    raise HTTPException(403, "Entity scope violation")
    link = {
        "id": link_id,
        "document_id": document_id,
        "target_type": target_type,
        "target_id": target_id,
        "note": body.get("note"),
        "linked_at": _now(),
        "linked_by": current.get("email"),
        "entity": doc.get("entity"),
    }
    await db.evidence_links.insert_one(dict(link))
    await audit_log(current["email"], "evidence_link", "evidence_link", link_id, {"document_id": document_id, "target_type": target_type, "target_id": target_id})
    return {"status": "ok", "link_id": link_id, "as_of": _now()}


@router.get("/quality-issues")
async def evidence_quality_issues(entity_code: Optional[str] = Query(None), status: str = Query("open"), limit: int = Query(200, ge=1, le=2000), offset: int = Query(0, ge=0), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    if status:
        q["status"] = status
    cur = db.evidence_quality_issues.find(q, {"_id": 0}).sort("detected_at", -1).skip(offset).limit(limit)
    items = [x async for x in cur]
    total = await db.evidence_quality_issues.count_documents(q)
    return {"items": items, "total": total, "limit": limit, "offset": offset, "as_of": _now()}


@router.get("/{document_id}")
async def evidence_get(document_id: str, current=Depends(get_current_user)):
    # IMPORTANT: keep this AFTER fixed paths like /quality-issues to avoid route shadowing.
    doc = await db.evidence_documents.find_one({"id": document_id}, {"_id": 0})
    if not doc:
        return {"id": document_id, "found": False, "as_of": _now()}
    await _enforce_evidence_document_entity_scope(db, current, doc)
    ext = await db.evidence_extractions.find_one({"document_id": document_id}, {"_id": 0})
    links = [l async for l in db.evidence_links.find({"document_id": document_id}, {"_id": 0}).limit(200)]
    return {"found": True, "document": doc, "extraction": ext, "links": links, "as_of": _now()}


@router.post("/{document_id}/review")
async def evidence_review(document_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    doc = await db.evidence_documents.find_one({"id": document_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Document not found")
    await _enforce_evidence_document_entity_scope(db, current, doc)
    rid = f"REV-{__import__('uuid').uuid4().hex[:10]}"
    decision = body.get("decision") or "accepted"  # accepted|rejected|needs_more_info
    review = {
        "id": rid,
        "document_id": document_id,
        "decision": decision,
        "note": body.get("note"),
        "reviewed_by": current.get("email"),
        "reviewed_at": _now(),
        "entity": doc.get("entity"),
    }
    await db.evidence_reviews.insert_one(dict(review))
    await db.evidence_documents.update_one({"id": document_id}, {"$set": {"review_status": decision, "reviewed_at": _now(), "reviewed_by": current.get("email")}})
    if decision == "accepted":
        await db.evidence_quality_issues.update_many({"document_id": document_id, "status": "open"}, {"$set": {"status": "resolved", "resolved_at": _now(), "resolved_by": current.get("email")}})
    await audit_log(current["email"], "evidence_review", "evidence_document", document_id, {"decision": decision})
    return {"status": "ok", "review_id": rid, "as_of": _now()}

