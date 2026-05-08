"""Synthetic demo data for the statutory audit workflow (ENG-DEMO-IN-2025).

Fills gaps so FS Hub, schedules, reporting, opinion, and aggregates have realistic
content without manual uploads. Idempotent: only inserts when collections are empty
for that engagement.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.deps import iso
from app.schemas import ca_audit as sch
from app.services import ca_report_opinion_engine as rpt_eng
from app.services import ca_schedule_audit as ca_sched
from app.services.ca_fs_validation import validate_trial_balance_upload

DEMO_EID = "ENG-DEMO-IN-2025"


def _now() -> str:
    return iso(datetime.now(timezone.utc))


def _balanced_tb_lines(trial_balance_id: str, engagement_id: str) -> List[Dict[str, Any]]:
    """Balanced trial balance (Dr = Cr) with IND-style codes for FS mapping."""
    rows = [
        ("1100", "Cash and bank balances", 50_000_000.0, 0.0),
        ("1200", "Trade receivables", 45_000_000.0, 0.0),
        ("2100", "Trade payables", 0.0, 30_000_000.0),
        ("2200", "Other current liabilities", 0.0, 20_000_000.0),
        ("3100", "Share capital", 0.0, 15_000_000.0),
        ("3200", "Reserves and surplus", 0.0, 40_000_000.0),
        ("4100", "Revenue from operations", 0.0, 120_000_000.0),
        ("5100", "Other operating expenses", 40_000_000.0, 0.0),
    ]
    lines: List[Dict[str, Any]] = []
    for code, name, dr, cr in rows:
        lines.append(
            {
                "id": str(uuid.uuid4()),
                "trial_balance_id": trial_balance_id,
                "engagement_id": engagement_id,
                "account_code": code,
                "account_name": name,
                "debit": dr,
                "credit": cr,
            }
        )
    return lines


async def ensure_synthetic_audit_bundle(db) -> Dict[str, Any]:
    """Upsert synthetic data for the demo engagement when missing."""
    out: Dict[str, Any] = {"engagement_id": DEMO_EID, "actions": []}

    eng = await db.audit_engagements.find_one({"engagement_id": DEMO_EID}, {"_id": 0})
    if not eng:
        out["status"] = "skipped_no_engagement"
        return out

    # ----- Trial balance + FS snapshot -----
    tb_count = await db.ca_trial_balance_lines.count_documents({"engagement_id": DEMO_EID})
    if tb_count == 0:
        tb_id = str(uuid.uuid4())
        lines = _balanced_tb_lines(tb_id, DEMO_EID)
        err, warn = validate_trial_balance_upload(lines)
        if err:
            out["trial_balance_error"] = err
            return out
        total_dr = sum(float(l.get("debit") or 0) for l in lines)
        total_cr = sum(float(l.get("credit") or 0) for l in lines)
        meta = {
            "id": tb_id,
            "engagement_id": DEMO_EID,
            "filename": "synthetic-seed-tb.csv",
            "rows": len(lines),
            "total_debit": round(total_dr, 2),
            "total_credit": round(total_cr, 2),
            "balanced": abs(total_dr - total_cr) < 0.01,
            "uploaded_by": "synthetic-seed@onetouch.ai",
            "uploaded_at": _now(),
            "validation_warnings": warn,
        }
        await db.ca_trial_balance.insert_one(dict(meta))
        await db.ca_trial_balance_lines.insert_many(lines)
        out["actions"].append("trial_balance_seeded")

    snap_n = await db.ca_fs_snapshots.count_documents({"engagement_id": DEMO_EID})
    if snap_n == 0 and await db.ca_trial_balance_lines.count_documents({"engagement_id": DEMO_EID}) > 0:
        # Lazy import avoids router cycles at module import time
        from app.routers.ca_audit_modules import _generate_fs_snapshot

        await _generate_fs_snapshot(
            DEMO_EID,
            sch.FinancialGenerateIn(mapping_profile="default_ind_as"),
            {"email": "synthetic-seed@onetouch.ai"},
        )
        out["actions"].append("fs_snapshot_generated")

    # ----- Schedule audit workbooks -----
    from app.routers.ca_audit_modules import _ensure_schedule_document

    for st in ca_sched.SCHEDULE_TYPES:
        doc = await db.ca_schedule_audit.find_one(
            {"engagement_id": DEMO_EID, "schedule_type": st}, {"_id": 0}
        )
        if not doc:
            await _ensure_schedule_document(DEMO_EID, st)
            out["actions"].append(f"schedule_{st}")

    # ----- IFC: deficiency row (for dashboards / opinion signals) -----
    if await db.ca_control_deficiencies.count_documents({"engagement_id": DEMO_EID}) == 0:
        test = await db.ca_control_tests.find_one({"engagement_id": DEMO_EID}, {"_id": 0})
        test_id = (test or {}).get("id") or str(uuid.uuid4())
        if not test:
            await db.ca_control_tests.insert_one(
                {
                    "id": test_id,
                    "engagement_id": DEMO_EID,
                    "test_type": "operating effectiveness",
                    "period": "2024-25",
                    "tester_email": "synthetic-seed@onetouch.ai",
                    "control_library_id": None,
                    "control_id": None,
                    "result": "ineffective",
                    "evidence_refs": ["WP-PLN-001"],
                    "notes": "Synthetic seed control test for IFC deficiency linkage.",
                    "created_at": _now(),
                    "updated_at": _now(),
                }
            )
        await db.ca_control_deficiencies.insert_one(
            {
                "id": str(uuid.uuid4()),
                "engagement_id": DEMO_EID,
                "control_test_id": test_id,
                "severity": "high",
                "description": "Segregation gap — payment initiator also approver (synthetic seed).",
                "create_case": False,
                "status": "open",
                "management_response": None,
                "closure_notes": None,
                "case_id": None,
                "created_at": _now(),
            }
        )
        out["actions"].append("control_deficiency_seeded")

    # ----- Extra working paper (reporting trail) -----
    wp_n = await db.ca_working_papers.count_documents({"engagement_id": DEMO_EID})
    if wp_n < 2:
        await db.ca_working_papers.insert_one(
            {
                "id": str(uuid.uuid4()),
                "engagement_id": DEMO_EID,
                "folder_id": "fld-2",
                "title": "FS analytical review — revenue & margin",
                "reference": "WP-FS-002",
                "body": "Synthetic analytical procedures: trend vs prior year, ratio analysis, enquiry of management.",
                "linked_risk_ids": [],
                "linked_control_ids": [],
                "linked_case_ids": [],
                "evidence_ids": [],
                "created_at": _now(),
                "updated_at": _now(),
            }
        )
        out["actions"].append("working_paper_fs_002")

    # ----- Opinion + final report (Reporting studio / tab) -----
    if await db.ca_audit_opinions.count_documents({"engagement_id": DEMO_EID}) == 0:
        obs = [o async for o in db.ca_audit_observations.find({"engagement_id": DEMO_EID}, {"_id": 0})]
        signals = await rpt_eng.gather_opinion_signals(db, DEMO_EID)
        rec = rpt_eng.recommend_opinion(obs, signals)
        await db.ca_audit_opinions.insert_one(
            {
                "id": str(uuid.uuid4()),
                "engagement_id": DEMO_EID,
                **rec,
                "generated_at": _now(),
                "inputs_snapshot": {
                    "entity": eng.get("entity_name"),
                    "signals": rec.get("signals_summary"),
                    "counts": rec.get("counts"),
                    "source": "synthetic_seed",
                },
            }
        )
        out["actions"].append("opinion_seeded")

    if await db.ca_final_reports.count_documents({"engagement_id": DEMO_EID}) == 0:
        opinion = await db.ca_audit_opinions.find_one(
            {"engagement_id": DEMO_EID}, {"_id": 0}, sort=[("generated_at", -1)]
        )
        obs = [o async for o in db.ca_audit_observations.find({"engagement_id": DEMO_EID}, {"_id": 0})]
        caro = await db.ca_caro_responses.find_one({"engagement_id": DEMO_EID}, {"_id": 0})
        signals = await rpt_eng.gather_opinion_signals(db, DEMO_EID)
        sections = rpt_eng.build_report_sections(eng, opinion, obs, caro, signals)
        now = _now()
        await db.ca_final_reports.insert_one(
            {
                "id": str(uuid.uuid4()),
                "engagement_id": DEMO_EID,
                "sections": sections,
                "approval_status": "draft",
                "status": "draft",
                "created_at": now,
                "updated_at": now,
                "source": "synthetic_seed",
            }
        )
        out["actions"].append("final_report_seeded")

    # ----- CARO responses stub (reporting annexure) -----
    row = await db.ca_caro_responses.find_one({"engagement_id": DEMO_EID}, {"_id": 0})
    if not row or not (row.get("responses") or []):
        await db.ca_caro_responses.replace_one(
            {"engagement_id": DEMO_EID},
            {
                "engagement_id": DEMO_EID,
                "responses": [
                    {
                        "clause_id": "3(i)",
                        "response": "Synthetic seed: fixed assets records maintained; sample tested.",
                        "status": "draft",
                    },
                    {
                        "clause_id": "3(ii)",
                        "response": "Synthetic seed: inventory procedures reviewed; no material exception noted.",
                        "status": "draft",
                    },
                ],
                "at": _now(),
            },
            upsert=True,
        )
        out["actions"].append("caro_responses_seeded")

    out["status"] = "ok" if out["actions"] else "noop_already_populated"
    return out
