"""Phase 25 — Fixed Asset & Capex Audit Expansion (seed-friendly)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.deps import audit_log, db
from app.services.kpi_service import as_of_now


router = APIRouter(prefix="/fixed-assets-audit", tags=["fixed-assets-audit"])


def _now() -> str:
    return as_of_now()


def _parse_dt(s: Any) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:  # noqa: BLE001
        return None


async def _ensure_seed_assets(entity_code: Optional[str] = None) -> Dict[str, int]:
    """If Phase 2 isn't enabled, synthesize minimal FA/Dep/Capex data."""
    out = {"fixed_assets": 0, "depreciation_schedules": 0, "capex_projects": 0}
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code

    if await db.fixed_assets.count_documents(q) == 0:
        invs = [i async for i in db.invoices.find({"entity": entity_code} if entity_code else {}, {"_id": 0}).sort("invoice_date", -1).limit(80)]
        now = datetime.now(timezone.utc)
        docs = []
        for idx, inv in enumerate(invs[:18]):
            cost = round(float(inv.get("amount") or 0.0) * (5.0 if idx % 4 == 0 else 2.0), 2)
            life = 60 if idx % 3 else 36
            in_service = now - timedelta(days=365 * (1 + (idx % 5)))
            disposed = idx in (7, 12)
            docs.append(
                {
                    "id": f"FA-SYN-{idx}",
                    "asset_code": f"FA-SYN-{idx}",
                    "asset_name": f"Synth Asset #{idx}",
                    "entity": inv.get("entity") or entity_code or "US-HQ",
                    "category": "IT Hardware" if idx % 2 else "Plant & Machinery",
                    "cost": cost,
                    "useful_life_months": life,
                    "in_service_date": in_service.isoformat(),
                    "status": "disposed" if disposed else "in_service",
                    "disposed_at": (now - timedelta(days=90)).isoformat() if disposed else None,
                    "monthly_depreciation": round(cost / life, 2),
                }
            )
        if docs:
            await db.fixed_assets.insert_many(docs)
            out["fixed_assets"] = len(docs)

    if await db.depreciation_schedules.count_documents(q) == 0:
        now = datetime.now(timezone.utc)
        current_period = now.replace(day=1).strftime("%Y-%m")
        assets = [a async for a in db.fixed_assets.find(q, {"_id": 0}).limit(200)]
        docs = []
        for a in assets:
            # last 2 periods + a few "bad" rows for disposed assets
            for m in (1, 2):
                period = (now.replace(day=1) - timedelta(days=30 * m)).strftime("%Y-%m")
                docs.append(
                    {
                        "id": f"DEP-{a['id']}-{period}",
                        "asset_id": a["id"],
                        "period": period,
                        "amount": a.get("monthly_depreciation"),
                        "entity": a.get("entity"),
                        "posted_at": (now - timedelta(days=30 * m)).isoformat(),
                    }
                )
            if a.get("status") == "disposed":
                docs.append(
                    {
                        "id": f"DEP-BAD-{a['id']}-{current_period}",
                        "asset_id": a["id"],
                        "period": current_period,
                        "amount": a.get("monthly_depreciation"),
                        "entity": a.get("entity"),
                        "posted_at": (now - timedelta(days=2)).isoformat(),
                    }
                )
        if docs:
            await db.depreciation_schedules.insert_many(docs)
            out["depreciation_schedules"] = len(docs)

    if await db.capex_projects.count_documents(q) == 0:
        now = datetime.now(timezone.utc)
        docs = []
        for idx in range(8):
            budget = 500_000 + idx * 150_000
            actual = budget * (1.2 if idx < 2 else 0.8)
            docs.append(
                {
                    "id": f"CPX-SYN-{idx}",
                    "project_code": f"CPX-SYN-{idx}",
                    "project_name": f"Synth Capex Project {idx}",
                    "entity": entity_code or "US-HQ",
                    "budget_amount": round(budget, 2),
                    "actual_amount": round(actual, 2),
                    "start_date": (now - timedelta(days=180 + idx * 20)).isoformat(),
                    "status": "in_progress" if idx < 5 else "completed",
                    "sponsor": "controller@onetouch.ai",
                }
            )
        await db.capex_projects.insert_many(docs)
        out["capex_projects"] = len(docs)

    return out


@router.get("/summary")
async def fa_summary(entity_code: Optional[str] = Query(None), current=Depends(get_current_user)):
    await _ensure_seed_assets(entity_code=entity_code)
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    asset_count = await db.fixed_assets.count_documents(q)
    disposed = await db.fixed_assets.count_documents({**q, "status": "disposed"})
    capex_count = await db.capex_projects.count_documents(q)
    over_budget = 0
    async for p in db.capex_projects.find(q, {"_id": 0, "budget_amount": 1, "actual_amount": 1}):
        if float(p.get("actual_amount") or 0.0) > float(p.get("budget_amount") or 0.0):
            over_budget += 1
    return {
        "as_of": _now(),
        "entity_code": entity_code,
        "kpis": {"asset_count": asset_count, "disposed_assets": disposed, "capex_projects": capex_count, "capex_over_budget": over_budget},
        "source": "fixed_assets+depreciation_schedules+capex_projects",
    }


@router.get("/assets")
async def fa_assets(entity_code: Optional[str] = Query(None), limit: int = Query(200, ge=1, le=2000), offset: int = Query(0, ge=0), current=Depends(get_current_user)):
    await _ensure_seed_assets(entity_code=entity_code)
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    cur = db.fixed_assets.find(q, {"_id": 0}).sort("in_service_date", -1).skip(offset).limit(limit)
    items = [a async for a in cur]
    total = await db.fixed_assets.count_documents(q)
    return {"items": items, "total": total, "limit": limit, "offset": offset, "as_of": _now()}


