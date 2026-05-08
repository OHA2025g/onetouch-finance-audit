"""Idempotent default hierarchy, currency rates, retention policy seeds."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.utils.timeutil import iso_utc


def _hierarchy_docs() -> List[Dict[str, Any]]:
    """4-level tree: org → region → legal entity; BUs are synthetic for drill (entity + process)."""
    root = "org-onetouch"
    return [
        {
            "id": root, "type": "organization", "code": "ONETOUCH-GROUP",
            "name": "OneTouch Group", "parent_id": None, "order": 0, "entity_code": None, "path": "ONETOUCH-GROUP",
        },
        {
            "id": "reg-americas", "type": "region", "code": "AMERICAS",
            "name": "Americas", "parent_id": root, "order": 0, "entity_code": None, "path": "ONETOUCH-GROUP/AMERICAS",
        },
        {
            "id": "reg-emea", "type": "region", "code": "EMEA",
            "name": "EMEA", "parent_id": root, "order": 1, "entity_code": None, "path": "ONETOUCH-GROUP/EMEA",
        },
        {
            "id": "reg-apac", "type": "region", "code": "APAC",
            "name": "APAC", "parent_id": root, "order": 2, "entity_code": None, "path": "ONETOUCH-GROUP/APAC",
        },
        {
            "id": "le-us", "type": "legal_entity", "code": "LE-US",
            "name": "OneTouch Global, Inc. (US HQ)", "parent_id": "reg-americas", "order": 0, "entity_code": "US-HQ",
            "path": "ONETOUCH-GROUP/AMERICAS/US-HQ",
        },
        {
            "id": "le-uk", "type": "legal_entity", "code": "LE-UK",
            "name": "OneTouch UK Operations Ltd", "parent_id": "reg-emea", "order": 0, "entity_code": "UK-OPS",
            "path": "ONETOUCH-GROUP/EMEA/UK-OPS",
        },
        {
            "id": "le-in", "type": "legal_entity", "code": "LE-IN",
            "name": "OneTouch India Services Pvt Ltd", "parent_id": "reg-apac", "order": 0, "entity_code": "IN-SVC",
            "path": "ONETOUCH-GROUP/APAC/IN-SVC",
        },
        {
            "id": "le-sg", "type": "legal_entity", "code": "LE-SG",
            "name": "OneTouch APAC Holdings Pte", "parent_id": "reg-apac", "order": 1, "entity_code": "SG-APAC",
            "path": "ONETOUCH-GROUP/APAC/SG-APAC",
        },
    ]


def _retention_policies() -> List[Dict[str, Any]]:
    now = iso_utc(datetime.now(timezone.utc))
    return [
        {
            "id": "rpol-case-default",
            "name": "Default cases", "artifact_type": "case", "retention_days": 2555, "scope": "global",
            "action": "archive", "legal_hold_protection": True, "active": True, "created_at": now, "updated_at": now,
        },
        {
            "id": "rpol-copilot-default",
            "name": "Copilot sessions", "artifact_type": "copilot_session", "retention_days": 90, "scope": "global",
            "action": "purge", "legal_hold_protection": True, "active": True, "created_at": now, "updated_at": now,
        },
        {
            "id": "rpol-auditlog-default",
            "name": "Audit log", "artifact_type": "audit_log", "retention_days": 2555, "scope": "global",
            "action": "archive", "legal_hold_protection": True, "active": True, "created_at": now, "updated_at": now,
        },
        {
            "id": "rpol-ingest-default",
            "name": "Ingestion runs", "artifact_type": "ingestion_run", "retention_days": 400, "scope": "global",
            "action": "purge", "legal_hold_protection": False, "active": True, "created_at": now, "updated_at": now,
        },
    ]


def _fx_rates() -> List[Dict[str, Any]]:
    now = iso_utc(datetime.now(timezone.utc))
    return [
        {"id": "fx-usd", "base": "USD", "quote": "USD", "rate": 1.0, "as_of": now, "source": "baseline"},
        {"id": f"fx-{uuid.uuid4().hex[:6]}", "base": "USD", "quote": "EUR", "rate": 0.92, "as_of": now, "source": "baseline"},
        {"id": f"fx-{uuid.uuid4().hex[:6]}", "base": "USD", "quote": "INR", "rate": 0.012, "as_of": now, "source": "baseline"},
        {"id": f"fx-{uuid.uuid4().hex[:6]}", "base": "USD", "quote": "SGD", "rate": 0.74, "as_of": now, "source": "baseline"},
    ]


async def ensure_governance_baseline(db) -> Dict[str, int]:
    """Create hierarchy, FX, retention if collections are empty. Safe to run every startup."""
    out: Dict[str, int] = {}
    if not await db.organization_hierarchy.count_documents({}):
        await db.organization_hierarchy.insert_many([dict(x) for x in _hierarchy_docs()])
        out["organization_hierarchy"] = len(_hierarchy_docs())
    for doc in _hierarchy_docs():
        if doc.get("entity_code"):
            await db.entity_group_map.update_one(
                {"entity_code": doc["entity_code"]},
                {"$set": {"hierarchy_node_id": doc["id"], "roll_up_path": doc.get("path")}}, upsert=True,
            )
    if not await db.reporting_currency_rates.count_documents({}):
        await db.reporting_currency_rates.insert_many(_fx_rates())
        out["reporting_currency_rates"] = len(_fx_rates())
    if not await db.retention_policies.count_documents({}):
        await db.retention_policies.insert_many(_retention_policies())
        out["retention_policies"] = len(_retention_policies())
    return out
