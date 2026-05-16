"""Application startup and shutdown: seeding, scheduler, DB client teardown."""
from __future__ import annotations
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.auth import hash_password
from app.controls_engine import run_all_controls, run_control
from app.deps import client, db, logger, iso
from app.notifier import (
    get_settings as get_notif_settings,
    scan_p0_action_queue,
    scan_sla_breaches,
    send_daily_brief,
)
from app.phase2 import seed_phase2
from app.seed import seed_database
from app.ca_audit_seed import repair_demo_audit_engagement_entity_codes, seed_ca_audit_if_empty
from app.services.ca_synthetic_audit_bundle import ensure_synthetic_audit_bundle
from app.services.case_service import case_from_exception
from app.governance.ensure_baseline import ensure_governance_baseline
from app.services.finance_masters_seed import ensure_finance_masters
from app.services.close_service import ensure_close_templates
from app.services.org_backfill_service import backfill_transaction_org_fields
scheduler: Optional[AsyncIOScheduler] = None


async def on_startup() -> None:
    global scheduler  # noqa: PLW0603 — module-level AsyncIOScheduler for graceful shutdown

    try:
        from app.db_indexes import ensure_workflow_indexes

        await ensure_workflow_indexes(db)
        logger.info("Workflow Mongo indexes ensured")
    except Exception as e:  # noqa: BLE001
        logger.warning("Workflow indexes skipped: %s", e)

    # 1) Phase 1 seed (idempotent)
    res = await seed_database(db, force=False)
    logger.info("Seed result: %s", res)
    try:
        ca = await seed_ca_audit_if_empty(db)
        if ca.get("status") == "ca_audit_seeded":
            logger.info("CA audit demo seeded: %s", ca.get("engagement_id"))
    except Exception as e:  # noqa: BLE001
        logger.warning("CA audit seed skipped: %s", e)
    try:
        rep = await repair_demo_audit_engagement_entity_codes(db)
        if rep.get("engagement_ids"):
            logger.info("CA audit demo entity_code repair: %s", rep.get("engagement_ids"))
    except Exception as e:  # noqa: BLE001
        logger.warning("CA audit entity_code repair skipped: %s", e)
    try:
        bundle = await ensure_synthetic_audit_bundle(db)
        if bundle.get("actions"):
            logger.info("Synthetic audit bundle: %s", bundle.get("actions"))
    except Exception as e:  # noqa: BLE001
        logger.warning("Synthetic audit bundle skipped: %s", e)
    gbl = await ensure_governance_baseline(db)
    if gbl:
        logger.info("Governance baseline: %s", gbl)

    try:
        fm = await ensure_finance_masters(db)
        if fm.get("actions"):
            logger.info("Finance master data: %s", fm)
    except Exception as e:  # noqa: BLE001
        logger.warning("Finance master data seed skipped: %s", e)

    try:
        ct = await ensure_close_templates(db)
        if ct.get("status") != "already_present":
            logger.info("Close task templates: %s", ct)
    except Exception as e:  # noqa: BLE001
        logger.warning("Close templates seed skipped: %s", e)

    # Slice 9 — ensure transactional docs carry org dims for master-scoped dashboards
    try:
        org = await backfill_transaction_org_fields(db)
        if any((org.get("updated") or {}).values()):
            logger.info("Org backfill: %s", org)
    except Exception as e:  # noqa: BLE001
        logger.warning("Org backfill skipped: %s", e)

    # Full-app evaluation overlay (connectors, close, FP&A variances, legal/RPT/CA seeds, action queue).
    # Set SKIP_DEMO_OVERLAY=1 to disable. seed_database() alone only runs on empty users — this fills gaps on warm DBs.
    try:
        from app.services.application_demo_seed import ensure_application_demo_overlay

        demo = await ensure_application_demo_overlay(db)
        if demo.get("status") != "skipped":
            logger.info("Application demo overlay: %s", demo)
    except Exception as e:  # noqa: BLE001
        logger.warning("Application demo overlay skipped: %s", e)

    # 2) Phase 2 seed (opt-in; keep baseline dataset stable unless explicitly enabled)
    if os.environ.get("ENABLE_PHASE2", "").lower() in ("1", "true", "yes", "on"):
        try:
            phase2 = await seed_phase2(db, force=False)
            logger.info("Phase 2 seed: %s", phase2)
            if phase2.get("phase2_controls_added", 0) > 0 or phase2.get("phase2_seeded") != "already_present":
                new_codes = [c["code"] for c in (await db.controls.find(
                    {"code": {"$regex": "^(C-OTC|C-PAY|C-TR-002|C-TR-003|C-TX-002|C-FA)"}}, {"_id": 0, "code": 1}
                ).to_list(length=None))]
                for code in new_codes:
                    ctrl = await db.controls.find_one({"code": code}, {"_id": 0})
                    if ctrl:
                        await run_control(db, ctrl)
                logger.info("Ran Phase 2 controls: %s", len(new_codes))
        except Exception as e:  # noqa: BLE001
            logger.warning("Phase 2 upgrade failed: %s", e)
    else:
        logger.info("Phase 2 seed skipped (set ENABLE_PHASE2=true to enable)")

    # 3) Super Admin user (upsert for databases seeded before this role existed)
    if not await db.users.find_one({"email": "superadmin@onetouch.ai"}, {"_id": 0}):
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": "superadmin@onetouch.ai",
            "full_name": "Alex Rivera",
            "role": "Super Admin",
            "entity": "US-HQ",
            "password_hash": hash_password("demo1234"),
            "status": "active",
            "created_at": iso(datetime.now(timezone.utc)),
        })
        logger.info("Upserted Super Admin user")

    # 4) External auditor user
    if not await db.users.find_one({"email": "external.auditor@bigfour.example"}, {"_id": 0}):
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": "external.auditor@bigfour.example",
            "full_name": "Hannah Oduya",
            "role": "External Auditor",
            "entity": "US-HQ",
            "password_hash": hash_password("demo1234"),
            "status": "active",
            "created_at": iso(datetime.now(timezone.utc)),
        })
        logger.info("Upserted external auditor user")

    await get_notif_settings(db)

    # 5) First-time: run all controls + auto-create top-8 cases
    if not await db.exceptions.count_documents({}):
        out = await run_all_controls(db)
        logger.info("Initial control run: %s exceptions generated", out["total_exceptions"])
        owner_map = {
            "Procure-to-Pay": "ap.clerk@onetouch.ai",
            "Record-to-Report": "gl.lead@onetouch.ai",
            "Access/SoD": "compliance@onetouch.ai",
            "Treasury": "controller@onetouch.ai",
            "Tax": "compliance@onetouch.ai",
            "Order-to-Cash": "controller@onetouch.ai",
            "Payroll": "compliance@onetouch.ai",
            "Fixed Assets": "gl.lead@onetouch.ai",
        }
        critical = [e async for e in db.exceptions.find(
            {"severity": {"$in": ["critical", "high"]}}, {"_id": 0}
        ).sort("financial_exposure", -1).limit(8)]
        for ex in critical:
            owner_email = owner_map.get(ex["process"], "owner@onetouch.ai")
            owner = await db.users.find_one({"email": owner_email}, {"_id": 0})
            case = case_from_exception(ex, owner_email, owner["full_name"] if owner else None)
            await db.cases.insert_one(dict(case))
            await db.exceptions.update_one({"id": ex["id"]}, {"$set": {"status": "in_progress"}})
            await db.case_status_history.insert_one({
                "id": str(uuid.uuid4()), "case_id": case["id"],
                "old_status": None, "new_status": "open",
                "changed_by_user_email": "system",
                "changed_at": iso(datetime.now(timezone.utc)),
            })

    try:
        from app.anomaly import recalibrate_anomaly_scores  # local import: sklearn/num stack only at startup

        anomaly_result = await recalibrate_anomaly_scores(db)
        logger.info("Anomaly recalibration: %s", anomaly_result)
    except Exception as e:  # noqa: BLE001
        logger.warning("Anomaly recalibration failed: %s", e)

    try:
        from app.vector_store import INDEX as vector_index  # local import: sklearn only at startup

        indexed = await vector_index.rebuild(db)
        logger.info("Vector index built: %s documents", indexed)
    except Exception as e:  # noqa: BLE001
        logger.warning("Vector index build failed: %s", e)

    # Semantic embeddings index: light-weight hash provider by default.
    try:
        if await db.embedding_chunks.count_documents({}) == 0:
            from app.embeddings.indexer import rebuild_embedding_index

            out = await rebuild_embedding_index(db, scope=None)
            logger.info("Embedding index built: %s", out)
    except Exception as e:  # noqa: BLE001
        logger.warning("Embedding index build failed: %s", e)

    try:
        async def _sla_job() -> None:
            await scan_sla_breaches(db)

        async def _brief_job() -> None:
            await send_daily_brief(db)

        async def _aq_snapshot_job() -> None:
            from app.services.action_queue_analytics_service import record_snapshot

            entity_codes: list = [None]
            try:
                async for ent in db.entities.find({}, {"_id": 0, "code": 1}).limit(25):
                    code = ent.get("code")
                    if code and code not in entity_codes:
                        entity_codes.append(code)
            except Exception:
                pass
            for entity_code in entity_codes:
                try:
                    await record_snapshot(db, entity_code=entity_code)
                except Exception as exc:
                    logger.warning("Action queue snapshot failed for %s: %s", entity_code, exc)

        async def _p0_queue_job() -> None:
            await scan_p0_action_queue(db)

        sched = AsyncIOScheduler()
        sched.add_job(_sla_job, "interval", minutes=5, id="sla_scan", replace_existing=True)
        sched.add_job(_aq_snapshot_job, "cron", hour=6, minute=15, id="aq_snapshot", replace_existing=True)
        sched.add_job(_p0_queue_job, "interval", hours=1, id="p0_action_queue", replace_existing=True)
        settings = await get_notif_settings(db)
        hour = int(settings.get("daily_brief_hour_utc", 8))
        sched.add_job(_brief_job, "cron", hour=hour, minute=0, id="daily_brief", replace_existing=True)
        sched.start()
        scheduler = sched
        logger.info(
            "Scheduler started: SLA 5m, AQ snapshot 06:15 UTC, P0 queue hourly, brief %02d:00 UTC",
            hour,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Scheduler start failed: %s", e)

    try:
        await scan_sla_breaches(db)
    except Exception as e:  # noqa: BLE001
        logger.warning("Initial SLA scan failed: %s", e)

    try:
        from app.analytics import backfill_test_run_entities

        bf = await backfill_test_run_entities(db, limit=5000)
        if bf.get("updated", 0):
            logger.info("Phase 8 backfill test_runs.entities: scanned=%s updated=%s", bf.get("scanned"), bf.get("updated"))
    except Exception as e:  # noqa: BLE001
        logger.warning("test_runs entities backfill skipped: %s", e)

    try:
        from app.controls_engine import backfill_exceptions_org_slice, backfill_exceptions_required_fields
        from app.services.case_service import (
            backfill_cases_org_from_exceptions,
            backfill_cases_required_fields,
            backfill_missing_exceptions_for_cases,
        )

        bfreq = await backfill_exceptions_required_fields(db, limit=20000)
        if bfreq.get("updated", 0):
            logger.info(
                "Exception required-fields backfill: scanned=%s updated=%s",
                bfreq.get("scanned"),
                bfreq.get("updated"),
            )
        bf11 = await backfill_exceptions_org_slice(db, limit=10000)
        if bf11.get("updated", 0):
            logger.info(
                "Phase 11 backfill exceptions org: scanned=%s updated=%s",
                bf11.get("scanned"),
                bf11.get("updated"),
            )
        bf9 = await backfill_cases_org_from_exceptions(db, limit=10000)
        if bf9.get("updated", 0):
            logger.info("Phase 9 backfill cases org fields: scanned=%s updated=%s", bf9.get("scanned"), bf9.get("updated"))
        bfre = await backfill_cases_required_fields(db, limit=10000)
        if bfre.get("updated", 0):
            logger.info("Case required-fields backfill: scanned=%s updated=%s", bfre.get("scanned"), bfre.get("updated"))
        bfex = await backfill_missing_exceptions_for_cases(db, limit=10000)
        if bfex.get("created", 0):
            logger.info("Case exception backfill: scanned=%s created=%s", bfex.get("scanned"), bfex.get("created"))
    except Exception as e:  # noqa: BLE001
        logger.warning("exceptions/cases org backfill skipped: %s", e)


async def on_shutdown() -> None:
    global scheduler  # noqa: PLW0602
    if scheduler is not None:
        try:
            scheduler.shutdown(wait=False)
        except Exception:  # noqa: BLE001
            pass
    client.close()
