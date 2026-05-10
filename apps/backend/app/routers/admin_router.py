"""Admin, seed-reset, CSV ingest, model registry/training, notifications, exports, auditor portal."""
import csv
import gzip
import hashlib
import io
import json
import uuid
import zlib
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Body
from fastapi.responses import StreamingResponse, Response

from app.auth import get_current_user, hash_password
from app.core.entity_scope import entity_scope_enforced
from app.deps import db, audit_log, iso
from app.models import IngestResult, PlatformUserCreate, UserPublic
from app.seed import seed_database
from app.controls_engine import run_all_controls
from app.exports import build_pdf, build_xlsx
from app.analytics import cfo_cockpit
from app.services.case_service import merge_cases_master_filters
from app.notifier import (get_settings as get_notif_settings, save_settings as save_notif_settings,
                          scan_sla_breaches, list_notifications, send_daily_brief)
from app.training import train_anomaly_model, list_model_versions, approve_model_version
from app.services.rbac_service import enforce_entity_scope, role_bypasses_entity_scope

router = APIRouter(tags=["admin-ops"])

PLATFORM_USER_ROLES = frozenset(
    {
        "CFO",
        "Controller",
        "Internal Auditor",
        "Compliance Head",
        "Process Owner",
        "External Auditor",
        "Super Admin",
    }
)


def _require_audit_log_viewer(current=Depends(get_current_user)):
    """Phase 25 — audit logs are governance data; restrict to admin-style roles."""
    if current.get("role") not in ("CFO", "Controller", "Internal Auditor", "Compliance Head", "Super Admin"):
        raise HTTPException(403, "Insufficient permissions")
    return current


def _maybe_prefix_regex(value: Optional[str]) -> Optional[Dict[str, Any]]:
    """Phase 29 — allow lightweight prefix filters for audit-log fields.

    - If value ends with '_' (e.g. 'export_'), treat as prefix.
    - If value contains '*' (e.g. 'export_*'), treat as prefix up to '*'.
    - Otherwise return None (caller should use exact match).
    """
    if not value:
        return None
    v = value.strip()
    if not v:
        return None
    if "*" in v:
        pref = v.split("*", 1)[0]
        if not pref:
            return None
        return {"$regex": f"^{pref}"}
    if v.endswith("_") and len(v) > 1:
        return {"$regex": f"^{v}"}
    return None


def _audit_log_query(
    *,
    q: Optional[str],
    actor: Optional[str],
    action_type: Optional[str],
    object_type: Optional[str],
    object_id: Optional[str],
    since_ts: Optional[str],
    until_ts: Optional[str],
) -> Dict[str, Any]:
    base: Dict[str, Any] = {}
    if actor:
        base["actor_user_email"] = actor
    if action_type:
        rx = _maybe_prefix_regex(action_type)
        base["action_type"] = rx if rx else action_type
    if object_type:
        base["object_type"] = object_type
    if object_id:
        rx = _maybe_prefix_regex(object_id)
        base["object_id"] = rx if rx else object_id
    if since_ts:
        base.setdefault("event_ts", {})
        base["event_ts"]["$gte"] = since_ts
    if until_ts:
        base.setdefault("event_ts", {})
        base["event_ts"]["$lte"] = until_ts

    query: Dict[str, Any] = base
    if q:
        # Use simple case-insensitive regex on key fields.
        rxq = {"$regex": q, "$options": "i"}
        ors = [
            {"actor_user_email": rxq},
            {"action_type": rxq},
            {"object_type": rxq},
            {"object_id": rxq},
        ]
        query = {"$and": [base, {"$or": ors}]} if base else {"$or": ors}
    return query


def _audit_log_export_sort() -> list[tuple[str, int]]:
    """Stable newest-first ordering for exports and keyset pagination (Phase 35)."""
    return [("event_ts", -1), ("id", -1)]


def _audit_log_merge_keyset(base: Dict[str, Any], after_ts: str, after_id: Optional[str]) -> Dict[str, Any]:
    """Restrict to rows strictly after `(after_ts, after_id)` in event_ts DESC, id DESC order."""
    ts = after_ts.strip()
    if after_id and str(after_id).strip():
        aid = str(after_id).strip()
        ks: Dict[str, Any] = {
            "$or": [
                {"event_ts": {"$lt": ts}},
                {"$and": [{"event_ts": ts}, {"id": {"$lt": aid}}]},
            ]
        }
    else:
        ks = {"event_ts": {"$lt": ts}}
    if not base:
        return ks
    return {"$and": [base, ks]}


