"""Continuous controls monitoring — 12 deterministic rule-based tests.

Each runner returns a list of `exception` dicts ready to upsert.
Exceptions include: source_record_ref, severity, materiality, financial_exposure, anomaly_score, summary.
"""
from __future__ import annotations
import math
import random
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


async def enrich_exceptions_org_slice(db, exs: List[Dict[str, Any]]) -> None:
    """Phase 10 — attach ``department_id`` / ``cost_center_id`` from finance masters per exception ``entity``."""
    if not exs:
        return
    cache: Dict[str, Tuple[Optional[str], Optional[str]]] = {}
    for ex in exs:
        if (ex.get("department_id") or ex.get("dept_id")) and (ex.get("cost_center_id") or ex.get("cc_id")):
            continue
        ent = ex.get("entity")
        if not ent:
            continue
        if ent not in cache:
            dept = await db.master_departments.find_one(
                {"entity_code": ent, "active": True}, {"_id": 0, "id": 1}
            )
            did: Optional[str] = dept.get("id") if dept else None
            cc_doc = None
            if did:
                cc_doc = await db.master_cost_centers.find_one(
                    {"entity_code": ent, "department_id": did, "active": True}, {"_id": 0, "id": 1}
                )
            if not cc_doc:
                cc_doc = await db.master_cost_centers.find_one(
                    {"entity_code": ent, "active": True}, {"_id": 0, "id": 1}
                )
            cid: Optional[str] = cc_doc.get("id") if cc_doc else None
            cache[ent] = (did, cid)
        did, cid = cache[ent]
        if not (ex.get("department_id") or ex.get("dept_id")) and did:
            ex["department_id"] = did
        if not (ex.get("cost_center_id") or ex.get("cc_id")) and cid:
            ex["cost_center_id"] = cid


def _exception_org_backfill_query() -> Dict[str, Any]:
    """Match exceptions that may still be missing canonical dept and/or CC (Phase 11)."""

    def _blank(field: str) -> Dict[str, Any]:
        return {"$or": [{field: {"$exists": False}}, {field: None}, {field: ""}]}

    return {
        "entity": {"$exists": True, "$nin": [None, ""]},
        "$or": [
            {"$and": [_blank("department_id"), _blank("dept_id")]},
            {"$and": [_blank("cost_center_id"), _blank("cc_id")]},
        ],
    }


async def backfill_exceptions_org_slice(db, *, limit: int = 10000, batch_size: int = 250) -> Dict[str, Any]:
    """Phase 11 — enrich persisted exceptions missing ``department_id`` / ``cost_center_id`` using finance masters."""
    scanned = 0
    updated = 0
    q = _exception_org_backfill_query()
    batch: List[Dict[str, Any]] = []
    cur = db.exceptions.find(q, {"_id": 0}).limit(limit)
    async for doc in cur:
        scanned += 1
        batch.append(dict(doc))
        if len(batch) >= batch_size:
            updated += await _apply_exception_org_enrichment_batch(db, batch)
            batch.clear()
    if batch:
        updated += await _apply_exception_org_enrichment_batch(db, batch)
    return {"scanned": scanned, "updated": updated}


