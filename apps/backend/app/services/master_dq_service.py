"""Master Data Quality (DQ) rules and findings store.

Scope: Phase 2 Unified finance model hardening (L4).

Produces deterministic, explainable findings for seeded demo data.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.utils.timeutil import iso_utc


def _now() -> str:
    return iso_utc(datetime.now(timezone.utc))


def _sev(rank: int) -> str:
    return {1: "critical", 2: "warning", 3: "info"}.get(rank, "info")


def _make(
    *,
    entity_code: Optional[str],
    master_type: str,
    object_id: str,
    rule_id: str,
    severity_rank: int,
    message: str,
    fields: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "at": _now(),
        "entity_code": entity_code,
        "master_type": master_type,
        "object_id": object_id,
        "rule_id": rule_id,
        "severity": _sev(severity_rank),
        "status": "open",
        "message": message,
        "fields": fields or {},
    }


def _key(master_type: str, object_id: str, rule_id: str) -> str:
    return f"{master_type}:{object_id}:{rule_id}"


async def recompute_findings(db, *, limit_per_type: int = 50_000) -> Dict[str, Any]:
    """Recompute and upsert findings. Uses (master_type, object_id, rule_id) as a natural key."""
    findings: List[Dict[str, Any]] = []

    # ---------------- Vendors ----------------
    vend_cur = db.vendors.find({}, {"_id": 0}).limit(limit_per_type)
    vendors = [v async for v in vend_cur]
    # duplicate detection by gstin/pan where present
    by_tax: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for v in vendors:
        gstin = (v.get("gstin") or "").strip().upper()
        pan = (v.get("pan") or "").strip().upper()
        ent = v.get("entity")
        if gstin:
            by_tax.setdefault(("gstin", gstin), []).append(v)
        if pan:
            by_tax.setdefault(("pan", pan), []).append(v)

        if not gstin and not pan:
            findings.append(
                _make(
                    entity_code=ent,
                    master_type="vendor",
                    object_id=str(v.get("id")),
                    rule_id="VENDOR_MISSING_TAX_ID",
                    severity_rank=2,
                    message="Vendor missing PAN/GSTIN",
                )
            )
        if not (v.get("ifsc") or "") and (v.get("bank_account_masked") or v.get("bank_account_number_masked")):
            findings.append(
                _make(
                    entity_code=ent,
                    master_type="vendor",
                    object_id=str(v.get("id")),
                    rule_id="VENDOR_MISSING_IFSC",
                    severity_rank=2,
                    message="Vendor bank details missing IFSC",
                )
            )

    for (kind, tax_id), rows in by_tax.items():
        if len(rows) > 1:
            for r in rows:
                findings.append(
                    _make(
                        entity_code=r.get("entity"),
                        master_type="vendor",
                        object_id=str(r.get("id")),
                        rule_id=f"VENDOR_DUPLICATE_{kind.upper()}",
                        severity_rank=1,
                        message=f"Duplicate vendor detected by {kind.upper()}={tax_id}",
                        fields={"tax_id": tax_id, "duplicates": [x.get("id") for x in rows if x.get("id") != r.get("id")]},
                    )
                )

    # ---------------- Customers ----------------
    cust_cur = db.customers.find({}, {"_id": 0}).limit(limit_per_type)
    customers = [c async for c in cust_cur]
    for c in customers:
        ent = c.get("entity")
        gstin = (c.get("gstin") or "").strip().upper()
        if not gstin:
            findings.append(
                _make(
                    entity_code=ent,
                    master_type="customer",
                    object_id=str(c.get("id")),
                    rule_id="CUSTOMER_MISSING_GSTIN",
                    severity_rank=3,
                    message="Customer missing GSTIN (if applicable)",
                )
            )
        cl = c.get("credit_limit")
        if cl is not None:
            try:
                if float(cl) < 0:
                    findings.append(
                        _make(
                            entity_code=ent,
                            master_type="customer",
                            object_id=str(c.get("id")),
                            rule_id="CUSTOMER_NEGATIVE_CREDIT_LIMIT",
                            severity_rank=2,
                            message="Customer credit limit is negative",
                            fields={"credit_limit": cl},
                        )
                    )
            except Exception:
                pass

    # ---------------- Employees ----------------
    emp_cur = db.employees.find({}, {"_id": 0}).limit(limit_per_type)
    employees = [e async for e in emp_cur]
    for e in employees:
        ent = e.get("entity")
        if not (e.get("email") or "").strip():
            findings.append(
                _make(
                    entity_code=ent,
                    master_type="employee",
                    object_id=str(e.get("id")),
                    rule_id="EMPLOYEE_MISSING_EMAIL",
                    severity_rank=3,
                    message="Employee missing email",
                )
            )
        if not (e.get("department") or "").strip():
            findings.append(
                _make(
                    entity_code=ent,
                    master_type="employee",
                    object_id=str(e.get("id")),
                    rule_id="EMPLOYEE_MISSING_DEPARTMENT",
                    severity_rank=2,
                    message="Employee missing department mapping",
                )
            )

    # ---------------- Bank accounts ----------------
    bank_cur = db.bank_accounts.find({}, {"_id": 0}).limit(limit_per_type)
    banks = [b async for b in bank_cur]
    seen_key: Dict[str, List[Dict[str, Any]]] = {}
    for b in banks:
        ent = b.get("entity")
        masked = b.get("account_number_masked") or b.get("account_number_mask") or b.get("account_number_masked")
        if not masked:
            findings.append(
                _make(
                    entity_code=ent,
                    master_type="bank_account",
                    object_id=str(b.get("id")),
                    rule_id="BANK_MISSING_MASKED_NUMBER",
                    severity_rank=2,
                    message="Bank account missing masked account number",
                )
            )
        if not (b.get("currency") or "").strip():
            findings.append(
                _make(
                    entity_code=ent,
                    master_type="bank_account",
                    object_id=str(b.get("id")),
                    rule_id="BANK_MISSING_CURRENCY",
                    severity_rank=3,
                    message="Bank account missing currency",
                )
            )
        k = f"{ent}:{masked}" if masked else None
        if k:
            seen_key.setdefault(k, []).append(b)
    for k, rows in seen_key.items():
        if len(rows) > 1:
            for r in rows:
                findings.append(
                    _make(
                        entity_code=r.get("entity"),
                        master_type="bank_account",
                        object_id=str(r.get("id")),
                        rule_id="BANK_DUPLICATE_MASKED",
                        severity_rank=2,
                        message=f"Duplicate bank account masked number for entity ({k})",
                    )
                )

    # ---------------- GL accounts ----------------
    gl_cur = db.master_gl_accounts.find({}, {"_id": 0}).limit(limit_per_type)
    gls = [g async for g in gl_cur]
    for g in gls:
        ent = g.get("entity_code")
        acct_type = (g.get("account_type") or "").strip().lower()
        if acct_type and acct_type not in ("asset", "liability", "revenue", "expense", "equity"):
            findings.append(
                _make(
                    entity_code=ent,
                    master_type="gl_account",
                    object_id=str(g.get("id")),
                    rule_id="GL_INVALID_ACCOUNT_TYPE",
                    severity_rank=3,
                    message="GL account has invalid account_type",
                    fields={"account_type": g.get("account_type")},
                )
            )

    # Upsert findings by natural key.
    now = _now()
    upserts = 0
    for f in findings:
        nk = _key(f["master_type"], f["object_id"], f["rule_id"])
        f["natural_key"] = nk
        f["computed_at"] = now
        await db.master_data_quality_findings.update_one({"natural_key": nk}, {"$set": dict(f)}, upsert=True)
        upserts += 1

    return {
        "status": "ok",
        "computed_at": now,
        "findings_upserted": upserts,
        "rules": [
            "VENDOR_MISSING_TAX_ID",
            "VENDOR_MISSING_IFSC",
            "VENDOR_DUPLICATE_GSTIN",
            "VENDOR_DUPLICATE_PAN",
            "CUSTOMER_MISSING_GSTIN",
            "CUSTOMER_NEGATIVE_CREDIT_LIMIT",
            "EMPLOYEE_MISSING_EMAIL",
            "EMPLOYEE_MISSING_DEPARTMENT",
            "BANK_MISSING_MASKED_NUMBER",
            "BANK_MISSING_CURRENCY",
            "BANK_DUPLICATE_MASKED",
            "GL_INVALID_ACCOUNT_TYPE",
        ],
    }


async def summary(db, *, entity_code: Optional[str] = None) -> Dict[str, Any]:
    """Counts by severity + master_type for open findings."""
    match: Dict[str, Any] = {"status": "open"}
    if entity_code:
        match["entity_code"] = entity_code
    pipeline = [
        {"$match": match},
        {"$group": {"_id": {"severity": "$severity", "master_type": "$master_type"}, "count": {"$sum": 1}}},
    ]
    rows = [r async for r in db.master_data_quality_findings.aggregate(pipeline)]
    by_sev: Dict[str, int] = {}
    by_type: Dict[str, int] = {}
    for r in rows:
        sev = r["_id"]["severity"]
        typ = r["_id"]["master_type"]
        by_sev[sev] = by_sev.get(sev, 0) + int(r["count"])
        by_type[typ] = by_type.get(typ, 0) + int(r["count"])
    return {"open_by_severity": by_sev, "open_by_type": by_type, "as_of": _now()}


async def list_findings(
    db,
    *,
    master_type: Optional[str] = None,
    severity: Optional[str] = None,
    entity_code: Optional[str] = None,
    status: str = "open",
    limit: int = 200,
    offset: int = 0,
) -> Dict[str, Any]:
    q: Dict[str, Any] = {}
    if status:
        q["status"] = status
    if master_type:
        q["master_type"] = master_type
    if severity:
        q["severity"] = severity
    if entity_code:
        q["entity_code"] = entity_code
    total = await db.master_data_quality_findings.count_documents(q)
    cur = db.master_data_quality_findings.find(q, {"_id": 0}).sort("severity", 1).skip(offset).limit(limit)
    items = [x async for x in cur]
    return {"items": items, "total": total, "limit": limit, "offset": offset}

