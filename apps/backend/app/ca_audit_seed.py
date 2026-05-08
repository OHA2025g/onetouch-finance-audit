"""Demo seed for CA audit modules (engagement, materiality, RACM, working papers)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from app.deps import iso
from app.services.ca_audit_domain import compute_benchmark_options, default_wp_folders, derive_performance_and_trivial, risk_scores
from app.services.ca_compliance_templates import compliance_rows_for_laws


def _now() -> str:
    return iso(datetime.now(timezone.utc))


async def seed_ca_audit_if_empty(db) -> Dict[str, Any]:
    """Idempotent: only inserts when audit_engagements is empty."""
    if await db.audit_engagements.count_documents({}) > 0:
        return {"status": "ca_audit_already_present"}

    t0 = datetime.now(timezone.utc)
    eid = "ENG-DEMO-IN-2025"
    due_near = iso(t0 + timedelta(days=7))
    due_mid = iso(t0 + timedelta(days=21))
    start_iso = iso(t0 - timedelta(days=30))
    end_iso = iso(t0 + timedelta(days=120))
    eng_doc: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "engagement_id": eid,
        "entity_name": "OneTouch India Services Pvt Ltd",
        "financial_year": "2024-25",
        "audit_type": "statutory",
        "audit_scope": "Ind AS financial statements and CARO reporting",
        "audit_objectives": ["Obtain reasonable assurance on FS", "Report on CARO clauses"],
        "start_date": start_iso,
        "end_date": end_iso,
        "audit_partner": "partner@onetouch.ai",
        "audit_manager": "auditor@onetouch.ai",
        "assigned_team": ["auditor@onetouch.ai", "controller@onetouch.ai"],
        "status": "in-progress",
        "risk_level": "high",
        "created_by": "system",
        "created_at": _now(),
        "updated_at": _now(),
        "milestones": [
            {"id": str(uuid.uuid4()), "title": "Planning sign-off", "due_date": due_near, "status": "pending", "owner_email": "auditor@onetouch.ai", "created_at": _now()},
            {"id": str(uuid.uuid4()), "title": "Fieldwork complete", "due_date": due_mid, "status": "pending", "owner_email": "auditor@onetouch.ai", "created_at": _now()},
        ],
        "team_members": [
            {"id": str(uuid.uuid4()), "user_email": "auditor@onetouch.ai", "role": "manager", "allocation_pct": 80.0, "added_at": _now()},
            {"id": str(uuid.uuid4()), "user_email": "controller@onetouch.ai", "role": "client_liaison", "allocation_pct": 20.0, "added_at": _now()},
        ],
        "planning_notes": [{"id": str(uuid.uuid4()), "note": "Demo engagement seeded for CA workflow.", "visibility": "team", "author_email": "system", "created_at": _now()}],
        "detailed_scopes": [{"id": str(uuid.uuid4()), "description": "Revenue and receivables", "process_area": "O2C", "financial_statement_area": "Revenue"}],
        "detailed_objectives": [{"id": str(uuid.uuid4()), "title": "Assess cut-off", "description": "Sales cut-off around year end"}],
        "timeline": {"planning_start": start_iso[:10], "fieldwork_start": (t0 + timedelta(days=14)).date().isoformat(), "fieldwork_end": (t0 + timedelta(days=90)).date().isoformat(), "reporting_date": end_iso[:10]},
    }

    eid2 = "ENG-GST-PLANNING-DEMO"
    overdue_end = iso(t0 - timedelta(days=14))
    eng2: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "engagement_id": eid2,
        "entity_name": "Demo Logistics LLP",
        "financial_year": "2025-26",
        "audit_type": "GST",
        "audit_scope": "GST reconciliation, GSTR-1/3B analytics, ITC review",
        "audit_objectives": ["Verify GST returns vs books", "Highlight ITC mismatches"],
        "start_date": iso(t0 - timedelta(days=60)),
        "end_date": overdue_end,
        "audit_partner": "partner@onetouch.ai",
        "audit_manager": "controller@onetouch.ai",
        "assigned_team": ["auditor@onetouch.ai"],
        "status": "planned",
        "risk_level": "critical",
        "created_by": "system",
        "created_at": _now(),
        "updated_at": _now(),
        "milestones": [
            {"id": str(uuid.uuid4()), "title": "GST data pull", "due_date": iso(t0 + timedelta(days=3)), "status": "pending", "owner_email": "auditor@onetouch.ai", "created_at": _now()},
        ],
        "team_members": [
            {"id": str(uuid.uuid4()), "user_email": "auditor@onetouch.ai", "role": "auditor", "allocation_pct": 100.0, "added_at": _now()},
        ],
        "planning_notes": [],
        "detailed_scopes": [{"id": str(uuid.uuid4()), "description": "Output tax vs GSTR-1", "process_area": "Record-to-report", "financial_statement_area": "Indirect taxes"}],
        "detailed_objectives": [{"id": str(uuid.uuid4()), "title": "ITC eligibility", "description": "Section 16 eligibility matrix"}],
        "timeline": {},
    }

    await db.audit_engagements.insert_many([dict(eng_doc), dict(eng2)])

    row = {"revenue": 120_000_000, "profit_before_tax": 8_000_000, "total_assets": 95_000_000, "gross_expenses": 102_000_000}
    opts = compute_benchmark_options(row)
    final_m = min(v for v in opts.values() if v > 0)
    lo, hi, trivial = derive_performance_and_trivial(final_m)
    await db.ca_materiality.insert_one(
        {
            "id": str(uuid.uuid4()),
            "engagement_id": eid,
            **row,
            "benchmark_options": opts,
            "benchmark_selected": "five_pct_pbt",
            "calculated_materiality": round(opts["five_pct_pbt"], 2),
            "final_materiality": round(final_m, 2),
            "performance_materiality_low": round(lo, 2),
            "performance_materiality_high": round(hi, 2),
            "performance_materiality": round((lo + hi) / 2, 2),
            "trivial_threshold": round(trivial, 2),
            "prepared_by": "auditor@onetouch.ai",
            "reviewed_by": "controller@onetouch.ai",
            "approved_by": "cfo@onetouch.ai",
            "approval_status": "approved",
            "updated_at": _now(),
        }
    )

    demo_risks = [
        {
            "risk_title": "Revenue cut-off",
            "risk_description": "Risk of revenue recorded in wrong period.",
            "process_area": "Order-to-Cash",
            "financial_statement_area": "Revenue",
            "risk_category": "Financial Reporting Risk",
            "likelihood_score": 4,
            "impact_score": 5,
            "control_effectiveness_score": 3,
            "linked_controls": [],
            "audit_procedures": ["Inspect shipping documents near year end"],
            "owner": "auditor@onetouch.ai",
            "status": "open",
        },
        {
            "risk_title": "Fraudulent disbursements",
            "risk_description": "Unauthorized payments or vendor master manipulation.",
            "process_area": "Procure-to-Pay",
            "financial_statement_area": "Trade payables",
            "risk_category": "Fraud Risk",
            "likelihood_score": 3,
            "impact_score": 5,
            "control_effectiveness_score": 2,
            "linked_controls": [],
            "audit_procedures": ["Bank confirmation", "Vendor verification"],
            "owner": "auditor@onetouch.ai",
            "status": "open",
        },
    ]
    seeded_risk_ids: list[str] = []
    for dr in demo_risks:
        rid = str(uuid.uuid4())
        seeded_risk_ids.append(rid)
        sc = risk_scores(dr["likelihood_score"], dr["impact_score"], dr["control_effectiveness_score"])
        await db.ca_risks.insert_one(
            {
                "id": rid,
                "engagement_id": eid,
                **dr,
                **sc,
                "created_at": _now(),
                "updated_at": _now(),
            }
        )

    await db.ca_wp_folders.insert_many([{**f, "engagement_id": eid} for f in default_wp_folders()])

    # Link a subset of existing cases/exceptions to demo engagement (best-effort)
    case_ids: list[str] = []
    cursor = db.cases.find({}, {"_id": 0, "id": 1, "exception_id": 1}).limit(5)
    async for c in cursor:
        case_ids.append(c["id"])
        await db.cases.update_one({"id": c["id"]}, {"$set": {"engagement_id": eid}})
        if c.get("exception_id"):
            await db.exceptions.update_one({"id": c["exception_id"]}, {"$set": {"engagement_id": eid}})

    await db.ca_working_papers.insert_one(
        {
            "id": str(uuid.uuid4()),
            "engagement_id": eid,
            "folder_id": "fld-1",
            "title": "Planning memo · scoping",
            "reference": "WP-PLN-001",
            "body": "Demo working paper linked to engagement.",
            "linked_risk_ids": seeded_risk_ids[:1],
            "linked_control_ids": [],
            "linked_case_ids": case_ids[:3],
            "evidence_ids": [],
            "created_at": _now(),
            "updated_at": _now(),
        }
    )

    obs_demo = [
        {
            "id": str(uuid.uuid4()),
            "engagement_id": eid,
            "title": "Revenue cut-off — heightened focus",
            "description": "Align shipping evidence with revenue recognition near year end.",
            "severity": "high",
            "material": True,
            "pervasive": False,
            "source": "fs",
            "source_id": None,
            "resolved": False,
            "created_at": _now(),
        },
        {
            "id": str(uuid.uuid4()),
            "engagement_id": eid,
            "title": "Case linkage — remediation tracking",
            "description": "Ensure management responses are logged for seeded audit cases.",
            "severity": "medium",
            "material": False,
            "pervasive": False,
            "source": "case",
            "source_id": case_ids[0] if case_ids else None,
            "resolved": False,
            "created_at": _now(),
        },
    ]
    await db.ca_audit_observations.insert_many([dict(x) for x in obs_demo])

    await db.ca_control_tests.insert_one(
        {
            "id": str(uuid.uuid4()),
            "engagement_id": eid,
            "test_type": "design effectiveness",
            "period": "2024-25",
            "tester_email": "auditor@onetouch.ai",
            "control_library_id": None,
            "control_id": None,
            "result": "pending",
            "evidence_refs": ["WP-PLN-001"],
            "notes": "Demo IFC-style test row; link evidence to working paper ref.",
            "created_at": _now(),
            "updated_at": _now(),
        }
    )

    reqs = compliance_rows_for_laws([])
    await db.ca_compliance_results.replace_one(
        {"engagement_id": eid},
        {
            "id": str(uuid.uuid4()),
            "engagement_id": eid,
            "requirements": reqs,
            "created_at": _now(),
            "updated_at": _now(),
        },
        upsert=True,
    )

    return {"status": "ca_audit_seeded", "engagement_id": eid}
