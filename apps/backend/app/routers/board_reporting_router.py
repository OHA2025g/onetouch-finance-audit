"""Wave 4 — Board reporting templates API (stubs + versioning hooks)."""

from __future__ import annotations

import io
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.core.security import require_roles
from app.deps import db, audit_log, iso
from datetime import datetime, timezone
from app.exports import build_pdf, build_xlsx

router = APIRouter(prefix="/reports", tags=["reports"])

EXPORT_FORMATS = ["pdf", "xlsx", "pptx"]


def _io_bytes(data: bytes):
    return io.BytesIO(data)


def _seed_templates() -> List[Dict[str, Any]]:
    # Phase 39 — SRS template library seed.
    return [
        {"id": "tpl-cfo-monthly-pack", "name": "CFO monthly pack", "default_format": "pdf", "status": "seed"},
        {"id": "tpl-audit-committee-pack", "name": "Audit committee pack", "default_format": "pdf", "status": "seed"},
        {"id": "tpl-internal-control-report", "name": "Internal control report", "default_format": "pdf", "status": "seed"},
        {"id": "tpl-compliance-exposure-report", "name": "Compliance exposure report", "default_format": "pdf", "status": "seed"},
        {"id": "tpl-working-capital-report", "name": "Working capital report", "default_format": "xlsx", "status": "seed"},
        {"id": "tpl-cash-forecast-report", "name": "Cash forecast report", "default_format": "xlsx", "status": "seed"},
        {"id": "tpl-month-end-close-report", "name": "Month-end close report", "default_format": "xlsx", "status": "seed"},
        {"id": "tpl-budget-variance-report", "name": "Budget variance report", "default_format": "xlsx", "status": "seed"},
        {"id": "tpl-gl-audit-report", "name": "GL audit report", "default_format": "xlsx", "status": "seed"},
        {"id": "tpl-journal-risk-report", "name": "Journal risk report", "default_format": "xlsx", "status": "seed"},
        {"id": "tpl-vendor-risk-report", "name": "Vendor risk report", "default_format": "xlsx", "status": "seed"},
        {"id": "tpl-revenue-assurance-report", "name": "Revenue assurance report", "default_format": "xlsx", "status": "seed"},
        {"id": "tpl-inventory-audit-report", "name": "Inventory audit report", "default_format": "xlsx", "status": "seed"},
        {"id": "tpl-treasury-risk-report", "name": "Treasury risk report", "default_format": "xlsx", "status": "seed"},
        {"id": "tpl-rpt-report", "name": "RPT report", "default_format": "pdf", "status": "seed"},
        {"id": "tpl-litigation-exposure-report", "name": "Litigation exposure report", "default_format": "pdf", "status": "seed"},
        {"id": "tpl-sod-conflict-report", "name": "SoD conflict report", "default_format": "xlsx", "status": "seed"},
        # Phase 39 — optional / placeholder PPT export
        {"id": "tpl-board-deck", "name": "Board deck (PowerPoint)", "default_format": "pptx", "status": "seed"},
    ]


async def _ensure_seed_templates() -> List[Dict[str, Any]]:
    cur = db.report_templates.find({}, {"_id": 0}).sort("name", 1).limit(200)
    items = [t async for t in cur]
    if items:
        return items
    seeds = _seed_templates()
    await db.report_templates.insert_many([dict(t) for t in seeds])
    return seeds


async def _next_version(db, template_id: str) -> str:
    now = iso(datetime.now(timezone.utc))
    doc = await db.report_template_versions.find_one_and_update(
        {"id": template_id},
        {"$inc": {"counter": 1}, "$setOnInsert": {"id": template_id, "created_at": now}, "$set": {"updated_at": now}},
        upsert=True,
        return_document=True,  # type: ignore[arg-type]
        projection={"_id": 0},
    )
    counter = int((doc or {}).get("counter") or 1)
    return f"1.{counter}"


