"""Phase 28 — Related Party Transaction (RPT) module (seed-friendly)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.deps import audit_log, db
from app.services.kpi_service import as_of_now
from app.services.rbac_service import enforce_entity_scope


router = APIRouter(prefix="/rpt", tags=["rpt"])


async def _ensure_seed_rpt(entity_code: Optional[str] = None) -> Dict[str, int]:
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code

    out = {"related_parties": 0, "rpt_transactions": 0}
    now = datetime.now(timezone.utc)

    if await db.related_parties.count_documents(q) == 0:
        parties = []
        base = [
            {"name": "Alpha Holdings Pvt Ltd", "relationship": "holding_company", "pan": "AAAAA1234A"},
            {"name": "Beta Trading LLP", "relationship": "associate", "pan": "BBBBB2345B"},
            {"name": "Gamma Services Pvt Ltd", "relationship": "subsidiary", "pan": "CCCCC3456C"},
            {"name": "Delta Family Trust", "relationship": "key_management", "pan": "DDDDD4567D"},
            {"name": "Epsilon Ventures", "relationship": "joint_venture", "pan": "EEEEE5678E"},
        ]
        for i, b in enumerate(base):
            parties.append(
                {
                    "id": f"RP-{9000+i}",
                    "entity": entity_code or ["IN-SVC", "UK-OPS", "SG-APAC"][i % 3],
                    "name": b["name"],
                    "relationship": b["relationship"],
                    "pan": b["pan"],
                    "gst": "27ABCDE1234F1Z5" if i % 2 == 0 else None,
                    "approval_required": True,
                    "active": True,
                    "created_at": as_of_now(),
                    "created_by": "controller@onetouch.ai",
                }
            )
        await db.related_parties.insert_many(parties)
        out["related_parties"] = len(parties)

    if await db.rpt_transactions.count_documents(q) == 0:
        parties = [p async for p in db.related_parties.find(q, {"_id": 0}).limit(50)]
        txns = []
        for i in range(22):
            rp = parties[i % len(parties)]
            amount = round(50_000 * (1 + (i % 7) * 0.9), 2)
            direction = "payable" if i % 2 == 0 else "receivable"
            txn_date = (now - timedelta(days=15 * (i % 10))).date().isoformat()
            tid = f"RPTX-{9500+i}"
            approved = i % 5 != 0
            settled = i % 6 == 0
            txns.append(
                {
                    "id": tid,
                    "entity": rp.get("entity"),
                    "related_party_id": rp["id"],
                    "related_party_name": rp["name"],
                    "transaction_type": ["sale", "purchase", "loan", "service", "lease"][i % 5],
                    "direction": direction,
                    "amount": amount,
                    "currency": "INR",
                    "transaction_date": txn_date,
                    "approval_status": "approved" if approved else "pending",
                    "approved_by": "cfo@onetouch.ai" if approved else None,
                    "approved_at": as_of_now() if approved else None,
                    "arm_length_doc": None,
                    "supporting_docs": [],
                    "settlement_status": "settled" if settled else "open",
                    "outstanding_amount": 0.0 if settled else amount * (0.4 if i % 3 == 0 else 1.0),
                    "created_at": as_of_now(),
                    "created_by": "controller@onetouch.ai",
                }
            )
        await db.rpt_transactions.insert_many(txns)
        out["rpt_transactions"] = len(txns)

    return out


@router.get("/related-parties")
async def rpt_related_parties(entity_code: Optional[str] = Query(None), q: Optional[str] = Query(None), limit: int = Query(200, ge=1, le=2000), offset: int = Query(0, ge=0), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_rpt(entity_code=entity_code)
    filt: Dict[str, Any] = {}
    if entity_code:
        filt["entity"] = entity_code
    if q and q.strip():
        rq = {"$regex": q.strip(), "$options": "i"}
        filt["$or"] = [{"name": rq}, {"relationship": rq}, {"id": rq}, {"pan": rq}]
    cur = db.related_parties.find(filt, {"_id": 0}).sort("name", 1).skip(offset).limit(limit)
    items = [x async for x in cur]
    total = await db.related_parties.count_documents(filt)
    return {"items": items, "total": total, "limit": limit, "offset": offset, "as_of": as_of_now()}


@router.post("/related-parties")
async def rpt_related_party_create(body: Dict[str, Any], current=Depends(get_current_user)):
    rid = f"RP-{__import__('uuid').uuid4().hex[:10]}"
    ent = str(body.get("entity") or body.get("entity_code") or "US-HQ")
    ent = await enforce_entity_scope(db, current=current, requested_entity_code=ent)
    doc = {
        "id": rid,
        "entity": ent,
        "name": body.get("name") or "Related Party",
        "relationship": body.get("relationship") or "associate",
        "pan": body.get("pan"),
        "gst": body.get("gst"),
        "approval_required": bool(body.get("approval_required", True)),
        "active": bool(body.get("active", True)),
        "created_at": as_of_now(),
        "created_by": current.get("email"),
    }
    await db.related_parties.insert_one(dict(doc))
    await audit_log(current["email"], "rpt_related_party_create", "related_party", rid, {"name": doc["name"]})
    return {"status": "ok", "related_party_id": rid, "as_of": as_of_now()}


@router.get("/transactions")
async def rpt_transactions(entity_code: Optional[str] = Query(None), related_party_id: Optional[str] = Query(None), approval_status: Optional[str] = Query(None), limit: int = Query(200, ge=1, le=5000), offset: int = Query(0, ge=0), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_rpt(entity_code=entity_code)
    filt: Dict[str, Any] = {}
    if entity_code:
        filt["entity"] = entity_code
    if related_party_id:
        filt["related_party_id"] = related_party_id
    if approval_status:
        filt["approval_status"] = approval_status
    cur = db.rpt_transactions.find(filt, {"_id": 0}).sort("transaction_date", -1).skip(offset).limit(limit)
    items = [x async for x in cur]
    total = await db.rpt_transactions.count_documents(filt)
    return {"items": items, "total": total, "limit": limit, "offset": offset, "as_of": as_of_now()}


@router.post("/transactions")
async def rpt_transaction_create(body: Dict[str, Any], current=Depends(get_current_user)):
    tid = f"RPTX-{__import__('uuid').uuid4().hex[:10]}"
    rp = None
    if body.get("related_party_id"):
        rp = await db.related_parties.find_one({"id": body["related_party_id"]}, {"_id": 0})
    amount = float(body.get("amount") or 0.0)
    resolved_ent = body.get("entity") or (rp.get("entity") if rp else "US-HQ")
    resolved_ent = await enforce_entity_scope(db, current=current, requested_entity_code=str(resolved_ent))
    doc = {
        "id": tid,
        "entity": resolved_ent,
        "related_party_id": body.get("related_party_id") or (rp.get("id") if rp else None),
        "related_party_name": body.get("related_party_name") or (rp.get("name") if rp else "Related Party"),
        "transaction_type": body.get("transaction_type") or "service",
        "direction": body.get("direction") or "payable",
        "amount": amount,
        "currency": body.get("currency") or "INR",
        "transaction_date": body.get("transaction_date") or datetime.now(timezone.utc).date().isoformat(),
        "approval_status": body.get("approval_status") or "pending",
        "approved_by": None,
        "approved_at": None,
        "arm_length_doc": None,
        "supporting_docs": [],
        "settlement_status": body.get("settlement_status") or "open",
        "outstanding_amount": float(body.get("outstanding_amount") or amount),
        "created_at": as_of_now(),
        "created_by": current.get("email"),
    }
    await db.rpt_transactions.insert_one(dict(doc))
    await audit_log(current["email"], "rpt_transaction_create", "rpt_transaction", tid, {"related_party_id": doc["related_party_id"]})
    return {"status": "ok", "transaction_id": tid, "as_of": as_of_now()}


@router.post("/transactions/{transaction_id}/approval")
async def rpt_transaction_approval(transaction_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    txn0 = await db.rpt_transactions.find_one({"id": transaction_id}, {"_id": 0, "entity": 1})
    if not txn0:
        raise HTTPException(404, "Transaction not found")
    if txn0.get("entity"):
        await enforce_entity_scope(db, current=current, requested_entity_code=txn0.get("entity"))
    decision = str(body.get("decision") or body.get("status") or "approved")
    if decision not in {"approved", "rejected", "pending"}:
        raise HTTPException(400, "Invalid approval decision")
    update = {
        "approval_status": decision,
        "approved_by": current.get("email"),
        "approved_at": as_of_now(),
        "approval_note": body.get("note"),
        "updated_at": as_of_now(),
    }
    res = await db.rpt_transactions.update_one({"id": transaction_id}, {"$set": update})
    await audit_log(current["email"], "rpt_transaction_approval", "rpt_transaction", transaction_id, {"decision": decision})
    return {"status": "ok", "matched": res.matched_count, "modified": res.modified_count, "as_of": as_of_now()}


@router.post("/transactions/{transaction_id}/document")
async def rpt_transaction_document(transaction_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    txn0 = await db.rpt_transactions.find_one({"id": transaction_id}, {"_id": 0, "entity": 1})
    if not txn0:
        raise HTTPException(404, "Transaction not found")
    if txn0.get("entity"):
        await enforce_entity_scope(db, current=current, requested_entity_code=txn0.get("entity"))
    doc_id = f"rptdoc-{__import__('uuid').uuid4().hex[:10]}"
    item = {
        "id": doc_id,
        "type": body.get("type") or "arm_length",
        "name": body.get("name") or "document",
        "uri": body.get("uri"),
        "uploaded_by": current.get("email"),
        "uploaded_at": as_of_now(),
        "meta": body.get("meta") or {},
    }
    # Store arm_length_doc separately for quick lookup, but also append to supporting_docs.
    update = {"$push": {"supporting_docs": item}, "$set": {"updated_at": as_of_now()}}
    if item["type"] == "arm_length":
        update["$set"]["arm_length_doc"] = item
    res = await db.rpt_transactions.update_one({"id": transaction_id}, update)
    await audit_log(current["email"], "rpt_transaction_document", "rpt_transaction", transaction_id, {"document_id": doc_id, "type": item["type"]})
    return {"status": "ok", "document_id": doc_id, "matched": res.matched_count, "modified": res.modified_count, "as_of": as_of_now()}


@router.get("/outstanding-balances")
async def rpt_outstanding_balances(entity_code: Optional[str] = Query(None), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_rpt(entity_code=entity_code)
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    cur = db.rpt_transactions.find(q, {"_id": 0}).limit(5000)
    agg: Dict[str, Dict[str, Any]] = {}
    async for t in cur:
        rp = t.get("related_party_id") or "UNKNOWN"
        name = t.get("related_party_name") or rp
        agg.setdefault(rp, {"related_party_id": rp, "related_party_name": name, "open_count": 0, "outstanding_payable": 0.0, "outstanding_receivable": 0.0})
        if t.get("settlement_status") == "settled":
            continue
        amt = float(t.get("outstanding_amount") or t.get("amount") or 0.0)
        agg[rp]["open_count"] += 1
        if t.get("direction") == "receivable":
            agg[rp]["outstanding_receivable"] += amt
        else:
            agg[rp]["outstanding_payable"] += amt
    rows = list(agg.values())
    for r in rows:
        r["outstanding_receivable"] = round(float(r["outstanding_receivable"]), 2)
        r["outstanding_payable"] = round(float(r["outstanding_payable"]), 2)
        r["net_outstanding"] = round(r["outstanding_receivable"] - r["outstanding_payable"], 2)
    rows.sort(key=lambda x: -abs(float(x.get("net_outstanding") or 0.0)))
    return {"items": rows, "count": len(rows), "as_of": as_of_now(), "entity_code": entity_code}


@router.get("/disclosure-checklist")
async def rpt_disclosure_checklist(entity_code: Optional[str] = Query(None), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_rpt(entity_code=entity_code)
    tx = await rpt_transactions(entity_code=entity_code, related_party_id=None, approval_status=None, limit=5000, offset=0, current=current)
    items = tx.get("items") or []
    missing_approval = [t for t in items if t.get("approval_status") != "approved"]
    missing_arm = [t for t in items if not t.get("arm_length_doc")]
    # Simple checklist items
    checklist = [
        {"key": "related_party_master_present", "status": "ok" if (await db.related_parties.count_documents({"entity": entity_code} if entity_code else {})) > 0 else "missing"},
        {"key": "transactions_present", "status": "ok" if len(items) > 0 else "missing"},
        {"key": "all_transactions_approved", "status": "ok" if len(missing_approval) == 0 else "attention", "count": len(missing_approval)},
        {"key": "arm_length_docs_present", "status": "ok" if len(missing_arm) == 0 else "attention", "count": len(missing_arm)},
    ]
    return {"as_of": as_of_now(), "entity_code": entity_code, "checklist": checklist, "sample_missing_approval": missing_approval[:25], "sample_missing_arm_length": missing_arm[:25]}


@router.get("/audit-committee-report")
async def rpt_audit_committee_report(entity_code: Optional[str] = Query(None), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_rpt(entity_code=entity_code)
    parties = await db.related_parties.count_documents({"entity": entity_code} if entity_code else {})
    tx = await rpt_transactions(entity_code=entity_code, related_party_id=None, approval_status=None, limit=5000, offset=0, current=current)
    items = tx.get("items") or []
    total_amount = round(sum(float(t.get("amount") or 0.0) for t in items), 2)
    pending = [t for t in items if t.get("approval_status") == "pending"]
    rejected = [t for t in items if t.get("approval_status") == "rejected"]
    out = await rpt_outstanding_balances(entity_code=entity_code, current=current)
    top_outstanding = (out.get("items") or [])[:10]
    return {
        "as_of": as_of_now(),
        "entity_code": entity_code,
        "headline": {
            "related_parties": parties,
            "transaction_count": len(items),
            "transaction_total_amount": total_amount,
            "pending_approvals": len(pending),
            "rejected": len(rejected),
        },
        "top_outstanding": top_outstanding,
        "notes": [
            "This report is synthesized from RPT master + transaction register.",
            "Replace proxy disclosure checks with statutory schedule mapping when legal template is implemented.",
        ],
    }