def _require_super_admin(current=Depends(get_current_user)):
    if current.get("role") != "Super Admin":
        raise HTTPException(403, "Super Admin role required")
    return current


# ---------- Platform users (Super Admin) ----------
@router.get("/admin/users", response_model=list[UserPublic])
async def platform_users_list(current=Depends(_require_super_admin)):
    cur = db.users.find({}, {"_id": 0, "password_hash": 0}).sort("email", 1)
    return [
        UserPublic(
            id=u["id"],
            email=u["email"],
            full_name=u["full_name"],
            role=u["role"],
            entity=u.get("entity"),
        )
        async for u in cur
    ]


@router.post("/admin/users", response_model=UserPublic)
async def platform_users_create(body: PlatformUserCreate, current=Depends(_require_super_admin)):
    if body.role not in PLATFORM_USER_ROLES:
        raise HTTPException(400, f"role must be one of: {', '.join(sorted(PLATFORM_USER_ROLES))}")
    email = str(body.email).lower().strip()
    if await db.users.find_one({"email": email}, {"_id": 0}):
        raise HTTPException(409, "User with this email already exists")
    uid = str(uuid.uuid4())
    now = iso(datetime.now(timezone.utc))
    doc = {
        "id": uid,
        "email": email,
        "full_name": body.full_name.strip(),
        "role": body.role,
        "entity": body.entity or "US-HQ",
        "password_hash": hash_password(body.password),
        "status": "active",
        "created_at": now,
    }
    await db.users.insert_one(dict(doc))
    await audit_log(current["email"], "create_user", "user", uid, {"email": email, "role": body.role})
    return UserPublic(id=uid, email=email, full_name=doc["full_name"], role=body.role, entity=doc["entity"])


@router.delete("/admin/users/{user_id}")
async def platform_users_delete(user_id: str, current=Depends(_require_super_admin)):
    target = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not target:
        raise HTTPException(404, "User not found")
    if target["id"] == current["user_id"]:
        raise HTTPException(400, "Cannot delete your own account")
    if target.get("role") == "Super Admin":
        n_sa = await db.users.count_documents({"role": "Super Admin"})
        if n_sa <= 1:
            raise HTTPException(400, "Cannot delete the last Super Admin user")
    await db.users.delete_one({"id": user_id})
    await audit_log(current["email"], "delete_user", "user", user_id, {"email": target.get("email")})
    return {"deleted": True, "id": user_id}


# ---------- Admin ----------
@router.get("/admin/models")
async def admin_models(current=Depends(get_current_user)):
    return [m async for m in db.model_registry.find({}, {"_id": 0})]


@router.get("/admin/prompts")
async def admin_prompts(current=Depends(get_current_user)):
    return [p async for p in db.prompt_registry.find({}, {"_id": 0})]


@router.get("/admin/audit-logs")
async def admin_audit_logs(limit: int = 100, current=Depends(_require_audit_log_viewer)):
    return [l async for l in db.audit_logs.find({}, {"_id": 0}).sort(_audit_log_export_sort()).limit(limit)]


