"""Phase 31 — Policy compliance & attestation (seed-friendly)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.deps import audit_log, db
from app.services.kpi_service import as_of_now


router = APIRouter(prefix="/policies", tags=["policies"])


async def _ensure_seed_policies(entity_code: Optional[str] = None) -> Dict[str, int]:
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code

    out = {"policies": 0, "policy_attestations": 0, "policy_breaches": 0}
    now = datetime.now(timezone.utc)

    if await db.policies.count_documents({}) == 0:
        docs = [
            {
                "id": "POL-1001",
                "entity": "GLOBAL",
                "title": "Global AP Payment Policy v4.2",
                "category": "finance",
                "version": 4,
                "effective_date": (now - timedelta(days=120)).date().isoformat(),
                "status": "active",
                "clauses": ["Dual approval for payments > INR 250k", "No split payments to bypass DoA"],
                "storage_uri": "s3://onetouch-audit/policies/POL-1001.pdf",
                "created_at": as_of_now(),
                "created_by": "compliance@onetouch.ai",
            },
            {
                "id": "POL-1002",
                "entity": "GLOBAL",
                "title": "Manual Journal Entry Policy v3.0",
                "category": "finance",
                "version": 3,
                "effective_date": (now - timedelta(days=200)).date().isoformat(),
                "status": "active",
                "clauses": ["Require justification for manual JEs", "Review high-risk journals within 5 days"],
                "storage_uri": "s3://onetouch-audit/policies/POL-1002.pdf",
                "created_at": as_of_now(),
                "created_by": "compliance@onetouch.ai",
            },
            {
                "id": "POL-1003",
                "entity": "GLOBAL",
                "title": "Segregation of Duties Matrix v2.1",
                "category": "risk",
                "version": 2,
                "effective_date": (now - timedelta(days=260)).date().isoformat(),
                "status": "active",
                "clauses": ["No create-and-approve access", "Quarterly access certification required"],
                "storage_uri": "s3://onetouch-audit/policies/POL-1003.pdf",
                "created_at": as_of_now(),
                "created_by": "compliance@onetouch.ai",
            },
        ]
        await db.policies.insert_many(docs)
        out["policies"] = len(docs)

    if await db.policy_attestations.count_documents(q) == 0:
        # Basic per-user attestations (seed) — keep small and deterministic.
        docs = []
        for i, email in enumerate(["cfo@onetouch.ai", "controller@onetouch.ai", "compliance@onetouch.ai"]):
            for pol in ["POL-1001", "POL-1002", "POL-1003"]:
                docs.append(
                    {
                        "id": f"ATST-{pol}-{i}",
                        "entity": entity_code or "GLOBAL",
                        "policy_id": pol,
                        "user_email": email,
                        "status": "acknowledged" if i != 2 else "pending",
                        "acknowledged_at": as_of_now() if i != 2 else None,
                        "campaign_id": "CMP-SEED",
                        "created_at": as_of_now(),
                    }
                )
        await db.policy_attestations.insert_many(docs)
        out["policy_attestations"] = len(docs)

    if await db.policy_breaches.count_documents(q) == 0:
        # Create a few breaches tied to existing surfaces (AP splits, journal risk, DoA).
        docs = [
            {
                "id": "PBR-2001",
                "entity": entity_code or "US-HQ",
                "policy_id": "POL-1001",
                "policy_title": "Global AP Payment Policy v4.2",
                "breach_type": "split_payment",
                "severity": "high",
                "status": "open",
                "detected_at": as_of_now(),
                "source_record_type": "invoice",
                "source_record_id": "INV-20001",
                "summary": "Potential split payment pattern to bypass approval threshold.",
                "financial_exposure": 275000.0,
                "case_id": None,
            },
            {
                "id": "PBR-2002",
                "entity": entity_code or "US-HQ",
                "policy_id": "POL-1002",
                "policy_title": "Manual Journal Entry Policy v3.0",
                "breach_type": "late_review",
                "severity": "medium",
                "status": "open",
                "detected_at": as_of_now(),
                "source_record_type": "journal",
                "source_record_id": "JE-1002",
                "summary": "High-risk manual journal not reviewed within SLA.",
                "financial_exposure": 120000.0,
                "case_id": None,
            },
        ]
        await db.policy_breaches.insert_many(docs)
        out["policy_breaches"] = len(docs)

    return out


@router.get("")
async def policies_list(entity_code: Optional[str] = Query(None), category: Optional[str] = Query(None), status: Optional[str] = Query(None), current=Depends(get_current_user)):
    await _ensure_seed_policies(entity_code=entity_code)
    q: Dict[str, Any] = {}
    if entity_code:
        q["$or"] = [{"entity": entity_code}, {"entity": "GLOBAL"}]
    if category:
        q["category"] = category
    if status:
        q["status"] = status
    cur = db.policies.find(q, {"_id": 0}).sort("title", 1).limit(5000)
    items = [x async for x in cur]
    return {"items": items, "count": len(items), "as_of": as_of_now()}


@router.post("")
async def policies_create(body: Dict[str, Any], current=Depends(get_current_user)):
    pid = f"POL-{__import__('uuid').uuid4().hex[:10]}"
    doc = {
        "id": pid,
        "entity": body.get("entity") or "GLOBAL",
        "title": body.get("title") or "Policy",
        "category": body.get("category") or "finance",
        "version": int(body.get("version") or 1),
        "effective_date": body.get("effective_date") or datetime.now(timezone.utc).date().isoformat(),
        "status": body.get("status") or "draft",
        "clauses": body.get("clauses") or [],
        "storage_uri": body.get("storage_uri"),
        "created_at": as_of_now(),
        "created_by": current.get("email"),
    }
    await db.policies.insert_one(dict(doc))
    await audit_log(current["email"], "policy_create", "policy", pid, {"title": doc["title"], "category": doc["category"]})
    return {"status": "ok", "policy_id": pid, "as_of": as_of_now()}


@router.post("/{policy_id}/version")
async def policies_new_version(policy_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    pol = await db.policies.find_one({"id": policy_id}, {"_id": 0})
    if not pol:
        raise HTTPException(404, "Policy not found")
    new_version = int(pol.get("version") or 1) + 1
    nid = f"{policy_id}-v{new_version}"
    doc = {
        **pol,
        "id": nid,
        "version": new_version,
        "effective_date": body.get("effective_date") or datetime.now(timezone.utc).date().isoformat(),
        "status": body.get("status") or "active",
        "created_at": as_of_now(),
        "created_by": current.get("email"),
        "supersedes": policy_id,
    }
    if "title" in body:
        doc["title"] = body["title"]
    if "clauses" in body:
        doc["clauses"] = body["clauses"]
    if "storage_uri" in body:
        doc["storage_uri"] = body["storage_uri"]
    await db.policies.insert_one(dict(doc))
    await audit_log(current["email"], "policy_new_version", "policy", nid, {"supersedes": policy_id, "version": new_version})
    return {"status": "ok", "policy_id": nid, "as_of": as_of_now()}


@router.get("/attestations")
async def policy_attestations(entity_code: Optional[str] = Query(None), user_email: Optional[str] = Query(None), status: Optional[str] = Query(None), current=Depends(get_current_user)):
    await _ensure_seed_policies(entity_code=entity_code)
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    if user_email:
        q["user_email"] = user_email
    if status:
        q["status"] = status
    cur = db.policy_attestations.find(q, {"_id": 0}).sort("created_at", -1).limit(5000)
    items = [x async for x in cur]
    return {"items": items, "count": len(items), "as_of": as_of_now()}


@router.post("/attestation-campaign")
async def policy_attestation_campaign(body: Dict[str, Any], current=Depends(get_current_user)):
    """Create an attestation campaign and seed pending attestation rows."""
    cid = f"CMP-{__import__('uuid').uuid4().hex[:10]}"
    entity = body.get("entity") or "GLOBAL"
    policy_ids = body.get("policy_ids") or ["POL-1001", "POL-1002"]
    users = body.get("users") or ["controller@onetouch.ai", "cfo@onetouch.ai"]
    due_date = body.get("due_date") or (datetime.now(timezone.utc) + timedelta(days=14)).date().isoformat()
    camp = {"id": cid, "entity": entity, "policy_ids": policy_ids, "users": users, "due_date": due_date, "status": "active", "created_at": as_of_now(), "created_by": current.get("email")}
    await db.policy_attestation_campaigns.insert_one(dict(camp))
    # Insert pending attestations (idempotent-ish on id)
    inserted = 0
    for u in users:
        for pid in policy_ids:
            aid = f"ATST-{cid}-{pid}-{u}"
            doc = {"id": aid, "entity": entity, "policy_id": pid, "user_email": u, "status": "pending", "acknowledged_at": None, "campaign_id": cid, "created_at": as_of_now()}
            await db.policy_attestations.update_one({"id": aid}, {"$setOnInsert": doc}, upsert=True)
            inserted += 1
    await audit_log(current["email"], "policy_attestation_campaign_create", "policy_campaign", cid, {"policies": len(policy_ids), "users": len(users)})
    return {"status": "ok", "campaign_id": cid, "attestations_seeded": inserted, "as_of": as_of_now()}


@router.post("/{policy_id}/acknowledge")
async def policy_acknowledge(policy_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    """Acknowledge a policy (creates or updates attestation row)."""
    entity = body.get("entity") or "GLOBAL"
    campaign_id = body.get("campaign_id")
    user_email = body.get("user_email") or current.get("email")
    aid = body.get("attestation_id") or f"ATST-{policy_id}-{user_email}"
    update = {
        "id": aid,
        "entity": entity,
        "policy_id": policy_id,
        "user_email": user_email,
        "status": "acknowledged",
        "acknowledged_at": as_of_now(),
        "campaign_id": campaign_id,
        "updated_at": as_of_now(),
        "note": body.get("note"),
    }
    await db.policy_attestations.update_one({"id": aid}, {"$set": update}, upsert=True)
    await audit_log(current["email"], "policy_acknowledge", "policy_attestation", aid, {"policy_id": policy_id, "user_email": user_email})
    return {"status": "ok", "attestation_id": aid, "as_of": as_of_now()}


@router.get("/breaches")
async def policy_breaches(entity_code: Optional[str] = Query(None), status: Optional[str] = Query(None), policy_id: Optional[str] = Query(None), current=Depends(get_current_user)):
    await _ensure_seed_policies(entity_code=entity_code)
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    if status:
        q["status"] = status
    if policy_id:
        q["policy_id"] = policy_id
    cur = db.policy_breaches.find(q, {"_id": 0}).sort("detected_at", -1).limit(5000)
    items = [x async for x in cur]
    return {"items": items, "count": len(items), "as_of": as_of_now()}


@router.post("/breaches/{breach_id}/create-case")
async def policy_breach_create_case(breach_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    await _ensure_seed_policies(entity_code=None)
    breach = await db.policy_breaches.find_one({"id": breach_id}, {"_id": 0})
    if not breach:
        raise HTTPException(404, "Breach not found")

    now = as_of_now()
    cid = f"case-pol-{__import__('uuid').uuid4().hex[:10]}"
    ex_id = f"policy-breach-{breach_id}"
    entity = breach.get("entity") or body.get("entity") or current.get("entity") or "US-HQ"
    exposure = float(body.get("financial_exposure") or breach.get("financial_exposure") or 0.0)

    ex_doc = {
        "id": ex_id,
        "control_id": "C-POL-001",
        "control_code": "POL-BREACH-001",
        "control_name": "Policy breach follow-up",
        "process": "Compliance",
        "entity": entity,
        "severity": str(body.get("severity") or breach.get("severity") or "medium"),
        "status": "open",
        "materiality_score": float(body.get("materiality_score") or 0.5),
        "anomaly_score": float(body.get("anomaly_score") or 0.5),
        "financial_exposure": exposure,
        "source_record_type": "policy_breach",
        "source_record_id": breach_id,
        "detected_at": now,
        "title": body.get("title") or f"Policy breach: {breach.get('policy_title')}",
        "summary": body.get("summary") or str(breach.get("summary") or ""),
        "recurrence_count": 0,
        "department_id": None,
        "cost_center_id": None,
    }
    await db.exceptions.update_one({"id": ex_id}, {"$setOnInsert": ex_doc}, upsert=True)

    case_doc = {
        "id": cid,
        "exception_id": ex_id,
        "control_code": ex_doc["control_code"],
        "control_name": ex_doc["control_name"],
        "title": ex_doc["title"],
        "summary": ex_doc["summary"],
        "severity": ex_doc["severity"],
        "status": "open",
        "priority": body.get("priority") or ("P1" if ex_doc["severity"] == "high" else "P2"),
        "owner_email": body.get("owner_email") or current.get("email"),
        "owner_name": None,
        "due_date": body.get("due_date") or now,
        "financial_exposure": float(ex_doc.get("financial_exposure") or 0.0),
        "entity": entity,
        "process": ex_doc["process"],
        "detected_at": now,
        "opened_at": now,
        "closed_at": None,
        "root_cause_category": None,
        "engagement_id": None,
        "material_impact": body.get("material_impact"),
        "material_watch": None,
        "department_id": None,
        "cost_center_id": None,
    }
    await db.cases.insert_one(dict(case_doc))
    await db.policy_breaches.update_one({"id": breach_id}, {"$set": {"case_id": cid, "updated_at": now}})
    await audit_log(current["email"], "policy_breach_create_case", "case", cid, {"breach_id": breach_id, "policy_id": breach.get("policy_id")})
    return {"status": "ok", "case_id": cid, "exception_id": ex_id, "as_of": as_of_now()}

