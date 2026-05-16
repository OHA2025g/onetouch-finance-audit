"""Map ERP payloads to OneTouch normalized documents (entity_code, stable ids)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from app.utils.timeutil import iso_utc

# Align with journal risk rules (JR-003) and seed data.
PRIVILEGED_JOURNAL_POSTERS = frozenset({"sysadmin@onetouch.ai", "gl.lead@onetouch.ai"})


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
    if domain == "journals":
        return normalize_journal(out)
    return out


def normalize_journal(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Canonical journal document for risk scoring and finance surfaces.

    Maps ERP aliases (amount, manual flags) to fields expected by ``_score_je``.
    Safe to call on already-normalized seed documents (idempotent).
    """
    out = dict(doc)

    if out.get("total_amount") is None:
        for key in ("amount", "Amount", "debit_amount", "line_amount", "document_amount"):
            raw = out.get(key)
            if raw is not None and raw != "":
                try:
                    out["total_amount"] = float(raw)
                    break
                except (TypeError, ValueError):
                    continue

    if not out.get("journal_number"):
        out["journal_number"] = out.get("document_number") or out.get("id")

    if out.get("is_manual") is None:
        jt = str(out.get("journal_type") or out.get("entry_type") or "").lower()
        if jt in ("manual", "adj", "adjustment", "top_side"):
            out["is_manual"] = True
        elif out.get("is_manual_entry") is not None:
            out["is_manual"] = bool(out.get("is_manual_entry"))
        elif out.get("manual") is not None:
            out["is_manual"] = bool(out.get("manual"))
        elif str(out.get("source_system") or "").upper().startswith("SAP"):
            # SAP integration path: treat as manual unless explicitly automated.
            out["is_manual"] = True
        else:
            out["is_manual"] = False

    if out.get("is_privileged_poster") is None:
        poster = out.get("created_by") or out.get("posted_by") or out.get("user_id")
        out["is_privileged_poster"] = str(poster) in PRIVILEGED_JOURNAL_POSTERS if poster else False

    if out.get("approver_email") is None and out.get("approved_by"):
        out["approver_email"] = out.get("approved_by")

    return out