@router.get("/templates")
async def list_templates(current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head", "Super Admin"))):
    items = await _ensure_seed_templates()
    return {"items": items, "export_formats": EXPORT_FORMATS, "note": "Phase 39 seed library + lightweight generator."}


@router.post("/templates/{template_id}/signoff")
async def template_signoff(
    template_id: str,
    body: Dict[str, Any] = Body(default={}),
    current=Depends(require_roles("CFO", "Super Admin")),
):
    await audit_log(
        current["email"],
        "signoff",
        "report_template",
        template_id,
        {"version": body.get("version")},
    )
    return {
        "template_id": template_id,
        "signed_off_by": current["email"],
        "signed_off_at": iso(datetime.now(timezone.utc)),
        "version": body.get("version") or "1.0",
    }


@router.get("/versions")
async def report_versions(
    template_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head", "Super Admin")),
):
    q: Dict[str, Any] = {}
    if template_id:
        q["template_id"] = template_id
    cur = db.reports.find(q, {"_id": 0, "id": 1, "template_id": 1, "version": 1, "generated_at": 1, "status": 1}).sort("generated_at", -1).limit(limit)
    items = [r async for r in cur]
    return {"items": items, "count": len(items)}


@router.post("/generate")
async def generate_report(
    body: Dict[str, Any] = Body(...),
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head", "Super Admin")),
):
    await _ensure_seed_templates()
    template_id = body.get("template_id") or body.get("template")
    if not template_id:
        raise HTTPException(400, "template_id is required")
    tpl = await db.report_templates.find_one({"id": template_id}, {"_id": 0})
    if not tpl:
        raise HTTPException(404, "Template not found")
    requested_format = (body.get("format") or tpl.get("default_format") or "pdf").lower()
    if requested_format not in EXPORT_FORMATS:
        raise HTTPException(400, f"format must be one of: {', '.join(EXPORT_FORMATS)}")
    filters_applied = body.get("filters") or {}

    rid = f"rep-{uuid.uuid4().hex[:10]}"
    now = iso(datetime.now(timezone.utc))
    version = await _next_version(db, template_id)
    doc = {
        "id": rid,
        "template_id": template_id,
        "template_name": tpl.get("name"),
        "version": version,
        "format": requested_format,
        "filters": filters_applied,
        "status": "generated",
        "generated_at": now,
        "generated_by": current["email"],
        "signed_off_at": None,
        "signed_off_by": None,
    }
    await db.reports.insert_one(dict(doc))
    await audit_log(current["email"], "report_generate", "report", rid, {"template_id": template_id, "format": requested_format, "version": version})
    return doc


@router.get("/{report_id}")
async def get_report(
    report_id: str,
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head", "Super Admin")),
):
    r = await db.reports.find_one({"id": report_id}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Report not found")
    return r


@router.post("/{report_id}/signoff")
async def signoff_report(
    report_id: str,
    body: Dict[str, Any] = Body(default={}),
    current=Depends(require_roles("CFO", "Super Admin")),
):
    r = await db.reports.find_one({"id": report_id}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Report not found")
    now = iso(datetime.now(timezone.utc))
    await db.reports.update_one(
        {"id": report_id},
        {"$set": {"signed_off_at": now, "signed_off_by": current["email"], "status": "signed_off", "signoff_note": body.get("note")}},
    )
    await audit_log(current["email"], "report_signoff", "report", report_id, {"template_id": r.get("template_id"), "version": r.get("version")})
    return await db.reports.find_one({"id": report_id}, {"_id": 0})


@router.post("/{report_id}/export")
async def export_report(
    report_id: str,
    body: Dict[str, Any] = Body(default={}),
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head", "Super Admin")),
):
    r = await db.reports.find_one({"id": report_id}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Report not found")
    fmt = (body.get("format") or r.get("format") or "pdf").lower()
    if fmt not in EXPORT_FORMATS:
        raise HTTPException(400, f"format must be one of: {', '.join(EXPORT_FORMATS)}")

    filters_applied = r.get("filters") or {}
    entity_code = filters_applied.get("entity_code")
    period_ym = filters_applied.get("period_ym")
    department_id = filters_applied.get("department_id")
    cost_center_id = filters_applied.get("cost_center_id")

    if fmt == "pdf":
        pdf = await build_pdf(db, entity_code=entity_code, period_ym=period_ym, department_id=department_id, cost_center_id=cost_center_id)
        await audit_log(current["email"], "report_export_pdf", "report", report_id, {"template_id": r.get("template_id"), "version": r.get("version")})
        return StreamingResponse(
            _io_bytes(pdf),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{r.get("template_id","report")}-{r.get("version","1.0")}.pdf"'},
        )

    if fmt == "xlsx":
        xlsx = await build_xlsx(db, entity_code=entity_code, period_ym=period_ym, department_id=department_id, cost_center_id=cost_center_id)
        await audit_log(current["email"], "report_export_xlsx", "report", report_id, {"template_id": r.get("template_id"), "version": r.get("version")})
        return StreamingResponse(
            _io_bytes(xlsx),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{r.get("template_id","report")}-{r.get("version","1.0")}.xlsx"'},
        )

    # pptx placeholder (Phase 39)
    payload = (
        "OneTouch Finance Audit AI\n"
        f"Template: {r.get('template_name')}\n"
        f"Version: {r.get('version')}\n"
        "Note: PPTX generator is a placeholder in this build.\n"
    ).encode("utf-8")
    await audit_log(current["email"], "report_export_pptx", "report", report_id, {"template_id": r.get("template_id"), "version": r.get("version")})
    return StreamingResponse(
        _io_bytes(payload),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f'attachment; filename="{r.get("template_id","report")}-{r.get("version","1.0")}.pptx"'},
    )
