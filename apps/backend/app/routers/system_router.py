"""Phase 40 — enterprise hardening endpoints.

These endpoints provide a stable, versionable surface for:
- system health checks
- audit log access
- security configuration (field masking / policy toggles)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.core.security import require_roles
from app.deps import db, iso

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health/live")
async def health_live():
    """Public liveness for load balancers (no auth). Deep dependency checks use ``GET /system/health``."""
    try:
        await db.command("ping")
    except Exception as e:
        raise HTTPException(503, f"Mongo ping failed: {type(e).__name__}")
    return {"status": "live", "service": "One Touch Audit AI"}


@router.get("/health")
async def system_health(current=Depends(require_roles("Super Admin"))):
    """Basic liveness + dependency checks (Mongo ping + collection counts)."""
    try:
        await db.command("ping")
    except Exception as e:
        raise HTTPException(503, f"Mongo ping failed: {type(e).__name__}")

    # Keep payload small and stable (frontend can render without knowing schema).
    counts: Dict[str, int] = {}
    for name in (
        "users",
        "controls",
        "exceptions",
        "cases",
        "audit_logs",
        "source_connectors",
    ):
        try:
            counts[name] = await db[name].count_documents({})
        except Exception:
            counts[name] = -1

    return {
        "status": "ok",
        "service": "One Touch Audit AI",
        "now": iso(datetime.now(timezone.utc)),
        "dependencies": {"mongo": "ok"},
        "counts": counts,
    }


@router.get("/audit-logs")
async def system_audit_logs(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    q: Optional[str] = Query(None, description="Substring search across actor/action/object"),
    actor: Optional[str] = Query(None),
    action_type: Optional[str] = Query(None),
    object_type: Optional[str] = Query(None),
    object_id: Optional[str] = Query(None),
    since_ts: Optional[str] = Query(None, description="ISO prefix match (e.g. 2026-05-01)"),
    until_ts: Optional[str] = Query(None, description="ISO prefix match (e.g. 2026-05-31)"),
    current=Depends(require_roles("Super Admin")),
):
    """Audit log listing for admin UX. Mirrors `/admin/audit-logs/query` but under `/system/*`."""
    filt: Dict[str, Any] = {}
    if q and q.strip():
        qq = q.strip()
        filt["$or"] = [
            {"actor_user_email": {"$regex": qq, "$options": "i"}},
            {"action_type": {"$regex": qq, "$options": "i"}},
            {"object_type": {"$regex": qq, "$options": "i"}},
            {"object_id": {"$regex": qq, "$options": "i"}},
        ]
    if actor and actor.strip():
        filt["actor_user_email"] = actor.strip()
    if action_type and action_type.strip():
        filt["action_type"] = action_type.strip()
    if object_type and object_type.strip():
        filt["object_type"] = object_type.strip()
    if object_id and object_id.strip():
        filt["object_id"] = object_id.strip()
    if since_ts and since_ts.strip():
        filt["event_ts"] = {**filt.get("event_ts", {}), "$gte": since_ts.strip()}
    if until_ts and until_ts.strip():
        filt["event_ts"] = {**filt.get("event_ts", {}), "$lte": until_ts.strip()}

    query = filt if filt else {}
    total = await db.audit_logs.count_documents(query)
    cur = (
        db.audit_logs.find(query, {"_id": 0})
        .sort("event_ts", -1)
        .skip(offset)
        .limit(limit)
    )
    items = [row async for row in cur]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/security-config")
async def get_security_config(current=Depends(require_roles("Super Admin"))):
    """Return the current security config singleton."""
    doc = await db.system_security_config.find_one({"id": "singleton"}, {"_id": 0})
    if not doc:
        return {
            "id": "singleton",
            "updated_at": None,
            "updated_by": None,
            "config": {
                "field_masking": {"enabled": False, "mask_email": True, "mask_bank_account": True},
                "rbac": {"entity_scope_enforced": False},
            },
        }
    return doc


@router.post("/security-config")
async def upsert_security_config(
    body: Dict[str, Any] = Body(...),
    current=Depends(require_roles("Super Admin")),
):
    """Update security configuration; stored as a singleton document."""
    cfg = body.get("config")
    if not isinstance(cfg, dict):
        raise HTTPException(400, "config must be an object")

    doc = {
        "id": "singleton",
        "updated_at": iso(datetime.now(timezone.utc)),
        "updated_by": current["email"],
        "config": cfg,
    }
    await db.system_security_config.update_one({"id": "singleton"}, {"$set": doc}, upsert=True)
    from app.deps import audit_log
    await audit_log(current["email"], "security_config_update", "system_security_config", "singleton", {"keys": list(cfg.keys())})
    return doc


@router.get("/org-backfill/status")
async def org_backfill_status(current=Depends(require_roles("Super Admin"))):
    """Slice 10 — Latest org-backfill run stats (transactions/exceptions/cases)."""
    doc = await db.system_org_backfill_runs.find_one({"id": "latest"}, {"_id": 0})
    return doc or {"id": "latest", "last_run_at": None, "last_run_by": None, "last_result": None}


@router.post("/org-backfill/run")
async def org_backfill_run(
    body: Dict[str, Any] = Body(default={}),
    current=Depends(require_roles("Super Admin")),
):
    """Slice 10 — Run org-backfill jobs on demand.

    Body:
    - targets: list of "transactions" | "exceptions" | "cases" (default all)
    - limit: optional int limit for exception/case backfill
    """
    targets = body.get("targets") or ["transactions", "exceptions", "cases"]
    if not isinstance(targets, list) or not targets:
        raise HTTPException(400, "targets must be a non-empty list")
    limit = int(body.get("limit") or 10_000)
    if limit < 1 or limit > 200_000:
        raise HTTPException(400, "limit out of range")

    result: Dict[str, Any] = {"targets": targets, "limit": limit}
    if "transactions" in targets:
        from app.services.org_backfill_service import backfill_transaction_org_fields

        result["transactions"] = await backfill_transaction_org_fields(db)
    if "exceptions" in targets:
        from app.controls_engine import backfill_exceptions_org_slice

        result["exceptions"] = await backfill_exceptions_org_slice(db, limit=limit)
    if "cases" in targets:
        from app.services.case_service import backfill_cases_org_from_exceptions

        result["cases"] = await backfill_cases_org_from_exceptions(db, limit=limit)

    doc = {
        "id": "latest",
        "last_run_at": iso(datetime.now(timezone.utc)),
        "last_run_by": current["email"],
        "last_result": result,
    }
    await db.system_org_backfill_runs.update_one({"id": "latest"}, {"$set": doc}, upsert=True)
    from app.deps import audit_log

    await audit_log(current["email"], "org_backfill_run", "system_org_backfill_runs", "latest", {"targets": targets, "limit": limit})
    return doc