async def backfill_exceptions_required_fields(db, *, limit: int = 20000) -> Dict[str, Any]:
    """Hardening: ensure all exception documents satisfy `ExceptionOut` required fields.

    Some modules may upsert lightweight placeholder exceptions (e.g. ad-hoc cases).
    The `/exceptions` endpoint uses `response_model=List[ExceptionOut]` so missing keys cause 500s.
    """
    scanned = 0
    updated = 0
    now = _iso(datetime.now(timezone.utc))
    cur = db.exceptions.find(
        {
            "$or": [
                {"control_id": {"$exists": False}},
                {"source_record_type": {"$exists": False}},
                {"source_record_id": {"$exists": False}},
                {"materiality_score": {"$exists": False}},
                {"anomaly_score": {"$exists": False}},
            ]
        },
        {"_id": 1, "id": 1, "control_code": 1, "control_name": 1, "title": 1, "summary": 1, "entity": 1, "process": 1, "severity": 1, "status": 1, "financial_exposure": 1, "detected_at": 1},
    ).limit(limit)
    async for ex in cur:
        scanned += 1
        patch: Dict[str, Any] = {}
        if not ex.get("control_id"):
            patch["control_id"] = "adhoc-backfill"
        if not ex.get("control_code"):
            patch["control_code"] = "ADHOC-EX"
        if not ex.get("control_name"):
            patch["control_name"] = "Ad hoc exception"
        if not ex.get("process"):
            patch["process"] = "General"
        if not ex.get("entity"):
            patch["entity"] = "US-HQ"
        if not ex.get("severity"):
            patch["severity"] = "medium"
        if not ex.get("status"):
            patch["status"] = "open"
        if ex.get("materiality_score") is None:
            patch["materiality_score"] = 0.0
        if ex.get("anomaly_score") is None:
            patch["anomaly_score"] = 0.0
        if ex.get("financial_exposure") is None:
            patch["financial_exposure"] = 0.0
        if not ex.get("source_record_type"):
            patch["source_record_type"] = "unknown"
        if not ex.get("source_record_id"):
            patch["source_record_id"] = ex.get("id")
        if not ex.get("detected_at"):
            patch["detected_at"] = now
        if not ex.get("title"):
            patch["title"] = "Ad hoc exception"
        if not ex.get("summary"):
            patch["summary"] = patch.get("title") or "Ad hoc exception"
        if patch:
            await db.exceptions.update_one({"_id": ex["_id"]}, {"$set": patch})
            updated += 1
    return {"scanned": scanned, "updated": updated}


async def _apply_exception_org_enrichment_batch(db, batch: List[Dict[str, Any]]) -> int:
    if not batch:
        return 0
    snapshots = [
        {
            "id": ex["id"],
            "department_id": ex.get("department_id"),
            "dept_id": ex.get("dept_id"),
            "cost_center_id": ex.get("cost_center_id"),
            "cc_id": ex.get("cc_id"),
        }
        for ex in batch
    ]
    await enrich_exceptions_org_slice(db, batch)
    n = 0
    for ex, snap in zip(batch, snapshots):
        patch: Dict[str, Any] = {}
        prev_d = snap.get("department_id") or snap.get("dept_id")
        prev_c = snap.get("cost_center_id") or snap.get("cc_id")
        new_d = ex.get("department_id")
        new_c = ex.get("cost_center_id")
        if new_d and new_d != prev_d:
            patch["department_id"] = new_d
        if new_c and new_c != prev_c:
            patch["cost_center_id"] = new_c
        if patch:
            await db.exceptions.update_one({"id": ex["id"]}, {"$set": patch})
            n += 1
    return n


def _exc(control: dict, *, entity: str, severity: str, title: str, summary: str,
         source_record_type: str, source_record_id: str,
         financial_exposure: float, materiality_score: float, anomaly_score: float) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "control_id": control["id"],
        "control_code": control["code"],
        "control_name": control["name"],
        "process": control["process"],
        "entity": entity,
        "severity": severity,
        "status": "open",
        "materiality_score": round(materiality_score, 2),
        "anomaly_score": round(anomaly_score, 2),
        "financial_exposure": round(financial_exposure, 2),
        "source_record_type": source_record_type,
        "source_record_id": source_record_id,
        "detected_at": _iso(datetime.now(timezone.utc)),
        "title": title,
        "summary": summary,
        "recurrence_count": 0,
    }


# ----- Individual rule implementations -----

async def run_duplicate_invoices(db, control):
    exs = []
    grouped = defaultdict(list)
    async for inv in db.invoices.find({}, {"_id": 0}):
        key = (inv["vendor_id"], round(inv["amount"], 2), inv["invoice_number"])
        grouped[key].append(inv)
    for key, items in grouped.items():
        if len(items) > 1:
            primary = items[0]
            for dup in items[1:]:
                exposure = dup["amount"]
                exs.append(_exc(control,
                                entity=dup["entity"],
                                severity="high",
                                title=f"Duplicate invoice {dup['invoice_number']} from {dup['vendor_name']}",
                                summary=f"Invoice {dup['invoice_number']} appears {len(items)}x for vendor {dup['vendor_name']} with amount ${dup['amount']:,.2f}. First seen {primary['invoice_date'][:10]}.",
                                source_record_type="invoice",
                                source_record_id=dup["id"],
                                financial_exposure=exposure,
                                materiality_score=min(1.0, exposure / 250000),
                                anomaly_score=0.95))
    return exs