@router.get("/admin/audit-logs/query")
async def admin_audit_logs_query(
    q: Optional[str] = Query(None, description="Phase 15 — substring search across actor/action/object"),
    actor: Optional[str] = Query(None),
    action_type: Optional[str] = Query(None),
    object_type: Optional[str] = Query(None),
    object_id: Optional[str] = Query(None),
    since_ts: Optional[str] = Query(None, description="ISO prefix match (e.g. 2026-05-01)"),
    until_ts: Optional[str] = Query(None, description="ISO prefix match (e.g. 2026-05-31)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current=Depends(_require_audit_log_viewer),
):
    query = _audit_log_query(
        q=q,
        actor=actor,
        action_type=action_type,
        object_type=object_type,
        object_id=object_id,
        since_ts=since_ts,
        until_ts=until_ts,
    )
    total = await db.audit_logs.count_documents(query if query else {})
    cur = (
        db.audit_logs.find(query if query else {}, {"_id": 0})
        .sort(_audit_log_export_sort())
        .skip(offset)
        .limit(limit)
    )
    items = [l async for l in cur]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/admin/audit-logs/export.csv")
async def admin_audit_logs_export_csv(
    q: Optional[str] = Query(None, description="Phase 19 — export the same filtered view as /admin/audit-logs/query"),
    actor: Optional[str] = Query(None),
    action_type: Optional[str] = Query(None),
    object_type: Optional[str] = Query(None),
    object_id: Optional[str] = Query(None),
    since_ts: Optional[str] = Query(None),
    until_ts: Optional[str] = Query(None),
    limit: int = Query(5000, ge=1, le=20000),
    offset: int = Query(0, ge=0, description="Phase 34 — skip N rows after sort (ignored when after_ts is set)"),
    after_ts: Optional[str] = Query(None, description="Phase 35 — keyset: ISO event_ts of anchor row (exclusive, newest-first)"),
    after_id: Optional[str] = Query(None, description="Phase 35 — keyset: audit id for stable tie-break (recommended)"),
    compress_gzip: bool = Query(False, alias="gzip", description="Phase 33 — gzip-compress the export body (?gzip=true)"),
    digest: bool = Query(False, description="Phase 34 — include X-Audit-Export-Sha256 of the exact response bytes"),
    current=Depends(_require_audit_log_viewer),
):
    use_gzip = compress_gzip
    if after_id and not (after_ts and str(after_ts).strip()):
        raise HTTPException(400, "after_id requires after_ts")
    base = _audit_log_query(
        q=q,
        actor=actor,
        action_type=action_type,
        object_type=object_type,
        object_id=object_id,
        since_ts=since_ts,
        until_ts=until_ts,
    )
    use_keyset = bool(after_ts and str(after_ts).strip())
    filt = _audit_log_merge_keyset(base, after_ts.strip(), after_id) if use_keyset else base
    ski = 0 if use_keyset else offset
    cur = (
        db.audit_logs.find(filt if filt else {}, {"_id": 0})
        .sort(_audit_log_export_sort())
        .skip(ski)
        .limit(limit + 1)
    )
    raw_rows = [r async for r in cur]
    has_more = len(raw_rows) > limit
    out_rows = raw_rows[:limit]

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["event_ts", "actor_user_email", "action_type", "object_type", "object_id", "detail_json"])
    n = 0
    for row in out_rows:
        n += 1
        detail = row.get("detail") or {}
        w.writerow([
            row.get("event_ts", ""),
            row.get("actor_user_email", ""),
            row.get("action_type", ""),
            row.get("object_type", ""),
            row.get("object_id", ""),
            json.dumps(detail, ensure_ascii=False),
        ])

    out = buf.getvalue().encode("utf-8")
    if use_gzip:
        out = gzip.compress(out, compresslevel=6)

    last = out_rows[-1] if out_rows else None
    await audit_log(
        current["email"],
        "export_csv",
        "audit_logs",
        "audit-logs",
        {"filters_applied": {k: v for k, v in {"q": q, "actor": actor, "action_type": action_type, "object_type": object_type, "object_id": object_id, "since_ts": since_ts, "until_ts": until_ts}.items() if v},
         "rows": n, "gzip": use_gzip, "offset": offset if not use_keyset else None, "keyset": use_keyset,
         "after_ts": after_ts, "after_id": after_id, "digest": digest},
    )
    hdrs = {
        "Content-Disposition": 'attachment; filename="audit-logs.csv.gz"'
        if use_gzip else 'attachment; filename="audit-logs.csv"',
        "X-Audit-Export-Offset": str(ski),
        "X-Audit-Export-Keyset": "true" if use_keyset else "false",
        "X-Audit-Export-Truncated": "true" if has_more else "false",
    }
    if has_more and last:
        hdrs["X-Audit-Export-Next-Cursor-After-Ts"] = str(last.get("event_ts", ""))
        if last.get("id") is not None:
            hdrs["X-Audit-Export-Next-Cursor-After-Id"] = str(last["id"])
    if digest:
        hdrs["X-Audit-Export-Sha256"] = hashlib.sha256(out).hexdigest()
    return StreamingResponse(
        io.BytesIO(out),
        media_type="application/gzip" if use_gzip else "text/csv",
        headers=hdrs,
    )


