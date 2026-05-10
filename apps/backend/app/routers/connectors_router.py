"""Connector admin endpoints: create/test/sync/backfill/runs/health/errors."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.auth import get_current_user
from app.core.entity_scope import entity_scope_enforced
from app.core.security import require_roles
from app.deps import db
from app.services import connector_service as cs
from app.services.rbac_service import assert_connector_entity_scope, enforce_entity_scope

# Prefix is applied in ``main`` twice: ``/connectors`` and ``/integrations`` (SRS alias).
router = APIRouter(tags=["connectors"])


_SECRET_KEY_TOKENS = ("secret", "token", "password", "api_key", "apikey", "access_key", "private_key")


def _redact_secrets(value: Any) -> Any:
    """Phase 38 — avoid leaking sensitive connector config in API responses."""
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for k, v in value.items():
            ks = str(k).lower()
            if any(t in ks for t in _SECRET_KEY_TOKENS) and ks != "env_key":
                out[k] = "***"
            else:
                out[k] = _redact_secrets(v)
        return out
    if isinstance(value, list):
        return [_redact_secrets(v) for v in value]
    return value


async def _connector_list_entity_code(current: dict) -> Optional[str]:
    if not await entity_scope_enforced(db):
        return None
    if current.get("role") == "Super Admin":
        return None
    user = await db.users.find_one({"id": current.get("user_id")}, {"_id": 0, "entity": 1})
    ue = (user or {}).get("entity")
    return str(ue).strip() if ue else None


def _sanitize_connector_doc(conn: Dict[str, Any]) -> Dict[str, Any]:
    """Return connector doc safe for general read endpoints."""
    if not conn:
        return conn
    out = dict(conn)
    if "config" in out:
        out["config"] = _redact_secrets(out.get("config") or {})
    if "credentials_ref" in out:
        out["credentials_ref"] = _redact_secrets(out.get("credentials_ref") or {})
    return out


@router.get("/matrix")
async def connector_matrix(
    entity_code: Optional[str] = Query(None, description="Legal entity key; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    """Wave 4 — connector catalog + configured instances (sync health overview)."""
    await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    ec = await _connector_list_entity_code(current)
    rows = await cs.list_connectors(db, entity_code=ec) if ec else await cs.list_connectors(db)
    configured = [_sanitize_connector_doc(c) for c in rows]
    catalog = [
        {
            "system": "SAP",
            "patterns": [
                {"id": "mock", "label": "Mock (CI / demo)", "auth": "env_ref | none"},
                {"id": "odata", "label": "S/4 OData / CDS + OAuth2", "auth": "env_ref | vault_ref"},
                {"id": "cpi_http", "label": "Integration Suite / API Gateway HTTPS", "auth": "vault_ref | static bearer"},
                {"id": "datasphere", "label": "Datasphere / BW snapshot URL", "auth": "vault_ref"},
            ],
            "config_key": "config.extra.connection_pattern",
            "phase": "enterprise",
        },
        {
            "system": "Oracle ERP",
            "patterns": [
                {"id": "mock", "label": "Mock (CI / demo)", "auth": "env_ref | none"},
                {"id": "fusion_rest", "label": "Fusion Cloud REST + OAuth2", "auth": "env_ref | vault_ref"},
                {"id": "ebs_integration", "label": "EBS via integration tier (HTTPS)", "auth": "vault_ref"},
                {"id": "oci_replica", "label": "OCI read model / OIC / ATP export", "auth": "vault_ref"},
            ],
            "config_key": "config.extra.connection_pattern",
            "phase": "enterprise",
        },
        {"system": "Tally", "adapter": "planned", "phase": "roadmap"},
        {"system": "NetSuite", "adapter": "planned", "phase": "roadmap"},
    ]
    return {
        "configured": configured,
        "catalog": catalog,
        "sync_policy": {
            "retries": 5,
            "backoff_seconds": "exponential",
            "max_pages_env": "CONNECTOR_SYNC_MAX_PAGES",
            "quarantine_env": "CONNECTOR_QUARANTINE_SCHEMA_FAILURES",
            "idempotency": "record_id upsert",
        },
    }


@router.post("")
async def create_connector(
    body: Dict[str, Any] = Body(...),
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head")),
):
    body = dict(body)
    cfg = dict(body.get("config") or {})
    ec_raw = (str(cfg.get("entity_code") or "")).strip() or None
    eff = await enforce_entity_scope(db, current=current, requested_entity_code=ec_raw)
    if eff:
        cfg["entity_code"] = eff
    body["config"] = cfg
    return _sanitize_connector_doc(await cs.create_connector(db, body, current["email"]))


@router.post("/{connector_id}/activate")
async def activate_connector(
    connector_id: str,
    current=Depends(require_roles("CFO", "Internal Auditor", "Compliance Head")),
):
    from app.services.governance_approval_service import require_approval_or_raise

    c0 = await cs.get_connector(db, connector_id)
    if not c0:
        raise HTTPException(404, "Connector not found")
    await assert_connector_entity_scope(db, current=current, connector=c0)
    cfg0 = c0.get("config") if isinstance(c0.get("config"), dict) else {}
    apr_ent = (str(cfg0.get("entity_code")).strip() if cfg0.get("entity_code") else None)
    await require_approval_or_raise(
        db,
        action="connector_activation",
        subject_type="connector",
        subject_id=connector_id,
        entity_code=apr_ent,
    )
    await db.source_connectors.update_one({"id": connector_id}, {"$set": {"status": "active"}})
    from app.deps import audit_log
    await audit_log(current["email"], "connector_activate", "connector", connector_id)
    c = await cs.get_connector(db, connector_id)
    if not c:
        raise HTTPException(404, "Connector not found")
    return _sanitize_connector_doc(c)


@router.get("")
async def list_connectors(
    entity_code: Optional[str] = Query(None, description="Legal entity key; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    ec = await _connector_list_entity_code(current)
    rows = await cs.list_connectors(db, entity_code=ec) if ec else await cs.list_connectors(db)
    return [_sanitize_connector_doc(c) for c in rows]


@router.get("/sync-logs")
async def integrations_sync_logs(
    connector_id: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=2000),
    entity_code: Optional[str] = Query(None, description="Legal entity key; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    """Phase 38 — global sync logs (connector runs)."""
    await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    q: Dict[str, Any] = {}
    ec = await _connector_list_entity_code(current)
    if ec:
        allowed = [c["id"] for c in await cs.list_connectors(db, entity_code=ec)]
        if connector_id:
            if connector_id not in allowed:
                raise HTTPException(403, "Entity scope violation")
            q["connector_id"] = connector_id
        else:
            if not allowed:
                return {"items": [], "count": 0}
            q["connector_id"] = {"$in": allowed}
    elif connector_id:
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
    await assert_connector_entity_scope(db, current=current, connector=c)
    patch = {k: v for k, v in (body or {}).items() if k in {"name", "status", "domains", "config", "credentials_ref"}}
    if "config" in patch and isinstance(patch["config"], dict):
        old_cfg = c.get("config") or {}
        merged = {**old_cfg, **patch["config"]}
        old_ex = dict(old_cfg.get("extra") or {})
        new_ex = dict((patch["config"].get("extra") or {}))
        merged["extra"] = {**old_ex, **new_ex}
        ec_in = (str(merged.get("entity_code") or "")).strip() or None
        merged["entity_code"] = await enforce_entity_scope(db, current=current, requested_entity_code=ec_in)
        patch["config"] = merged
    if not patch:
        return _sanitize_connector_doc(c)
    from datetime import datetime, timezone
    from app.utils.timeutil import iso_utc
    patch["updated_at"] = iso_utc(datetime.now(timezone.utc))
    patch["updated_by"] = current["email"]
    await db.source_connectors.update_one({"id": connector_id}, {"$set": patch})
    from app.deps import audit_log
    await audit_log(current["email"], "connector_update", "connector", connector_id, patch)
    out = await cs.get_connector(db, connector_id)
    return _sanitize_connector_doc(out) if out else out


@router.get("/{connector_id}")
async def get_connector(connector_id: str, current=Depends(get_current_user)):
    c = await cs.get_connector(db, connector_id)
    if not c:
        raise HTTPException(404, "Connector not found")
    await assert_connector_entity_scope(db, current=current, connector=c)
    return _sanitize_connector_doc(c)


@router.post("/{connector_id}/test")
async def test_connector(
    connector_id: str,
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head")),
):
    c = await cs.get_connector(db, connector_id)
    if not c:
        raise HTTPException(404, "Connector not found")
    await assert_connector_entity_scope(db, current=current, connector=c)
    return await cs.test_connector(db, connector_id)


@router.post("/{connector_id}/sync")
async def sync_connector(
    connector_id: str,
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head")),
):
    c = await cs.get_connector(db, connector_id)
    if not c:
        raise HTTPException(404, "Connector not found")
    await assert_connector_entity_scope(db, current=current, connector=c)
    return await cs.run_sync(db, connector_id, mode="sync", initiated_by=current["email"])


@router.post("/{connector_id}/backfill")
async def backfill_connector(
    connector_id: str,
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head")),
):
    c = await cs.get_connector(db, connector_id)
    if not c:
        raise HTTPException(404, "Connector not found")
    await assert_connector_entity_scope(db, current=current, connector=c)
    return await cs.run_sync(db, connector_id, mode="backfill", initiated_by=current["email"])


@router.get("/{connector_id}/runs")
async def connector_runs(
    connector_id: str,
    entity_code: Optional[str] = Query(None, description="Legal entity key; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    c = await cs.get_connector(db, connector_id)
    if not c:
        raise HTTPException(404, "Connector not found")
    await assert_connector_entity_scope(db, current=current, connector=c)
    return await cs.list_runs(db, connector_id)


@router.get("/{connector_id}/health")
async def connector_health(
    connector_id: str,
    entity_code: Optional[str] = Query(None, description="Legal entity key; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    # health = test + last run summary
    c = await cs.get_connector(db, connector_id)
    if not c:
        raise HTTPException(404, "Connector not found")
    await assert_connector_entity_scope(db, current=current, connector=c)
    last = (await cs.list_runs(db, connector_id))[:1]
    return {"connector": _sanitize_connector_doc(c), "last_run": last[0] if last else None}


@router.get("/{connector_id}/errors")
async def connector_errors(
    connector_id: str,
    entity_code: Optional[str] = Query(None, description="Legal entity key; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    c = await cs.get_connector(db, connector_id)
    if not c:
        raise HTTPException(404, "Connector not found")
    await assert_connector_entity_scope(db, current=current, connector=c)
    return await cs.list_errors(db, connector_id)