async def run_duplicate_payments(db, control):
    exs = []
    grouped = defaultdict(list)
    async for p in db.payments.find({}, {"_id": 0}):
        key = (p["vendor_id"], round(p["amount"], 2), p["invoice_id"])
        grouped[key].append(p)
    for items in grouped.values():
        if len(items) > 1:
            for dup in items[1:]:
                exs.append(_exc(control,
                                entity=dup["entity"],
                                severity="critical",
                                title=f"Duplicate payment to {dup['vendor_name']} for ${dup['amount']:,.2f}",
                                summary=f"Payment {dup['id']} duplicates {items[0]['id']} — same vendor, amount, invoice reference.",
                                source_record_type="payment",
                                source_record_id=dup["id"],
                                financial_exposure=dup["amount"],
                                materiality_score=min(1.0, dup["amount"] / 200000),
                                anomaly_score=0.98))
    return exs


async def run_three_way_match(db, control):
    exs = []
    # Build lookup PO and GRN by po_id
    po_map, grn_map = {}, {}
    async for po in db.purchase_orders.find({}, {"_id": 0}):
        po_map[po["id"]] = po
    async for grn in db.goods_receipts.find({}, {"_id": 0}):
        grn_map[grn["po_id"]] = grn
    tolerance = 0.02
    async for inv in db.invoices.find({"po_id": {"$ne": None}}, {"_id": 0}):
        po = po_map.get(inv["po_id"])
        grn = grn_map.get(inv["po_id"])
        if not po or not grn:
            continue
        max_d = max(abs(inv["amount"] - po["amount"]), abs(po["amount"] - grn["amount"]))
        rel = max_d / max(po["amount"], 1)
        if rel > tolerance:
            exposure = max_d
            sev = "critical" if rel > 0.2 else "high" if rel > 0.05 else "medium"
            exs.append(_exc(control,
                            entity=inv["entity"],
                            severity=sev,
                            title=f"3-way match variance on {inv['invoice_number']}",
                            summary=f"Invoice ${inv['amount']:,.2f}, PO ${po['amount']:,.2f}, GRN ${grn['amount']:,.2f} — variance {rel*100:.1f}%.",
                            source_record_type="invoice",
                            source_record_id=inv["id"],
                            financial_exposure=exposure,
                            materiality_score=min(1.0, exposure / 100000),
                            anomaly_score=min(0.99, 0.4 + rel)))
    return exs


async def run_manual_journal_above_threshold(db, control):
    exs = []
    threshold = 100_000
    async for j in db.journals.find({"is_manual": True, "total_amount": {"$gt": threshold}}, {"_id": 0}):
        if not j.get("approver_email"):
            exs.append(_exc(control,
                            entity=j["entity"],
                            severity="high" if j["total_amount"] < 300000 else "critical",
                            title=f"Manual JE {j['journal_number']} ${j['total_amount']:,.0f} missing approver",
                            summary=f"Manual journal {j['journal_number']} for ${j['total_amount']:,.2f} posted by {j['created_by']} without documented approver.",
                            source_record_type="journal",
                            source_record_id=j["id"],
                            financial_exposure=j["total_amount"],
                            materiality_score=min(1.0, j["total_amount"] / 500000),
                            anomaly_score=0.82))
    return exs


async def run_backdated_journals(db, control):
    exs = []
    # posting_date before (created_at - 2d) and created_at within last 14d
    now = datetime.now(timezone.utc)
    async for j in db.journals.find({}, {"_id": 0}):
        try:
            posting = datetime.fromisoformat(j["posting_date"])
            created = datetime.fromisoformat(j["created_at"])
        except Exception:
            continue
        if (created - posting).days >= 3 and (now - created).days <= 14:
            exs.append(_exc(control,
                            entity=j["entity"],
                            severity="critical",
                            title=f"Backdated journal {j['journal_number']} ({(created-posting).days}d)",
                            summary=f"JE {j['journal_number']} posted in closed period — posting date {j['posting_date'][:10]}, entered {j['created_at'][:10]}.",
                            source_record_type="journal",
                            source_record_id=j["id"],
                            financial_exposure=j["total_amount"],
                            materiality_score=min(1.0, j["total_amount"] / 300000),
                            anomaly_score=0.9))
    return exs