@router.get("/admin/audit-logs/export.json")
async def admin_audit_logs_export_json(
    q: Optional[str] = Query(None, description="Phase 31 — same filters as CSV; JSON envelope for SIEM/archival ingestion"),
    actor: Optional[str] = Query(None),
    action_type: Optional[str] = Query(None),
    object_type: Optional[str] = Query(None),
    object_id: Optional[str] = Query(None),
    since_ts: Optional[str] = Query(None),
    until_ts: Optional[str] = Query(None),
    limit: int = Query(5000, ge=1, le=20000),
    offset: int = Query(0, ge=0, description="Phase 34 — skip N rows after sort (ignored when after_ts is set)"),
    after_ts: Optional[str] = Query(None, description="Phase 35 — keyset anchor event_ts"),
    after_id: Optional[str] = Query(None, description="Phase 35 — keyset anchor audit id (recommended)"),
    compress_gzip: bool = Query(False, alias="gzip", description="Phase 33 — gzip-compress the JSON body (?gzip=true)"),
    digest: bool = Query(False, description="Phase 34 — SHA-256 of delivered bytes (after gzip if any)"),
    current=Depends(_require_audit_log_viewer),
):
    if after_id and not (after_ts and str(after_ts).strip()):
        raise HTTPException(400, "after_id requires after_ts")
    base = _audit_log_query(
        q=q,
        actor=actor,
        action_type=action_type,
        object_type=object_type,
        object_id=object_id,
        since_ts=since_ts,
        until_ts=until_ts,
    )
    use_keyset = bool(after_ts and str(after_ts).strip())
    filt = _audit_log_merge_keyset(base, after_ts.strip(), after_id) if use_keyset else base
    ski = 0 if use_keyset else offset
    total = await db.audit_logs.count_documents(base if base else {})
    cur = (
        db.audit_logs.find(filt if filt else {}, {"_id": 0})
        .sort(_audit_log_export_sort())
        .skip(ski)
        .limit(limit + 1)
    )
    raw_items = [row async for row in cur]
    has_more = len(raw_items) > limit
    items = raw_items[:limit]

    filters_applied = {
        k: v
        for k, v in {
            "q": q,
            "actor": actor,
            "action_type": action_type,
            "object_type": object_type,
            "object_id": object_id,
            "since_ts": since_ts,
            "until_ts": until_ts,
        }.items()
        if v
    }

    chunk_returned = len(items)
    last = items[-1] if items else None
    next_cursor = (
        {"after_ts": last.get("event_ts"), "after_id": last.get("id")}
        if has_more and last is not None
        else None
    )
    body = {
        "exported_at": iso(datetime.now(timezone.utc)),
        "filters_applied": filters_applied,
        "total_matched": total,
        "paging": "keyset" if use_keyset else "offset",
        "offset": ski,
        "limit": limit,
        "returned": chunk_returned,
        "truncated": has_more,
        "next_cursor": next_cursor,
        "items": items,
    }
    payload = json.dumps(body, ensure_ascii=False, default=str).encode("utf-8")
    if compress_gzip:
        payload = gzip.compress(payload, compresslevel=6)

    await audit_log(
        current["email"],
        "export_json",
        "audit_logs",
        "audit-logs",
        {
            "filters_applied": filters_applied,
            "total_matched": total,
            "returned": chunk_returned,
            "gzip": compress_gzip,
            "offset": offset if not use_keyset else None,
            "keyset": use_keyset,
            "after_ts": after_ts,
            "after_id": after_id,
            "digest": digest,
        },
    )
    hdrs = {
        "Content-Disposition": 'attachment; filename="audit-logs.json.gz"'
        if compress_gzip else 'attachment; filename="audit-logs.json"',
        "X-Audit-Export-Offset": str(ski),
        "X-Audit-Export-Total-Matched": str(total),
        "X-Audit-Export-Truncated": "true" if has_more else "false",
        "X-Audit-Export-Keyset": "true" if use_keyset else "false",
    }
    if next_cursor:
        hdrs["X-Audit-Export-Next-Cursor-After-Ts"] = str(next_cursor.get("after_ts", ""))
        if next_cursor.get("after_id") is not None:
            hdrs["X-Audit-Export-Next-Cursor-After-Id"] = str(next_cursor["after_id"])
    if digest:
        hdrs["X-Audit-Export-Sha256"] = hashlib.sha256(payload).hexdigest()
    return Response(
        content=payload,
        media_type="application/gzip" if compress_gzip else "application/json; charset=utf-8",
        headers=hdrs,
    )


