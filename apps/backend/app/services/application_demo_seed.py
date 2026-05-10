"""Idempotent synthetic/demo overlay for full-application evaluation (Docker + local).

Runs on startup unless ``SKIP_DEMO_OVERLAY=1``. Safe on production DBs: only inserts when
collections are empty (or upserts fixed ``*-demo-*`` connector ids).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from app.services.connector_service import DEFAULT_DOMAINS
from app.utils.timeutil import iso_utc


def _now() -> str:
    return iso_utc(datetime.now(timezone.utc))


async def _ensure_demo_connectors(db) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    now = _now()
    sap_id = "conn-demo-sap-evaluation"
    ora_id = "conn-demo-oracle-evaluation"
    sap = await db.source_connectors.find_one({"id": sap_id}, {"_id": 0})
    if not sap:
        await db.source_connectors.insert_one(
            {
                "id": sap_id,
                "name": "Demo SAP (mock OData pattern)",
                "provider": "sap",
                "status": "inactive",
                "domains": DEFAULT_DOMAINS["sap"],
                "config": {
                    "entity_code": "US-HQ",
                    "base_currency": "USD",
                    "reporting_currency": "USD",
                    "extra": {"connection_pattern": "mock", "source_system_label": "SAP-DEMO"},
                },
                "credentials_ref": {"kind": "none", "id": f"cred-{uuid.uuid4().hex[:8]}"},
                "created_at": now,
                "updated_at": now,
                "created_by": "system@onetouch.ai",
                "last_run_at": None,
                "last_run_status": None,
            }
        )
        out["sap_connector"] = "inserted"
    else:
        out["sap_connector"] = "present"

    ora = await db.source_connectors.find_one({"id": ora_id}, {"_id": 0})
    if not ora:
        await db.source_connectors.insert_one(
            {
                "id": ora_id,
                "name": "Demo Oracle ERP (mock Fusion pattern)",
                "provider": "oracle_erp",
                "status": "inactive",
                "domains": DEFAULT_DOMAINS["oracle_erp"],
                "config": {
                    "entity_code": "US-HQ",
                    "base_currency": "USD",
                    "reporting_currency": "USD",
                    "extra": {"connection_pattern": "mock", "source_system_label": "ORACLE-DEMO"},
                },
                "credentials_ref": {"kind": "none", "id": f"cred-{uuid.uuid4().hex[:8]}"},
                "created_at": now,
                "updated_at": now,
                "created_by": "system@onetouch.ai",
                "last_run_at": None,
                "last_run_status": None,
            }
        )
        out["oracle_connector"] = "inserted"
    else:
        out["oracle_connector"] = "present"
    return out


async def _ensure_demo_close_cycle(db) -> str:
    from app.services.close_service import create_cycle

    period = datetime.now(timezone.utc).strftime("%Y-%m")
    q = {"period_ym": period, "entity_code": "US-HQ"}
    if await db.close_cycles.find_one(q, {"_id": 0}):
        return "already_present"
    if await db.close_task_templates.count_documents({}) == 0:
        return "skipped_no_templates"
    await create_cycle(
        db,
        period_ym=period,
        name=f"Evaluation close — {period}",
        created_by="cfo@onetouch.ai",
        entity_code="US-HQ",
    )
    return f"created:{period}"


async def _ensure_demo_budget_forecast(db) -> Dict[str, str]:
    out: Dict[str, str] = {}
    bud_id = "bud-demo-evaluation-pack"
    if not await db.budget_versions.find_one({"id": bud_id}, {"_id": 0}):
        lines = [
            {"account_code": "6000", "gl_account": "6000", "amount": 1_250_000, "description": "OpEx — evaluation"},
            {"account_code": "6100", "gl_account": "6100", "amount": 420_000, "description": "IT & systems"},
            {"account_code": "7000", "gl_account": "7000", "amount": 3_100_000, "description": "Payroll"},
            {"account_code": "4000", "gl_account": "4000", "amount": 8_200_000, "description": "Revenue"},
        ]
        await db.budget_versions.insert_one(
            {
                "id": bud_id,
                "name": "FY26 Board evaluation budget",
                "entity": "US-HQ",
                "status": "approved",
                "locked": True,
                "lines": lines,
                "approved_by": "cfo@onetouch.ai",
                "approved_at": _now(),
                "created_at": _now(),
                "created_by": "cfo@onetouch.ai",
            }
        )
        out["budget"] = "inserted"
    else:
        out["budget"] = "present"

    fct_id = "fct-demo-evaluation-pack"
    if not await db.forecast_versions.find_one({"id": fct_id}, {"_id": 0}):
        await db.forecast_versions.insert_one(
            {
                "id": fct_id,
                "name": "FY26 rolling forecast (demo)",
                "entity": "US-HQ",
                "status": "active",
                "lines": [
                    {"account_code": "4000", "amount": 7_950_000},
                    {"account_code": "6000", "amount": 1_310_000},
                ],
                "created_at": _now(),
                "created_by": "controller@onetouch.ai",
            }
        )
        out["forecast"] = "inserted"
    else:
        out["forecast"] = "present"
    return out


async def _ensure_demo_budget_variances(db) -> str:
    from app.services.kpi_service import as_of_now

    q = {"entity": "US-HQ"}
    if await db.budget_variances.count_documents(q) > 0:
        return "present"
    b = await db.budget_versions.find_one({"id": "bud-demo-evaluation-pack"}, {"_id": 0})
    if not b:
        b = await db.budget_versions.find_one(q, {"_id": 0}, sort=[("created_at", -1)])
    if not b:
        return "skipped_no_budget"
    lines = b.get("lines") or []
    for i, ln in enumerate(lines[:20]):
        v_id = f"var-{b.get('id', 'bud')}-{i}"
        bud = float(ln.get("amount") or 0.0)
        act = round(bud * 0.9, 2)
        var = round(act - bud, 2)
        doc = {
            "id": v_id,
            "entity": b.get("entity"),
            "period_ym": ln.get("period_ym"),
            "gl_account": ln.get("gl_account"),
            "budget_amount": bud,
            "actual_amount": act,
            "variance": var,
            "abs_variance": abs(var),
            "status": "open",
            "comments": [],
            "created_at": as_of_now(),
        }
        await db.budget_variances.update_one({"id": v_id}, {"$setOnInsert": doc}, upsert=True)
    return f"upserted:{min(len(lines), 20)}"


async def ensure_application_demo_overlay(db) -> Dict[str, Any]:
    if os.environ.get("SKIP_DEMO_OVERLAY", "").lower() in ("1", "true", "yes", "on"):
        return {"status": "skipped", "reason": "SKIP_DEMO_OVERLAY"}

    actions: Dict[str, Any] = {"status": "ok"}

    # Integration hub — mock SAP / Oracle rows for UI matrix + test/sync flows.
    actions["connectors"] = await _ensure_demo_connectors(db)

    # Month-end close — one open cycle for current month when templates exist.
    actions["close_cycle"] = await _ensure_demo_close_cycle(db)

    # FP&A surfaces — budget + forecast versions for BvA / accuracy pages.
    actions["budget_forecast"] = await _ensure_demo_budget_forecast(db)
    actions["budget_variances"] = await _ensure_demo_budget_variances(db)

    # Legal + RPT + CA rules + board templates — reuse router seed helpers (empty-only inserts).
    try:
        from app.routers.continuous_audit_router import _ensure_seed_rules
        from app.routers.legal_router import _ensure_seed_legal
        from app.routers.rpt_router import _ensure_seed_rpt
        from app.routers.board_reporting_router import _ensure_seed_templates

        actions["legal"] = await _ensure_seed_legal(entity_code=None)
        actions["rpt"] = await _ensure_seed_rpt(entity_code=None)
        actions["continuous_audit_rules"] = await _ensure_seed_rules(entity_code=None)
        tpl = await _ensure_seed_templates()
        actions["report_templates"] = len(tpl or [])
    except Exception as e:  # noqa: BLE001
        actions["router_seeds_error"] = str(e)

    # CFO action queue — materialize candidates for default entity scope.
    try:
        from app.services import action_queue_service as aqs

        aq = await aqs.refresh_action_queue(db, entity_code="US-HQ", period_ym=None, department_id=None, cost_center_id=None)
        actions["action_queue_refresh"] = {"upserted": aq.get("upserted"), "candidates": len(aq.get("items") or [])}
    except Exception as e:  # noqa: BLE001
        actions["action_queue_error"] = str(e)

    return actions
