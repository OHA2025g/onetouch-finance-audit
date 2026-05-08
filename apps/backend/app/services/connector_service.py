"""Connector orchestration: create/test/sync/backfill, run tracking, schema validation, DQ views."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.connectors.registry import get_adapter_class
from app.connectors.types import ConnectorConfig, ConnectorCredentialRef, ConnectorProvider, RunMode
from app.connectors.validation import validate_required_fields
from app.utils.timeutil import iso_utc


DEFAULT_DOMAINS: Dict[str, List[str]] = {
    "sap": ["vendors", "invoices", "payments", "journals", "purchase_orders", "goods_receipts"],
    "oracle_erp": ["customers", "ar_invoices", "sales_orders", "employees", "payroll_entries", "bank_transactions", "fixed_assets", "tax_records"],
}

DOMAIN_TO_COLLECTION: Dict[str, str] = {
    # phase 1
    "vendors": "vendors",
    "invoices": "invoices",
    "payments": "payments",
    "journals": "journals",
    "purchase_orders": "purchase_orders",
    "goods_receipts": "goods_receipts",
    # phase 2
    "customers": "customers",
    "sales_orders": "sales_orders",
    "ar_invoices": "ar_invoices",
    "employees": "employees",
    "payroll_entries": "payroll_entries",
    "bank_transactions": "bank_transactions",
    "fixed_assets": "fixed_assets",
    # tax_records stored alongside tax_filings if needed, but keep separate for now
    "tax_records": "tax_records",
}


def _parse_config(d: Dict[str, Any]) -> ConnectorConfig:
    return ConnectorConfig(
        entity_code=d.get("entity_code", "US-HQ"),
        base_currency=d.get("base_currency", "USD"),
        reporting_currency=d.get("reporting_currency", "USD"),
        extra=d.get("extra") or {},
    )


def _parse_cred_ref(d: Dict[str, Any]) -> ConnectorCredentialRef:
    kind = d.get("kind", "env_ref")
    env_key = d.get("env_key")
    return ConnectorCredentialRef(id=d.get("id") or f"cred-{uuid.uuid4().hex[:8]}", kind=kind, env_key=env_key)


async def create_connector(db, body: Dict[str, Any], user_email: str) -> Dict[str, Any]:
    now = iso_utc(datetime.now(timezone.utc))
    provider: str = body.get("provider")
    if provider not in ("sap", "oracle_erp"):
        from fastapi import HTTPException
        raise HTTPException(400, "Unsupported provider. Use 'sap' or 'oracle_erp'.")

    cid = body.get("id") or f"conn-{uuid.uuid4().hex[:10]}"
    config = body.get("config") or {}
    cred_ref = body.get("credentials_ref") or {"kind": "env_ref", "env_key": body.get("env_key")}
    domains = body.get("domains") or DEFAULT_DOMAINS[provider]
    doc = {
        "id": cid,
        "name": body.get("name") or f"{provider.upper()} connector",
        "provider": provider,
        "status": body.get("status", "inactive"),
        "domains": domains,
        "config": config,
        "credentials_ref": cred_ref,
        "created_at": now,
        "updated_at": now,
        "created_by": user_email,
        "last_run_at": None,
        "last_run_status": None,
    }
    await db.source_connectors.update_one({"id": cid}, {"$set": doc}, upsert=True)
    return await db.source_connectors.find_one({"id": cid}, {"_id": 0})  # type: ignore[return-value]


async def list_connectors(db) -> List[Dict[str, Any]]:
    return [c async for c in db.source_connectors.find({}, {"_id": 0}).sort("created_at", -1)]


async def get_connector(db, connector_id: str) -> Optional[Dict[str, Any]]:
    return await db.source_connectors.find_one({"id": connector_id}, {"_id": 0})


def _resolve_credentials(cred_ref: ConnectorCredentialRef) -> Dict[str, Any]:
    if cred_ref.kind == "none":
        return {"kind": "none"}
    if cred_ref.kind == "env_ref":
        if not cred_ref.env_key:
            return {"kind": "env_ref", "ok": False, "error": "env_key missing"}
        return {"kind": "env_ref", "ok": True, "env_key": cred_ref.env_key, "present": bool(os.environ.get(cred_ref.env_key))}
    return {"kind": cred_ref.kind, "ok": False, "error": "unknown kind"}


async def test_connector(db, connector_id: str) -> Dict[str, Any]:
    c = await get_connector(db, connector_id)
    if not c:
        from fastapi import HTTPException
        raise HTTPException(404, "Connector not found")
    provider: ConnectorProvider = c["provider"]
    adapter_cls = get_adapter_class(provider)
    cfg = _parse_config(c.get("config") or {})
    cred = _parse_cred_ref(c.get("credentials_ref") or {})
    adapter = adapter_cls(config=cfg, credentials=cred)
    health = await adapter.health_check()
    return {
        "connector": {"id": c["id"], "provider": provider, "name": c.get("name"), "domains": c.get("domains", [])},
        "credentials": _resolve_credentials(cred),
        "health": {"ok": health.ok, "message": health.message, "details": health.details},
    }


async def _start_run(db, connector: Dict[str, Any], mode: RunMode, initiated_by: str) -> Dict[str, Any]:
    now = iso_utc(datetime.now(timezone.utc))
    rid = f"run-{uuid.uuid4().hex[:10]}"
    run = {
        "id": rid,
        "connector_id": connector["id"],
        "provider": connector["provider"],
        "mode": mode,
        "status": "running",
        "run_start": now,
        "run_end": None,
        "initiated_by": initiated_by,
        "records_pulled": 0,
        "records_loaded": 0,
        "failures": 0,
        "retries": 0,
        "domains": connector.get("domains") or [],
        "schema_validations": [],
        "cursor_out": {},
    }
    await db.connector_runs.insert_one(dict(run))
    await db.source_connectors.update_one(
        {"id": connector["id"]},
        {"$set": {"last_run_at": now, "last_run_status": "running", "updated_at": now}},
    )
    return run


async def _finish_run(db, connector_id: str, run_id: str, status: str, patch: Dict[str, Any]) -> None:
    now = iso_utc(datetime.now(timezone.utc))
    await db.connector_runs.update_one(
        {"id": run_id},
        {"$set": {**patch, "status": status, "run_end": now}},
    )
    await db.source_connectors.update_one(
        {"id": connector_id},
        {"$set": {"last_run_status": status, "updated_at": now}},
    )


async def _record_error(db, *, connector_id: str, run_id: str, domain: str, stage: str, message: str, detail: Dict[str, Any] | None) -> None:
    now = iso_utc(datetime.now(timezone.utc))
    await db.connector_errors.insert_one(
        {
            "id": f"cerr-{uuid.uuid4().hex[:10]}",
            "connector_id": connector_id,
            "run_id": run_id,
            "domain": domain,
            "stage": stage,
            "message": message,
            "detail": detail or {},
            "created_at": now,
        }
    )


async def _upsert_records(db, collection: str, records: List[Dict[str, Any]]) -> int:
    loaded = 0
    for r in records:
        rid = r.get("id")
        if not rid:
            continue
        await db[collection].update_one({"id": rid}, {"$set": r}, upsert=True)
        loaded += 1
    return loaded


async def run_sync(db, connector_id: str, *, mode: RunMode, initiated_by: str) -> Dict[str, Any]:
    from app.deps import audit_log

    c = await get_connector(db, connector_id)
    if not c:
        from fastapi import HTTPException
        raise HTTPException(404, "Connector not found")
    provider: ConnectorProvider = c["provider"]
    adapter_cls = get_adapter_class(provider)
    cfg = _parse_config(c.get("config") or {})
    cred = _parse_cred_ref(c.get("credentials_ref") or {})
    adapter = adapter_cls(config=cfg, credentials=cred)

    run = await _start_run(db, c, mode, initiated_by)
    pulled = 0
    loaded = 0
    failures = 0
    schema_validations: List[Dict[str, Any]] = []
    cursor_out: Dict[str, Any] = {}

    for domain in (c.get("domains") or []):
        try:
            fr = await adapter.fetch_domain(domain=domain, cursor=None, mode=mode)
            pulled += len(fr.records)
            schema = adapter.expected_schema(domain)
            ok, report = validate_required_fields(schema, fr.records)
            schema_validations.append({"domain": domain, "ok": ok, "report": report})
            await db.connector_schemas.update_one(
                {"connector_id": connector_id, "domain": domain},
                {"$set": {"id": f"cs-{connector_id}-{domain}", "connector_id": connector_id, "domain": domain, "schema": schema, "last_validation": {"ok": ok, "report": report, "at": iso_utc(datetime.now(timezone.utc))}}},
                upsert=True,
            )
            if not ok:
                failures += report.get("violations", 0) or 1
                await _record_error(db, connector_id=connector_id, run_id=run["id"], domain=domain, stage="schema_validation", message="Schema validation failed", detail=report)
                continue
            normalized = [adapter.normalize(domain, r) for r in fr.records]
            coll = DOMAIN_TO_COLLECTION.get(domain, f"connector_{domain}")
            loaded += await _upsert_records(db, coll, normalized)
            cursor_out[domain] = fr.cursor
        except Exception as e:  # noqa: BLE001
            failures += 1
            await _record_error(db, connector_id=connector_id, run_id=run["id"], domain=domain, stage="fetch_or_load", message=str(e), detail={})

    status = "success" if failures == 0 else "partial"
    await _finish_run(
        db, connector_id, run["id"], status,
        {
            "records_pulled": pulled,
            "records_loaded": loaded,
            "failures": failures,
            "schema_validations": schema_validations,
            "cursor_out": cursor_out,
        },
    )
    await audit_log(initiated_by, "connector_run", "connector", connector_id, {"run_id": run["id"], "mode": mode, "status": status, "pulled": pulled, "loaded": loaded, "failures": failures})
    out = await db.connector_runs.find_one({"id": run["id"]}, {"_id": 0})
    return out  # type: ignore[return-value]


async def list_runs(db, connector_id: str) -> List[Dict[str, Any]]:
    return [r async for r in db.connector_runs.find({"connector_id": connector_id}, {"_id": 0}).sort("run_start", -1).limit(200)]


async def list_errors(db, connector_id: str) -> List[Dict[str, Any]]:
    return [e async for e in db.connector_errors.find({"connector_id": connector_id}, {"_id": 0}).sort("created_at", -1).limit(200)]


async def dq_health(db) -> Dict[str, Any]:
    connectors = await list_connectors(db)
    rows: List[Dict[str, Any]] = []
    for c in connectors:
        last_list = [r async for r in db.connector_runs.find({"connector_id": c["id"]}, {"_id": 0}).sort("run_start", -1).limit(1)]
        last = last_list[0] if last_list else None
        rows.append(
            {
                "connector": {"id": c["id"], "name": c.get("name"), "provider": c.get("provider"), "status": c.get("status")},
                "last_run": last,
            }
        )
    return {"connectors": rows}


async def dq_schema_validations(db, limit: int = 200) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    async for r in db.connector_runs.find({}, {"_id": 0, "id": 1, "connector_id": 1, "run_start": 1, "schema_validations": 1}).sort("run_start", -1).limit(limit):
        for sv in r.get("schema_validations") or []:
            out.append(
                {
                    "run_id": r["id"],
                    "connector_id": r["connector_id"],
                    "run_start": r.get("run_start"),
                    "domain": sv.get("domain"),
                    "ok": sv.get("ok"),
                    "report": sv.get("report"),
                }
            )
    return out[:limit]