@router.get("/admin/audit-logs/export.ndjson")
async def admin_audit_logs_export_ndjson(
    q: Optional[str] = Query(None, description="Phase 32 — streamed NDJSON; one audit event JSON object per line (SIEM / jq / large pulls)"),
    actor: Optional[str] = Query(None),
    action_type: Optional[str] = Query(None),
    object_type: Optional[str] = Query(None),
    object_id: Optional[str] = Query(None),
    since_ts: Optional[str] = Query(None),
    until_ts: Optional[str] = Query(None),
    limit: int = Query(5000, ge=1, le=20000),
    offset: int = Query(0, ge=0, description="Phase 34 — Mongo skip (ignored when after_ts is set)"),
    after_ts: Optional[str] = Query(None, description="Phase 35 — keyset anchor event_ts"),
    after_id: Optional[str] = Query(None, description="Phase 35 — keyset anchor audit id (recommended)"),
    compress_gzip: bool = Query(False, alias="gzip", description="Phase 33 — gzip the NDJSON byte stream (?gzip=true)"),
    digest: bool = Query(False, description="Phase 34 — SHA-256 of delivered bytes"),
    current=Depends(_require_audit_log_viewer),
):
    if after_id and not (after_ts and str(after_ts).strip()):
        raise HTTPException(400, "after_id requires after_ts")
    base = _audit_log_query(
        q=q,
        actor=actor,
        action_type=action_type,
        object_type=object_type,
        object_id=object_id,
        since_ts=since_ts,
        until_ts=until_ts,
    )
    use_keyset = bool(after_ts and str(after_ts).strip())
    filt = _audit_log_merge_keyset(base, after_ts.strip(), after_id) if use_keyset else base
    ski = 0 if use_keyset else offset
    total = await db.audit_logs.count_documents(base if base else {})

    filters_applied = {
        k: v
        for k, v in {
            "q": q,
            "actor": actor,
            "action_type": action_type,
            "object_type": object_type,
            "object_id": object_id,
            "since_ts": since_ts,
            "until_ts": until_ts,
        }.items()
        if v
    }

    exported_at = iso(datetime.now(timezone.utc))
    cur = (
        db.audit_logs.find(filt if filt else {}, {"_id": 0})
        .sort(_audit_log_export_sort())
        .skip(ski)
        .limit(limit + 1)
    )
    raw_rows = [r async for r in cur]
    has_more = len(raw_rows) > limit
    out_rows = raw_rows[:limit]

    compressor = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION, zlib.DEFLATED, zlib.MAX_WBITS | 16) if compress_gzip else None
    emitted = len(out_rows)

    async def ndjson_body() -> AsyncIterator[bytes]:
        try:
            for row in out_rows:
                chunk = (json.dumps(row, ensure_ascii=False, default=str) + "\n").encode("utf-8")
                if compressor:
                    z = compressor.compress(chunk)
                    if z:
                        yield z
                else:
                    yield chunk
            if compressor:
                tail = compressor.flush()
                if tail:
                    yield tail
        finally:
            await audit_log(
                current["email"],
                "export_ndjson",
                "audit_logs",
                "audit-logs",
                {
                    "filters_applied": filters_applied,
                    "total_matched": total,
                    "returned": emitted,
                    "gzip": compress_gzip,
                    "offset": offset if not use_keyset else None,
                    "keyset": use_keyset,
                    "after_ts": after_ts,
                    "after_id": after_id,
                    "digest": digest,
                },
            )

    last = out_rows[-1] if out_rows else None
    headers: Dict[str, str] = {
        "Content-Disposition": ('attachment; filename="audit-logs.ndjson.gz"' if compress_gzip else 'attachment; filename="audit-logs.ndjson"'),
        "X-Audit-Export-Exported-At": exported_at,
        "X-Audit-Export-Total-Matched": str(total),
        "X-Audit-Export-Offset": str(ski),
        "X-Audit-Export-Limit": str(limit),
        "X-Audit-Export-Truncated": "true" if has_more else "false",
        "X-Audit-Export-Keyset": "true" if use_keyset else "false",
    }
    if has_more and last is not None:
        headers["X-Audit-Export-Next-Cursor-After-Ts"] = str(last.get("event_ts", ""))
        if last.get("id") is not None:
            headers["X-Audit-Export-Next-Cursor-After-Id"] = str(last["id"])
    if digest:
        buf = io.BytesIO()
        async for part in ndjson_body():
            buf.write(part)
        raw = buf.getvalue()
        headers["X-Audit-Export-Sha256"] = hashlib.sha256(raw).hexdigest()
        return Response(
            content=raw,
            media_type="application/gzip" if compress_gzip else "application/x-ndjson; charset=utf-8",
            headers=headers,
        )

    return StreamingResponse(
        ndjson_body(),
        media_type="application/gzip" if compress_gzip else "application/x-ndjson; charset=utf-8",
        headers=headers,
    )


