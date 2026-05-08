"""Idempotent seed for Phase 2 unified master collections + synthetic lines/scores."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.utils.timeutil import iso_utc


def _now() -> str:
    return iso_utc(datetime.now(timezone.utc))


ENTITY_CODES = ["US-HQ", "UK-OPS", "IN-SVC", "SG-APAC"]
DEPT_NAMES = ["Finance", "Operations", "Engineering", "Sales", "HR", "IT"]


async def ensure_master_indexes(db) -> None:
    specs = [
        ("companies", [("id", 1)], True),
        ("master_business_units", [("entity_code", 1), ("code", 1)], True),
        ("master_locations", [("entity_code", 1), ("code", 1)], True),
        ("master_departments", [("entity_code", 1), ("code", 1)], True),
        ("master_cost_centers", [("entity_code", 1), ("code", 1)], True),
        ("master_gl_accounts", [("entity_code", 1), ("account_code", 1)], True),
        ("master_transaction_lines", [("transaction_id", 1), ("line_no", 1)], True),
        ("master_documents", [("entity_code", 1), ("id", 1)], False),
        ("finance_risk_scores", [("object_type", 1), ("object_id", 1)], False),
        ("master_data_audit_trail", [("at", -1)], False),
        # Phase 2 + L4 hardening
        ("vendors", [("entity", 1), ("vendor_code", 1)], False),
        ("customers", [("entity", 1), ("customer_code", 1)], False),
        ("employees", [("entity", 1), ("employee_code", 1)], False),
        ("bank_accounts", [("entity", 1), ("id", 1)], False),
        ("master_data_quality_findings", [("natural_key", 1)], True),
    ]
    for coll, keys, unique in specs:
        try:
            await db[coll].create_index(keys, unique=unique)
        except Exception:
            pass


async def ensure_finance_masters(db) -> Dict[str, Any]:
    """Populate master_* if empty. Safe on partially seeded DBs."""
    out: Dict[str, Any] = {"actions": []}

    await ensure_master_indexes(db)

    if not await db.companies.count_documents({}):
        await db.companies.insert_one(
            {
                "id": "COMP-ONETOUCH",
                "name": "OneTouch Finance Audit AI (Group)",
                "country": "US",
                "base_currency": "USD",
                "source": "master",
                "created_at": _now(),
            }
        )
        out["actions"].append("companies_inserted")

    if not await db.master_business_units.count_documents({}):
        bu: List[Dict[str, Any]] = []
        for ent in ENTITY_CODES:
            for i, label in enumerate(["Corporate", "Shared Services", "Regional Ops"]):
                code = f"{ent}-BU{i+1}"
                bu.append(
                    {
                        "id": str(uuid.uuid4()),
                        "code": code,
                        "name": f"{label} · {ent}",
                        "entity_code": ent,
                        "company_id": "COMP-ONETOUCH",
                        "active": True,
                    }
                )
        if bu:
            await db.master_business_units.insert_many(bu)
        out["actions"].append("business_units_seeded")

    if not await db.master_locations.count_documents({}):
        mapping = [
            ("US-HQ", "New York", "US"),
            ("UK-OPS", "London", "UK"),
            ("IN-SVC", "Mumbai", "IN"),
            ("SG-APAC", "Singapore", "SG"),
        ]
        locs = [
            {
                "id": str(uuid.uuid4()),
                "code": f"{ent}-LOC-{city[:3].upper()}",
                "name": f"{city} office",
                "entity_code": ent,
                "country": cc,
                "active": True,
            }
            for ent, city, cc in mapping
        ]
        await db.master_locations.insert_many(locs)
        out["actions"].append("locations_seeded")

    if not await db.master_departments.count_documents({}):
        depts = []
        for ent in ENTITY_CODES:
            for name in DEPT_NAMES:
                code = f"{ent}-D-{name[:3].upper()}"
                did = str(uuid.uuid4())
                depts.append(
                    {
                        "id": did,
                        "code": code,
                        "name": name,
                        "entity_code": ent,
                        "cost_center_id": None,
                        "active": True,
                    }
                )
        if depts:
            await db.master_departments.insert_many(depts)
        out["actions"].append("departments_seeded")

    if not await db.master_cost_centers.count_documents({}):
        ccs = []
        async for d in db.master_departments.find({}, {"_id": 0}):
            slug = "".join(ch for ch in d["name"] if ch.isalnum())[:6].upper() or "GEN"
            code = f"{d['entity_code']}-CC-{slug}"
            cid = str(uuid.uuid4())
            ccs.append(
                {
                    "id": cid,
                    "code": code,
                    "name": f"Cost pool · {d['name']}",
                    "entity_code": d["entity_code"],
                    "department_id": d["id"],
                    "active": True,
                }
            )
            await db.master_departments.update_one({"id": d["id"]}, {"$set": {"cost_center_id": cid}})
        if ccs:
            await db.master_cost_centers.insert_many(ccs)
        out["actions"].append("cost_centers_seeded")

    if not await db.master_gl_accounts.count_documents({}):
        gls = []
        templates = [
            ("1000", "Cash and bank", "asset"),
            ("2000", "Accounts payable", "liability"),
            ("4000", "Revenue — services", "revenue"),
            ("6000", "Payroll expense", "expense"),
            ("7000", "FX gain/loss", "expense"),
        ]
        for ent in ENTITY_CODES:
            for acct, name, typ in templates:
                code = f"{acct}-{ent}"
                gls.append(
                    {
                        "id": str(uuid.uuid4()),
                        "account_code": code,
                        "account_name": f"{name} ({ent})",
                        "entity_code": ent,
                        "account_type": typ,
                        "active": True,
                    }
                )
        if gls:
            await db.master_gl_accounts.insert_many(gls)
        out["actions"].append("gl_accounts_seeded")

    if not await db.master_transaction_lines.count_documents({}):
        lines: List[Dict[str, Any]] = []
        journals = await db.journals.find({}, {"_id": 0}).sort("posting_date", -1).limit(25).to_list(length=25)
        for j in journals:
            e = j.get("entity") or "US-HQ"
            amt = float(j.get("total_amount") or 0)
            half = round(amt / 2.0, 2) if amt else 1000.0
            tid = j.get("id")
            lines.append(
                {
                    "id": str(uuid.uuid4()),
                    "transaction_id": tid,
                    "line_no": 1,
                    "entity_code": e,
                    "account_code": f"1000-{e}",
                    "debit": half,
                    "credit": 0.0,
                    "description": "Auto-balanced demo line",
                }
            )
            lines.append(
                {
                    "id": str(uuid.uuid4()),
                    "transaction_id": tid,
                    "line_no": 2,
                    "entity_code": e,
                    "account_code": f"4000-{e}",
                    "debit": 0.0,
                    "credit": half,
                    "description": "Offset",
                }
            )
        if lines:
            await db.master_transaction_lines.insert_many(lines)
        out["actions"].append("transaction_lines_seeded")

    if not await db.master_documents.count_documents({}):
        docs = [
            {
                "id": str(uuid.uuid4()),
                "doc_type": "policy",
                "title": "Delegation of authority matrix (draft)",
                "entity_code": "US-HQ",
                "external_uri": "s3://onetouch-audit/policies/doa-v0.pdf",
            },
            {
                "id": str(uuid.uuid4()),
                "doc_type": "contract",
                "title": "Treasury ISDA master sample",
                "entity_code": "UK-OPS",
                "external_uri": None,
            },
        ]
        await db.master_documents.insert_many(docs)
        out["actions"].append("documents_seeded")

    if not await db.finance_risk_scores.count_documents({}):
        scores = []
        for ent in ENTITY_CODES:
            scores.append(
                {
                    "id": str(uuid.uuid4()),
                    "object_type": "entity",
                    "object_id": ent,
                    "entity_code": ent,
                    "score": 42.0 + hash(ent) % 40,
                    "band": "amber",
                    "drivers": ["open_exceptions_mix", "control_pass_rate_proxy"],
                }
            )
        await db.finance_risk_scores.insert_many(scores)
        out["actions"].append("risk_scores_seeded")

    if not await db.master_data_audit_trail.count_documents({}):
        await db.master_data_audit_trail.insert_one(
            {
                "id": str(uuid.uuid4()),
                "at": _now(),
                "actor_email": "system@onetouch.ai",
                "action": "masters.bootstrap",
                "resource_type": "finance_masters",
                "resource_id": "phase2",
                "detail": {"message": "Initial master data baseline created"},
            }
        )
        out["actions"].append("audit_trail_seeded")

    if not out["actions"]:
        out["status"] = "already_present"
    else:
        out["status"] = "seeded"
    return out
