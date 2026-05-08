"""Connector admin endpoints: create/test/sync/backfill/runs/health/errors."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.auth import get_current_user
from app.core.security import require_roles
from app.deps import db
from app.services import connector_service as cs

# Prefix is applied in ``main`` twice: ``/connectors`` and ``/integrations`` (SRS alias).
router = APIRouter(tags=["connectors"])


@router.get("/matrix")
async def connector_matrix(current=Depends(get_current_user)):
    """Wave 4 — connector catalog + configured instances (sync health overview)."""
    configured = await cs.list_connectors(db)
    catalog = [
        {"system": "SAP", "adapter": "mock_sap", "phase": "demo"},
        {"system": "Oracle ERP", "adapter": "mock_oracle", "phase": "demo"},
        {"system": "Tally", "adapter": "planned", "phase": "roadmap"},
        {"system": "NetSuite", "adapter": "planned", "phase": "roadmap"},
    ]
    return {
        "configured": configured,
        "catalog": catalog,
        "sync_policy": {"retries": 3, "backoff_seconds": 30, "idempotency": "run_id"},
    }


@router.post("")
async def create_connector(
    body: Dict[str, Any] = Body(...),
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head")),
):
    return await cs.create_connector(db, body, current["email"])


@router.post("/{connector_id}/activate")
async def activate_connector(
    connector_id: str,
    current=Depends(require_roles("CFO", "Internal Auditor", "Compliance Head")),
):
    from app.services.governance_approval_service import require_approval_or_raise

    await require_approval_or_raise(db, action="connector_activation", subject_type="connector", subject_id=connector_id)
    await db.source_connectors.update_one({"id": connector_id}, {"$set": {"status": "active"}})
    from app.deps import audit_log
    await audit_log(current["email"], "connector_activate", "connector", connector_id)
    c = await cs.get_connector(db, connector_id)
    if not c:
        raise HTTPException(404, "Connector not found")
    return c


@router.get("")
async def list_connectors(current=Depends(get_current_user)):
    return await cs.list_connectors(db)


@router.get("/sync-logs")
async def integrations_sync_logs(
    connector_id: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=2000),
    current=Depends(get_current_user),
):
    """Phase 38 — global sync logs (connector runs)."""
    q: Dict[str, Any] = {}
    if connector_id:
        q["connector_id"] = connector_id
    cur = db.connector_runs.find(q, {"_id": 0}).sort("run_start", -1).limit(limit)
    items = [r async for r in cur]
    return {"items": items, "count": len(items)}


@router.patch("/{connector_id}")
async def update_connector(
    connector_id: str,
    body: Dict[str, Any] = Body(...),
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head")),
):
    """Phase 38 — partial update of a configured connector instance."""
    c = await cs.get_connector(db, connector_id)
    if not c:
        raise HTTPException(404, "Connector not found")
    patch = {k: v for k, v in (body or {}).items() if k in {"name", "status", "domains", "config", "credentials_ref"}}
    if not patch:
        return c
    from datetime import datetime, timezone
    from app.utils.timeutil import iso_utc
    patch["updated_at"] = iso_utc(datetime.now(timezone.utc))
    patch["updated_by"] = current["email"]
    await db.source_connectors.update_one({"id": connector_id}, {"$set": patch})
    from app.deps import audit_log
    await audit_log(current["email"], "connector_update", "connector", connector_id, patch)
    return await cs.get_connector(db, connector_id)


@router.get("/{connector_id}")
async def get_connector(connector_id: str, current=Depends(get_current_user)):
    c = await cs.get_connector(db, connector_id)
    if not c:
        raise HTTPException(404, "Connector not found")
    return c


@router.post("/{connector_id}/test")
async def test_connector(
    connector_id: str,
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head")),
):
    return await cs.test_connector(db, connector_id)


@router.post("/{connector_id}/sync")
async def sync_connector(
    connector_id: str,
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head")),
):
    return await cs.run_sync(db, connector_id, mode="sync", initiated_by=current["email"])


@router.post("/{connector_id}/backfill")
async def backfill_connector(
    connector_id: str,
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head")),
):
    return await cs.run_sync(db, connector_id, mode="backfill", initiated_by=current["email"])


@router.get("/{connector_id}/runs")
async def connector_runs(connector_id: str, current=Depends(get_current_user)):
    return await cs.list_runs(db, connector_id)


@router.get("/{connector_id}/health")
async def connector_health(connector_id: str, current=Depends(get_current_user)):
    # health = test + last run summary
    c = await cs.get_connector(db, connector_id)
    if not c:
        raise HTTPException(404, "Connector not found")
    last = (await cs.list_runs(db, connector_id))[:1]
    return {"connector": c, "last_run": last[0] if last else None}


@router.get("/{connector_id}/errors")
async def connector_errors(connector_id: str, current=Depends(get_current_user)):
    return await cs.list_errors(db, connector_id)

