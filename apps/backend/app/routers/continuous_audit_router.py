"""Phase 35 — Continuous Audit Rules Engine (seed-friendly).

Implements a minimal rule registry + run surface that generates exceptions into `db.exceptions`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.deps import audit_log, db
from app.services.kpi_service import as_of_now
from app.services.rbac_service import enforce_entity_scope


router = APIRouter(prefix="/continuous-audit", tags=["continuous-audit"])


def _now() -> str:
    return as_of_now()


async def _ensure_seed_rules(entity_code: Optional[str] = None) -> Dict[str, int]:
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code

    out = {"continuous_audit_rules": 0, "continuous_audit_rule_runs": 0}
    if await db.continuous_audit_rules.count_documents(q) == 0:
        now = datetime.now(timezone.utc)
        rules = [
            {
                "id": "CAR-001",
                "entity": entity_code or "US-HQ",
                "name": "Payment after vendor bank change",
                "description": "Flag payments made within 14 days of vendor bank detail update.",
                "status": "active",
                "severity": "high",
                "rule_type": "vendor_bank_change_payment",
                "threshold_days": 14,
                "created_at": _now(),
                "created_by": "internal-audit@onetouch.ai",
                "updated_at": _now(),
            },
            {
                "id": "CAR-002",
                "entity": entity_code or "US-HQ",
                "name": "Split payments near approval threshold",
                "description": "Detect potential split invoices/payments to bypass DoA threshold.",
                "status": "active",
                "severity": "medium",
                "rule_type": "split_payment_pattern",
                "threshold_amount": 250000,
                "window_days": 7,
                "created_at": _now(),
                "created_by": "internal-audit@onetouch.ai",
                "updated_at": _now(),
            },
            {
                "id": "CAR-003",
                "entity": entity_code or "US-HQ",
                "name": "Off-hours large bank transfers",
                "description": "Flag large outbound transfers outside business hours.",
                "status": "active",
                "severity": "high",
                "rule_type": "bank_off_hours_large_outbound",
                "threshold_amount": 300000,
                "created_at": _now(),
                "created_by": "internal-audit@onetouch.ai",
                "updated_at": _now(),
            },
        ]
        await db.continuous_audit_rules.insert_many(rules)
        out["continuous_audit_rules"] = len(rules)
    return out


@router.get("/rules")
async def ca_rules(entity_code: Optional[str] = Query(None), status: Optional[str] = Query(None), limit: int = Query(200, ge=1, le=5000), offset: int = Query(0, ge=0), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_rules(entity_code=entity_code)
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    if status:
        q["status"] = status
    cur = db.continuous_audit_rules.find(q, {"_id": 0}).sort("id", 1).skip(offset).limit(limit)
    items = [x async for x in cur]
    total = await db.continuous_audit_rules.count_documents(q)
    return {"items": items, "total": total, "limit": limit, "offset": offset, "as_of": _now()}


@router.get("/runs")
async def ca_runs_list(
    entity_code: Optional[str] = Query(None),
    rule_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current=Depends(get_current_user),
):
    """Recent rule runs for scheduler / ops visibility (failure modes surface via status + duration)."""
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    if rule_id:
        q["rule_id"] = rule_id
    cur = db.continuous_audit_rule_runs.find(q, {"_id": 0}).sort("started_at", -1).skip(offset).limit(limit)
    rows = [x async for x in cur]
    total = await db.continuous_audit_rule_runs.count_documents(q)
    failed = sum(1 for x in rows if (x.get("status") or "").lower() == "failed")
    return {
        "items": rows,
        "total": total,
        "limit": limit,
        "offset": offset,
        "failed_in_page": failed,
        "as_of": _now(),
    }


@router.post("/rules")
async def ca_rules_create(body: Dict[str, Any], current=Depends(get_current_user)):
    rid = f"CAR-{__import__('uuid').uuid4().hex[:8]}"
    ent = await enforce_entity_scope(
        db, current=current, requested_entity_code=(body.get("entity") or body.get("entity_code"))
    )
    doc = {
        "id": rid,
        "entity": ent or body.get("entity") or "US-HQ",
        "name": body.get("name") or "Continuous audit rule",
        "description": body.get("description") or "",
        "status": body.get("status") or "draft",
        "severity": body.get("severity") or "medium",
        "rule_type": body.get("rule_type") or "custom",
        "config": body.get("config") or {},
        "created_at": _now(),
        "created_by": current.get("email"),
        "updated_at": _now(),
    }
    await db.continuous_audit_rules.insert_one(dict(doc))
    await audit_log(current["email"], "continuous_audit_rule_create", "continuous_audit_rule", rid, {"rule_type": doc["rule_type"]})
    return {"status": "ok", "rule_id": rid, "as_of": _now()}


@router.patch("/rules/{rule_id}")
async def ca_rules_update(rule_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    r0 = await db.continuous_audit_rules.find_one({"id": rule_id}, {"_id": 0, "entity": 1})
    if r0 and r0.get("entity"):
        await enforce_entity_scope(db, current=current, requested_entity_code=r0.get("entity"))
    update = {k: v for k, v in body.items() if k in {"name", "description", "status", "severity", "config"}}
    update["updated_at"] = _now()
    update["updated_by"] = current.get("email")
    res = await db.continuous_audit_rules.update_one({"id": rule_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Rule not found")
    await audit_log(current["email"], "continuous_audit_rule_update", "continuous_audit_rule", rule_id, update)
    return {"status": "ok", "matched": res.matched_count, "modified": res.modified_count, "as_of": _now()}


async def _generate_exceptions(rule: Dict[str, Any], run_id: str) -> int:
    """Generate exceptions based on seeded data; idempotent-ish by exception id."""
    entity = rule.get("entity") or "US-HQ"
    rule_type = rule.get("rule_type")
    sev = rule.get("severity") or "medium"
    now = _now()
    inserted = 0

    def ex_id(suffix: str) -> str:
        return f"CAEX-{rule['id']}-{suffix}"

    if rule_type == "vendor_bank_change_payment":
        # Reuse Phase 19 logic surfaces; but for seed-friendly, look at vendors with bank_last_changed_at if present.
        vendors = [v async for v in db.vendors.find({"entity": entity}, {"_id": 0}).limit(1000)]
        for i, v in enumerate(vendors[:5]):
            eid = ex_id(f"V{i}")
            doc = {
                "id": eid,
                "control_id": f"adhoc-{rule['id']}",
                "control_code": rule["id"],
                "control_name": rule.get("name"),
                "process": "Procure-to-Pay",
                "entity": entity,
                "severity": sev,
                "status": "open",
                "materiality_score": 0.6 if sev == "high" else 0.4,
                "anomaly_score": 0.7,
                "financial_exposure": float(v.get("ytd_spend") or 0.0),
                "source_record_type": "continuous_audit_rule",
                "source_record_id": run_id,
                "detected_at": now,
                "title": f"{rule['name']} — {v.get('vendor_name') or v.get('id')}",
                "summary": "Seeded continuous audit finding based on vendor activity surfaces.",
                "recurrence_count": 0,
                "department_id": None,
                "cost_center_id": None,
            }
            res = await db.exceptions.update_one({"id": eid}, {"$setOnInsert": doc}, upsert=True)
            if res.upserted_id is not None:
                inserted += 1

    elif rule_type == "bank_off_hours_large_outbound":
        txns = [t async for t in db.bank_transactions.find({"entity": entity, "direction": "outbound"}, {"_id": 0}).limit(2000)]
        # pick a few large / off-hour transfers already seeded (BT-OFF-*)
        picks = [t for t in txns if str(t.get("id", "")).startswith("BT-OFF")][:5] or txns[:3]
        for i, t in enumerate(picks):
            eid = ex_id(f"BT{i}")
            exposure = float(t.get("amount") or 0.0)
            doc = {
                "id": eid,
                "control_id": f"adhoc-{rule['id']}",
                "control_code": rule["id"],
                "control_name": rule.get("name"),
                "process": "Treasury",
                "entity": entity,
                "severity": sev,
                "status": "open",
                "materiality_score": 0.7,
                "anomaly_score": 0.8,
                "financial_exposure": exposure,
                "source_record_type": "bank_transaction",
                "source_record_id": t.get("id"),
                "detected_at": now,
                "title": f"{rule['name']} — {t.get('reference') or t.get('id')}",
                "summary": "Outbound transfer flagged by continuous audit rule.",
                "recurrence_count": 0,
                "department_id": None,
                "cost_center_id": None,
            }
            res = await db.exceptions.update_one({"id": eid}, {"$setOnInsert": doc}, upsert=True)
            if res.upserted_id is not None:
                inserted += 1

    else:
        # generic placeholder exception
        eid = ex_id("GEN")
        doc = {
            "id": eid,
            "control_id": f"adhoc-{rule['id']}",
            "control_code": rule["id"],
            "control_name": rule.get("name"),
            "process": "Continuous Audit",
            "entity": entity,
            "severity": sev,
            "status": "open",
            "materiality_score": 0.4,
            "anomaly_score": 0.4,
            "financial_exposure": 0.0,
            "source_record_type": "continuous_audit_rule",
            "source_record_id": run_id,
            "detected_at": now,
            "title": f"{rule['name']} — placeholder finding",
            "summary": "Placeholder finding until rule is fully modeled.",
            "recurrence_count": 0,
            "department_id": None,
            "cost_center_id": None,
        }
        res = await db.exceptions.update_one({"id": eid}, {"$setOnInsert": doc}, upsert=True)
        if res.upserted_id is not None:
            inserted += 1

    return inserted


@router.post("/rules/{rule_id}/run")
async def ca_run(rule_id: str, body: Dict[str, Any] | None = None, current=Depends(get_current_user)):
    rule = await db.continuous_audit_rules.find_one({"id": rule_id}, {"_id": 0})
    if not rule:
        raise HTTPException(404, "Rule not found")
    if rule.get("entity"):
        await enforce_entity_scope(db, current=current, requested_entity_code=rule.get("entity"))
    run_id = f"CARUN-{__import__('uuid').uuid4().hex[:10]}"
    started = datetime.now(timezone.utc)
    run = {"id": run_id, "rule_id": rule_id, "entity": rule.get("entity"), "status": "running", "started_at": _now(), "started_by": current.get("email"), "params": body or {}}
    await db.continuous_audit_rule_runs.insert_one(dict(run))
    inserted = await _generate_exceptions(rule, run_id)
    ended = datetime.now(timezone.utc)
    dur_ms = int((ended - started).total_seconds() * 1000)
    await db.continuous_audit_rule_runs.update_one({"id": run_id}, {"$set": {"status": "completed", "ended_at": _now(), "duration_ms": dur_ms, "exceptions_created": inserted}})
    await audit_log(current["email"], "continuous_audit_rule_run", "continuous_audit_rule_run", run_id, {"rule_id": rule_id, "exceptions_created": inserted})
    return {"status": "ok", "run_id": run_id, "exceptions_created": inserted, "duration_ms": dur_ms, "as_of": _now()}


@router.get("/exceptions")
async def ca_exceptions(entity_code: Optional[str] = Query(None), limit: int = Query(200, ge=1, le=2000), offset: int = Query(0, ge=0), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_rules(entity_code=entity_code)
    q: Dict[str, Any] = {"status": {"$ne": "closed"}, "control_code": {"$regex": "^CAR-"}}
    if entity_code:
        q["entity"] = entity_code
    cur = db.exceptions.find(q, {"_id": 0}).sort("detected_at", -1).skip(offset).limit(limit)
    items = [x async for x in cur]
    total = await db.exceptions.count_documents(q)
    return {"items": items, "total": total, "limit": limit, "offset": offset, "as_of": _now()}


@router.post("/exceptions/{exception_id}/case")
async def ca_exception_create_case(exception_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    ex = await db.exceptions.find_one({"id": exception_id}, {"_id": 0})
    if not ex:
        raise HTTPException(404, "Exception not found")
    if ex.get("entity"):
        await enforce_entity_scope(db, current=current, requested_entity_code=ex.get("entity"))

    now = _now()
    cid = f"case-ca-{__import__('uuid').uuid4().hex[:10]}"
    # Ensure exception doc has required fields (defensive).
    await db.exceptions.update_one(
        {"id": exception_id},
        {
            "$set": {
                "status": ex.get("status") or "open",
                "severity": ex.get("severity") or "medium",
                "financial_exposure": float(ex.get("financial_exposure") or 0.0),
                "control_code": ex.get("control_code") or "CAR-UNKNOWN",
                "control_name": ex.get("control_name") or "Continuous audit rule finding",
                "process": ex.get("process") or "Continuous Audit",
                "entity": ex.get("entity") or "US-HQ",
                "detected_at": ex.get("detected_at") or now,
                "title": ex.get("title") or f"Continuous audit exception {exception_id}",
                "summary": ex.get("summary") or "",
                "updated_at": now,
            }
        },
    )

    case_doc = {
        "id": cid,
        "exception_id": exception_id,
        "control_code": ex.get("control_code") or "CAR-UNKNOWN",
        "control_name": ex.get("control_name") or "Continuous audit rule finding",
        "title": body.get("title") or ex.get("title") or f"Continuous audit exception {exception_id}",
        "summary": body.get("summary") or ex.get("summary") or "Case created from continuous audit exception.",
        "severity": str(body.get("severity") or ex.get("severity") or "medium"),
        "status": "open",
        "priority": body.get("priority") or ("P1" if (ex.get("severity") == "high") else "P2"),
        "owner_email": body.get("owner_email") or current.get("email"),
        "owner_name": None,
        "due_date": body.get("due_date") or now,
        "financial_exposure": float(ex.get("financial_exposure") or 0.0),
        "entity": ex.get("entity") or "US-HQ",
        "process": ex.get("process") or "Continuous Audit",
        "detected_at": ex.get("detected_at") or now,
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
    await audit_log(current["email"], "continuous_audit_exception_case_create", "case", cid, {"exception_id": exception_id})
    return {"status": "ok", "case_id": cid, "as_of": _now()}


@router.get("/rule-performance")
async def ca_rule_performance(entity_code: Optional[str] = Query(None), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_rules(entity_code=entity_code)
    q: Dict[str, Any] = {"entity": entity_code} if entity_code else {}
    rules = [r async for r in db.continuous_audit_rules.find(q, {"_id": 0}).limit(5000)]
    items = []
    for r in rules:
        rq = {"rule_id": r["id"]}
        if entity_code:
            rq["entity"] = entity_code
        runs = await db.continuous_audit_rule_runs.count_documents(rq)
        last = await db.continuous_audit_rule_runs.find_one(rq, {"_id": 0}, sort=[("started_at", -1)])
        open_ex = await db.exceptions.count_documents({"control_code": r["id"], "status": {"$ne": "closed"}})
        items.append(
            {
                "rule_id": r["id"],
                "name": r.get("name"),
                "status": r.get("status"),
                "severity": r.get("severity"),
                "run_count": runs,
                "last_run_at": (last or {}).get("started_at"),
                "last_duration_ms": (last or {}).get("duration_ms"),
                "open_exceptions": open_ex,
            }
        )
    items.sort(key=lambda x: (-int(x.get("open_exceptions") or 0), -int(x.get("run_count") or 0)))
    return {"items": items, "count": len(items), "as_of": _now()}