async def run_privileged_user_journals(db, control):
    exs = []
    async for j in db.journals.find({"is_privileged_poster": True, "total_amount": {"$gt": 50_000}}, {"_id": 0}):
        exs.append(_exc(control,
                        entity=j["entity"],
                        severity="high",
                        title=f"Privileged user posted ${j['total_amount']:,.0f}",
                        summary=f"User {j['created_by']} (privileged) posted JE {j['journal_number']} for ${j['total_amount']:,.2f}.",
                        source_record_type="journal",
                        source_record_id=j["id"],
                        financial_exposure=j["total_amount"],
                        materiality_score=min(1.0, j["total_amount"] / 300000),
                        anomaly_score=0.78))
    return exs


async def run_approval_bypass(db, control):
    exs = []
    threshold = 50_000
    async for inv in db.invoices.find({"amount": {"$gt": threshold}, "approver_email": None}, {"_id": 0}):
        exs.append(_exc(control,
                        entity=inv["entity"],
                        severity="high",
                        title=f"Invoice {inv['invoice_number']} > threshold, missing approver",
                        summary=f"Invoice from {inv['vendor_name']} for ${inv['amount']:,.2f} exceeds $50k dual-approval threshold but has no documented approver.",
                        source_record_type="invoice",
                        source_record_id=inv["id"],
                        financial_exposure=inv["amount"],
                        materiality_score=min(1.0, inv["amount"] / 200000),
                        anomaly_score=0.72))
    return exs


async def run_inactive_user_activity(db, control):
    exs = []
    async for e in db.user_access_events.find({"user_terminated": True}, {"_id": 0}):
        exs.append(_exc(control,
                        entity=e["entity"],
                        severity="critical",
                        title=f"Terminated user {e['user_email']} active on {e['system']}",
                        summary=f"Event `{e['event_type']}` at {e['event_ts'][:16]} by terminated user {e['user_email']}.",
                        source_record_type="access_event",
                        source_record_id=e["id"],
                        financial_exposure=0.0,
                        materiality_score=0.65,
                        anomaly_score=0.88))
    return exs


async def run_sod_conflict(db, control):
    exs = []
    role_map = [r async for r in db.sod_role_map.find({}, {"_id": 0})]
    forbidden = [(f["a"], f["b"]) async for f in db.sod_forbidden.find({}, {"_id": 0})]
    by_user = defaultdict(set)
    user_entity = {}
    for r in role_map:
        by_user[r["user_email"]].add(r["role"])
        user_entity[r["user_email"]] = r["entity"]
    for user, roles in by_user.items():
        for a, b in forbidden:
            if a in roles and b in roles:
                exs.append(_exc(control,
                                entity=user_entity.get(user, "US-HQ"),
                                severity="high",
                                title=f"SoD conflict: {user} holds {a} + {b}",
                                summary=f"User {user} assigned incompatible roles ({a}, {b}). Immediate review required.",
                                source_record_type="user",
                                source_record_id=user,
                                financial_exposure=0.0,
                                materiality_score=0.7,
                                anomaly_score=0.85))
    return exs


async def run_unreconciled(db, control):
    exs = []
    async for r in db.reconciliations.find({}, {"_id": 0}):
        overdue = r["status"] == "overdue"
        variance = abs(r.get("variance_amount", 0.0))
        if overdue or variance > r.get("tolerance", 5000):
            sev = "high" if variance > 20000 or overdue else "medium"
            exs.append(_exc(control,
                            entity=r["entity"],
                            severity=sev,
                            title=f"{r['reconciliation_type']} reconciliation {r['period']} {'overdue' if overdue else 'variance'}",
                            summary=f"{r['reconciliation_type']} recon for {r['entity']} {r['period']} — variance ${variance:,.2f}, status {r['status']}.",
                            source_record_type="reconciliation",
                            source_record_id=r["id"],
                            financial_exposure=variance,
                            materiality_score=min(1.0, variance / 100000),
                            anomaly_score=0.6 + min(0.3, variance / 200000)))
    return exs


async def run_tax_mismatch(db, control):
    exs = []
    async for inv in db.invoices.find({}, {"_id": 0}):
        exp = inv.get("expected_tax_amount", 0)
        act = inv.get("tax_amount", 0)
        if exp > 0 and abs(exp - act) / exp > 0.05:
            diff = abs(exp - act)
            exs.append(_exc(control,
                            entity=inv["entity"],
                            severity="medium" if diff < 2000 else "high",
                            title=f"Tax mismatch on {inv['invoice_number']}: ${diff:,.2f}",
                            summary=f"Vendor {inv['vendor_name']} — expected tax ${exp:,.2f}, actual ${act:,.2f} (variance ${diff:,.2f}).",
                            source_record_type="invoice",
                            source_record_id=inv["id"],
                            financial_exposure=diff,
                            materiality_score=min(1.0, diff / 50000),
                            anomaly_score=0.55))
    return exs