@router.get("/depreciation-exceptions")
async def fa_depreciation_exceptions(entity_code: Optional[str] = Query(None), current=Depends(get_current_user)):
    await _ensure_seed_assets(entity_code=entity_code)
    now = datetime.now(timezone.utc)
    current_period = now.replace(day=1).strftime("%Y-%m")
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code

    assets = [a async for a in db.fixed_assets.find(q, {"_id": 0}).limit(400)]
    # Missing: in_service assets without current period dep
    missing = []
    for a in assets:
        if a.get("status") != "in_service":
            continue
        dep = await db.depreciation_schedules.find_one({"asset_id": a["id"], "period": current_period}, {"_id": 0})
        if not dep:
            missing.append(a)
    # Bad: disposed assets with current period dep
    bad = []
    async for dep in db.depreciation_schedules.find({**q, "period": current_period}, {"_id": 0}).limit(500):
        a = await db.fixed_assets.find_one({"id": dep.get("asset_id")}, {"_id": 0})
        if a and a.get("status") == "disposed":
            bad.append({"asset": a, "depreciation": dep})
    return {"as_of": _now(), "missing_depreciation": missing[:50], "disposed_depreciated": bad[:50], "note": "Exceptions based on current period vs depreciation_schedules"}


@router.get("/cwip-ageing")
async def fa_cwip_ageing(entity_code: Optional[str] = Query(None), current=Depends(get_current_user)):
    # Not modeled explicitly; surface stable placeholder.
    return {"as_of": _now(), "entity_code": entity_code, "items": [], "count": 0, "note": "Seed CWIP register to compute CWIP ageing."}


@router.get("/capex-overrun")
async def fa_capex_overrun(entity_code: Optional[str] = Query(None), limit: int = Query(50, ge=1, le=500), current=Depends(get_current_user)):
    await _ensure_seed_assets(entity_code=entity_code)
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    cur = db.capex_projects.find(q, {"_id": 0}).sort([("actual_amount", -1)]).limit(500)
    out = []
    async for p in cur:
        bud = float(p.get("budget_amount") or 0.0)
        act = float(p.get("actual_amount") or 0.0)
        if act > bud:
            out.append({**p, "overrun_amount": round(act - bud, 2), "overrun_pct": round(100.0 * (act - bud) / max(bud, 1.0), 2)})
    out.sort(key=lambda x: -float(x.get("overrun_amount") or 0.0))
    return {"items": out[:limit], "count": len(out), "as_of": _now()}


@router.get("/disposals")
async def fa_disposals(entity_code: Optional[str] = Query(None), limit: int = Query(50, ge=1, le=500), current=Depends(get_current_user)):
    await _ensure_seed_assets(entity_code=entity_code)
    q: Dict[str, Any] = {"status": "disposed"}
    if entity_code:
        q["entity"] = entity_code
    cur = db.fixed_assets.find(q, {"_id": 0}).sort("disposed_at", -1).limit(limit)
    items = [a async for a in cur]
    return {"items": items, "count": len(items), "as_of": _now()}


@router.post("/{asset_or_project_id}/create-case")
async def fa_create_case(asset_or_project_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    await _ensure_seed_assets()
    asset = await db.fixed_assets.find_one({"id": asset_or_project_id}, {"_id": 0})
    proj = None if asset else await db.capex_projects.find_one({"id": asset_or_project_id}, {"_id": 0})
    if not asset and not proj:
        raise HTTPException(404, "Asset/Project not found")

    now = _now()
    cid = f"case-fa-{__import__('uuid').uuid4().hex[:10]}"
    ex_id = f"fa-{asset_or_project_id}"
    entity = (asset or proj).get("entity") or current.get("entity") or "US-HQ"
    exposure = float(body.get("financial_exposure") or (proj.get("actual_amount") if proj else asset.get("cost")) or 0.0)

    ex_doc = {
        "id": ex_id,
        "control_id": "C-FA-003" if proj else "C-FA-001",
        "control_code": "FA-003" if proj else "FA-001",
        "control_name": "CapEx overrun" if proj else "Fixed asset audit follow-up",
        "process": "Fixed Assets",
        "entity": entity,
        "severity": str(body.get("severity") or "medium"),
        "status": "open",
        "materiality_score": float(body.get("materiality_score") or 0.4),
        "anomaly_score": float(body.get("anomaly_score") or 0.4),
        "financial_exposure": exposure,
        "source_record_type": "capex_project" if proj else "fixed_asset",
        "source_record_id": asset_or_project_id,
        "detected_at": now,
        "title": body.get("title") or (f"CapEx follow-up: {proj.get('project_name')}" if proj else f"Fixed asset follow-up: {asset.get('asset_name')}"),
        "summary": body.get("summary") or "Case created from Fixed Assets & Capex module.",
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
        "priority": body.get("priority") or "P2",
        "owner_email": body.get("owner_email") or current.get("email"),
        "owner_name": None,
        "due_date": body.get("due_date") or now,
        "financial_exposure": float(ex_doc.get("financial_exposure") or 0.0),
        "entity": ex_doc["entity"],
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
    await audit_log(current["email"], "fixed_assets_create_case", "case", cid, {"source_id": asset_or_project_id})
    return {"status": "ok", "case_id": cid, "exception_id": ex_id, "as_of": _now()}

