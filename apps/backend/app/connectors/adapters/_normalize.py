"""Map ERP payloads to OneTouch normalized documents (entity_code, stable ids)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.utils.timeutil import iso_utc


def _now() -> str:
    return iso_utc(datetime.now(timezone.utc))


def normalize_vendor_sap(raw: Dict[str, Any], *, entity_code: str, source_system: str) -> Dict[str, Any]:
    code = raw.get("vendor_code") or raw.get("BusinessPartner") or raw.get("Supplier") or raw.get("id")
    name = raw.get("vendor_name") or raw.get("BusinessPartnerFullName") or raw.get("OrganizationBPName1") or ""
    rid = raw.get("id") or f"V-{code}"
    return {
        "id": str(rid),
        "vendor_code": str(code),
        "vendor_name": str(name)[:512],
        "entity": entity_code,
        "status": (raw.get("status") or raw.get("BusinessPartnerGrouping") or "active"),
        "created_at": raw.get("created_at") or raw.get("CreationDate") or _now(),
        "source_system": source_system,
        **{k: v for k, v in raw.items() if k not in ("id", "vendor_code", "vendor_name", "entity", "status", "created_at", "source_system")},
    }


def normalize_generic(domain: str, rec: Dict[str, Any], *, entity_code: str, source_system: str) -> Dict[str, Any]:
    out = dict(rec)
    out.setdefault("entity", entity_code)
    out.setdefault("source_system", source_system)
    out.setdefault("created_at", _now())
    if "id" not in out or not out["id"]:
        blob = str(sorted(out.items()))[:2000]
        out["id"] = hashlib.sha256(f"{domain}|{blob}".encode()).hexdigest()[:28]
    return out