async def run_vendor_bank_change(db, control):
    exs = []
    now = datetime.now(timezone.utc)
    recent_vendors = {}
    async for v in db.vendors.find({}, {"_id": 0}):
        try:
            changed = datetime.fromisoformat(v["bank_changed_at"])
        except Exception:
            continue
        if (now - changed).days <= 14:
            recent_vendors[v["id"]] = v
    async for pay in db.payments.find({}, {"_id": 0}):
        if pay["vendor_id"] in recent_vendors:
            v = recent_vendors[pay["vendor_id"]]
            days = (now - datetime.fromisoformat(v["bank_changed_at"])).days
            exs.append(_exc(control,
                            entity=pay["entity"],
                            severity="critical",
                            title=f"Payment to {v['vendor_name']} {days}d after bank change",
                            summary=f"Payment {pay['id']} for ${pay['amount']:,.2f} to vendor whose bank account changed {days} days ago.",
                            source_record_type="payment",
                            source_record_id=pay["id"],
                            financial_exposure=pay["amount"],
                            materiality_score=min(1.0, pay["amount"] / 150000),
                            anomaly_score=0.94))
    return exs


RUNNERS = {
    "C-AP-001": run_duplicate_invoices,
    "C-AP-002": run_duplicate_payments,
    "C-AP-003": run_three_way_match,
    "C-GL-001": run_manual_journal_above_threshold,
    "C-GL-002": run_backdated_journals,
    "C-GL-003": run_privileged_user_journals,
    "C-AP-004": run_approval_bypass,
    "C-ACC-001": run_inactive_user_activity,
    "C-ACC-002": run_sod_conflict,
    "C-TR-001": run_unreconciled,
    "C-TX-001": run_tax_mismatch,
    "C-AP-005": run_vendor_bank_change,
}

# Merge Phase 2 runners (Order-to-Cash, Payroll, Treasury, Tax, Fixed Assets)
from .controls_phase2 import RUNNERS_PHASE2  # noqa: E402
RUNNERS.update(RUNNERS_PHASE2)


async def run_control(db, control: dict) -> Dict[str, Any]:
    """Run a single control, persist exceptions + test_run, update control status."""
    runner = RUNNERS.get(control["code"])
    run_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    if runner is None:
        return {"run_id": run_id, "exceptions": 0, "status": "no_runner"}
    try:
        exs = await runner(db, control)
    except Exception as e:  # boundary
        await db.test_runs.insert_one({
            "id": run_id, "control_id": control["id"], "control_code": control["code"],
            "run_ts": _iso(now), "status": "failed", "error": str(e), "exceptions_count": 0,
            "entities": [],
        })
        return {"run_id": run_id, "exceptions": 0, "status": "failed", "error": str(e)}

    await enrich_exceptions_org_slice(db, exs)
    # Delete prior OPEN exceptions for this control (to avoid duplicates across reruns),
    # keeping any that have been transitioned into cases (in_progress/closed)
    await db.exceptions.delete_many({"control_id": control["id"], "status": "open"})
    if exs:
        await db.exceptions.insert_many([dict(e) for e in exs])

    entity_tags = sorted({str(e["entity"]) for e in exs if e.get("entity")})
    await db.test_runs.insert_one({
        "id": run_id, "control_id": control["id"], "control_code": control["code"],
        "run_ts": _iso(now), "status": "success", "exceptions_count": len(exs),
        "entities": entity_tags,
    })
    await db.controls.update_one(
        {"id": control["id"]},
        {"$set": {"last_run_at": _iso(now), "last_run_exceptions": len(exs), "last_run_pass": len(exs) == 0}},
    )
    return {"run_id": run_id, "exceptions": len(exs), "status": "success"}


async def run_all_controls(db) -> Dict[str, Any]:
    results = []
    async for c in db.controls.find({"active": True}, {"_id": 0}):
        r = await run_control(db, c)
        results.append({"control_code": c["code"], **r})
    total_ex = sum(r["exceptions"] for r in results)
    return {"runs": results, "total_exceptions": total_ex}