@router.get("/admin/audit-logs/{log_id}")
async def admin_audit_log_detail(log_id: str, current=Depends(_require_audit_log_viewer)):
    """Phase 23 — deep-linkable single audit event.

    Registered after static paths like ``/admin/audit-logs/query`` so ``log_id`` cannot
    shadow ``query`` / ``export.*``.
    """
    doc = await db.audit_logs.find_one({"id": log_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Audit log not found")
    return doc


@router.get("/admin/summary")
async def admin_summary(current=Depends(get_current_user)):
    return {
        "collections": {c: await db[c].count_documents({}) for c in [
            "users", "entities", "vendors", "invoices", "payments", "journals",
            "controls", "exceptions", "cases", "audit_logs", "copilot_sessions",
        ]},
    }


@router.post("/admin/seed-reset")
async def admin_seed_reset(current=Depends(get_current_user)):
    if current["role"] not in ("CFO", "Internal Auditor", "Controller"):
        raise HTTPException(403, "Insufficient permissions")
    result = await seed_database(db, force=True)
    await run_all_controls(db)
    await audit_log(current["email"], "seed_reset", "system", "all", result)
    return {"reseeded": True, "counts": result}


@router.get("/admin/model-versions")
async def admin_model_versions(current=Depends(get_current_user)):
    return await list_model_versions(db)


@router.post("/admin/model-versions/{version_id}/approve")
async def admin_approve_version(version_id: str, current=Depends(get_current_user)):
    if current["role"] not in ("CFO", "Internal Auditor"):
        raise HTTPException(403, "Approval requires CFO or Internal Auditor role")
    result = await approve_model_version(db, version_id, current["email"])
    if result.get("error"):
        raise HTTPException(404, "Version not found")
    await audit_log(current["email"], "approve_model_version", "model_version", version_id)
    return result


# ---------- CSV ingest ----------
@router.post("/ingest/csv", response_model=IngestResult)
async def ingest_csv(
    file: UploadFile = File(...),
    dataset: str = Form(...),
    current=Depends(get_current_user),
):
    dataset = dataset.strip().lower()
    if dataset not in ("vendors", "invoices"):
        raise HTTPException(400, "Unsupported dataset. Use 'vendors' or 'invoices'.")
    forced_entity = await enforce_entity_scope(db, current=current, requested_entity_code=None)
    content = (await file.read()).decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(content))
    rows_ingested = 0
    rows_failed = 0
    now = datetime.now(timezone.utc)
    docs = []
    for row in reader:
        try:
            if dataset == "vendors":
                doc = {
                    "id": row.get("id") or f"V-CSV-{uuid.uuid4().hex[:8]}",
                    "vendor_code": row.get("vendor_code") or row.get("id") or f"V-{uuid.uuid4().hex[:6]}",
                    "vendor_name": row["vendor_name"],
                    "entity": forced_entity if forced_entity else row.get("entity", "US-HQ"),
                    "bank_account_hash": row.get("bank_account_hash", "HASHCSV"),
                    "bank_changed_at": row.get("bank_changed_at", iso(now - timedelta(days=365))),
                    "status": row.get("status", "active"),
                    "created_at": iso(now),
                }
            else:
                doc = {
                    "id": row.get("id") or f"INV-CSV-{uuid.uuid4().hex[:8]}",
                    "invoice_number": row["invoice_number"],
                    "vendor_id": row.get("vendor_id", "V-1000"),
                    "vendor_name": row.get("vendor_name", "Unknown"),
                    "entity": forced_entity if forced_entity else row.get("entity", "US-HQ"),
                    "invoice_date": row.get("invoice_date", iso(now)),
                    "amount": float(row["amount"]),
                    "tax_amount": float(row.get("tax_amount", 0)),
                    "expected_tax_amount": float(row.get("expected_tax_amount", float(row.get("amount", 0)) * 0.18)),
                    "status": row.get("status", "posted"),
                    "po_id": row.get("po_id") or None,
                    "approver_email": row.get("approver_email") or None,
                    "created_at": iso(now),
                }
            docs.append(doc)
            rows_ingested += 1
        except Exception:
            rows_failed += 1
    if docs:
        await db[dataset].insert_many(docs)
    lineage_id = str(uuid.uuid4())
    await db.ingestion_runs.insert_one({
        "id": lineage_id,
        "dataset": dataset,
        "source": f"csv_upload:{file.filename}",
        "rows_read": rows_ingested + rows_failed,
        "rows_loaded": rows_ingested,
        "rows_failed": rows_failed,
        "status": "success" if rows_failed == 0 else "partial",
        "run_start": iso(now),
        "run_end": iso(datetime.now(timezone.utc)),
        "user_email": current["email"],
    })
    await audit_log(current["email"], "csv_ingest", "dataset", dataset,
                    {"filename": file.filename, "rows": rows_ingested})
    return {
        "dataset": dataset,
        "rows_ingested": rows_ingested,
        "rows_failed": rows_failed,
        "lineage_id": lineage_id,
        "ingested_at": iso(datetime.now(timezone.utc)),
    }


@router.get("/admin/ingestion-runs")
async def ingestion_runs(current=Depends(get_current_user)):
    return [r async for r in db.ingestion_runs.find({}, {"_id": 0}).sort("run_end", -1).limit(50)]


# ---------- Exports ----------
def _io_bytes(data: bytes):
    return io.BytesIO(data)


def _export_scope_detail(
    entity_code: Optional[str],
    period_ym: Optional[str],
    department_id: Optional[str],
    cost_center_id: Optional[str],
) -> Dict[str, Any]:
    return {k: v for k, v in {
        "entity_code": entity_code,
        "period_ym": period_ym,
        "department_id": department_id,
        "cost_center_id": cost_center_id,
    }.items() if v}


@router.get("/reports/audit-committee-pack.pdf")
async def report_pdf(
    entity_code: Optional[str] = Query(None, description="Phase 13 — align pack with CFO reporting context"),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    current=Depends(get_current_user),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    pdf = await build_pdf(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    await audit_log(
        current["email"],
        "export_pdf",
        "report",
        "audit-committee-pack",
        detail={"filters_applied": _export_scope_detail(entity_code, period_ym, department_id, cost_center_id)},
    )
    return StreamingResponse(
        _io_bytes(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="audit-committee-pack.pdf"'},
    )


@router.get("/reports/audit-committee-pack.xlsx")
async def report_xlsx(
    entity_code: Optional[str] = Query(None, description="Phase 13 — align pack with CFO reporting context"),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    current=Depends(get_current_user),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    xlsx = await build_xlsx(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    await audit_log(
        current["email"],
        "export_xlsx",
        "report",
        "audit-committee-pack",
        detail={"filters_applied": _export_scope_detail(entity_code, period_ym, department_id, cost_center_id)},
    )
    return StreamingResponse(
        _io_bytes(xlsx),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="audit-committee-pack.xlsx"'},
    )


# ---------- External Auditor Portal (read-only) ----------
def _require_auditor_or_internal(current=Depends(get_current_user)):
    if current["role"] not in ("External Auditor", "Internal Auditor", "CFO", "Controller"):
        raise HTTPException(403, "Auditor access required")
    return current


@router.get("/auditor/pack")
async def auditor_pack(
    entity_code: Optional[str] = Query(None, description="Phase 14 — align auditor JSON pack with CFO reporting context"),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    current=Depends(_require_auditor_or_internal),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    cockpit = await cfo_cockpit(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    filters_applied = {k: v for k, v in {
        "entity_code": entity_code,
        "period_ym": period_ym,
        "department_id": department_id,
        "cost_center_id": cost_center_id,
    }.items() if v}
    controls = [c async for c in db.controls.find({}, {"_id": 0}).sort("code", 1)]
    run_q: Dict[str, Any] = {}
    if period_ym:
        run_q["run_ts"] = {"$regex": f"^{period_ym}"}
    if entity_code:
        run_q["entities"] = entity_code
    recent_runs = [
        r async for r in db.test_runs.find(run_q if run_q else {}, {"_id": 0}).sort("run_ts", -1).limit(20)
    ]
    policies = [p async for p in db.policies.find({}, {"_id": 0})]
    case_q = merge_cases_master_filters(
        {"status": {"$ne": "closed"}},
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    open_cases = [
        c async for c in db.cases.find(case_q, {"_id": 0}).sort("financial_exposure", -1).limit(25)
    ]
    return {
        "generated_at": iso(datetime.now(timezone.utc)),
        "kpis": cockpit["kpis"],
        "heatmap": cockpit["heatmap"],
        "top_risks": cockpit["top_risks"],
        "controls": controls,
        "recent_runs": recent_runs,
        "policies": policies,
        "open_cases": open_cases,
        "filters_applied": filters_applied,
    }


@router.get("/auditor/controls/{control_id}")
async def auditor_control_detail(control_id: str, current=Depends(_require_auditor_or_internal)):
    c = await db.controls.find_one({"id": control_id}, {"_id": 0})
    if not c:
        c = await db.controls.find_one({"code": control_id}, {"_id": 0})
    if not c:
        raise HTTPException(404, "Control not found")
    cid = c["id"]
    runs = [r async for r in db.test_runs.find({"control_id": cid}, {"_id": 0}).sort("run_ts", -1).limit(10)]
    exceptions = [e async for e in db.exceptions.find({"control_id": cid}, {"_id": 0}).limit(50)]
    if await entity_scope_enforced(db) and not role_bypasses_entity_scope(current):
        user = await db.users.find_one({"id": current.get("user_id")}, {"_id": 0, "entity": 1})
        ue = (user or {}).get("entity")
        if ue:
            ue_s = str(ue).strip()
            exceptions = [e for e in exceptions if str(e.get("entity") or "").strip() == ue_s]
    return {"control": c, "recent_runs": runs, "exceptions": exceptions}


# ---------- Notifications ----------
@router.get("/notifications")
async def notifications_list(limit: int = 50, current=Depends(get_current_user)):
    return await list_notifications(db, limit=limit)


@router.get("/notifications/settings")
async def notifications_settings_get(current=Depends(get_current_user)):
    return await get_notif_settings(db)


@router.patch("/notifications/settings")
async def notifications_settings_patch(patch: Dict[str, Any], current=Depends(get_current_user)):
    if current["role"] not in ("CFO", "Controller", "Internal Auditor", "Compliance Head"):
        raise HTTPException(403, "Insufficient permissions")
    result = await save_notif_settings(db, patch)
    await audit_log(current["email"], "update_notification_settings", "system", "notifications", patch)
    return result


@router.post("/notifications/scan-sla")
async def notifications_scan_now(current=Depends(get_current_user)):
    if current["role"] == "External Auditor":
        raise HTTPException(403, "Read-only auditor role cannot trigger scans")
    if await entity_scope_enforced(db) and current.get("role") != "Super Admin":
        raise HTTPException(403, "Entity scope violation")
    return await scan_sla_breaches(db)


@router.post("/notifications/daily-brief/send")
async def daily_brief_send_now(current=Depends(get_current_user)):
    if current["role"] == "External Auditor":
        raise HTTPException(403, "Read-only auditor role cannot dispatch briefs")
    if await entity_scope_enforced(db) and current.get("role") != "Super Admin":
        raise HTTPException(403, "Entity scope violation")
    result = await send_daily_brief(db)
    await audit_log(current["email"], "send_daily_brief", "notification", result.get("id", "skipped"))
    return result


# ---------- Anomaly Training ----------
@router.post("/anomaly/train")
async def anomaly_train(body: Optional[Dict[str, Any]] = Body(default=None), current=Depends(get_current_user)):
    if current["role"] not in ("CFO", "Internal Auditor", "Controller", "Super Admin"):
        raise HTTPException(403, "Training requires CFO / Controller / Internal Auditor role")
    if await entity_scope_enforced(db) and current.get("role") != "Super Admin":
        raise HTTPException(403, "Entity scope violation")
    body = body or {}
    result = await train_anomaly_model(
        db,
        trained_by=current["email"],
        notes=body.get("notes", ""),
        contamination=float(body.get("contamination", 0.06)),
        n_estimators=int(body.get("n_estimators", 100)),
    )
    if result.get("error"):
        raise HTTPException(400, result["error"])
    await audit_log(current["email"], "train_anomaly_model", "model_version", result["id"],
                    {"version_label": result["version_label"]})
    return result
