"""Evidence graph, copilot, drill, insights, anomaly, vector store endpoints."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.core.entity_scope import entity_scope_enforced
from app.deps import db, audit_log
from app.models import EvidenceGraph, CopilotAskRequest, CopilotAnswer
from app.analytics import evidence_graph
from app.copilot import ask_copilot
from app.drill import drill
from app.insights import get_insights as insights_get, SECTIONS as INSIGHT_SECTIONS
from app.services.rbac_service import (
    assert_exception_entity_scope,
    enforce_drill_entity_scope,
    enforce_entity_scope,
)

router = APIRouter(tags=["evidence-ai"])

_COPILOT_INJECTION_MARKERS = (
    "ignore previous instructions",
    "disregard the above",
    "system prompt",
    "ignore all prior rules",
)


async def _enforce_copilot_rate_limit(email: str) -> None:
    cap = int(os.environ.get("COPILOT_REQUESTS_PER_MINUTE", "60"))
    if cap <= 0:
        return
    minute_key = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    doc_id = f"{email}:{minute_key}"
    await db.copilot_usage_buckets.update_one(
        {"id": doc_id},
        {"$inc": {"count": 1}, "$setOnInsert": {"email": email, "minute_key": minute_key}},
        upsert=True,
    )
    doc = await db.copilot_usage_buckets.find_one({"id": doc_id}, {"_id": 0, "count": 1})
    if doc and int(doc.get("count") or 0) > cap:
        raise HTTPException(429, "Copilot rate limit exceeded for this user; try again shortly.")


def _reject_obvious_prompt_injection(question: str) -> None:
    q = question.lower()
    if any(m in q for m in _COPILOT_INJECTION_MARKERS):
        raise HTTPException(400, "Prompt rejected by input safety filter")


@router.get("/evidence/{exception_id}", response_model=EvidenceGraph)
async def evidence(exception_id: str, current=Depends(get_current_user)):
    from app.services import legal_hold_service as ghs
    from app.services import worm_service as ws

    ex0 = await db.exceptions.find_one({"id": exception_id}, {"_id": 0})
    if ex0:
        await assert_exception_entity_scope(db, current=current, exception=ex0)

    graph = await evidence_graph(db, exception_id)
    on_hold = await ghs.is_held(db, "evidence", exception_id)
    worm, _ = await ws.is_worm_locked(db, ws.REF_EVIDENCE, exception_id)
    return {
        **graph,
        "governance": {"legal_hold": on_hold, "worm": worm},
    }


@router.post("/copilot/ask", response_model=CopilotAnswer)
async def copilot_ask(body: CopilotAskRequest, current=Depends(get_current_user)):
    await _enforce_copilot_rate_limit(current["email"])
    _reject_obvious_prompt_injection(body.question)
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=body.entity_code)
    scope = {k: v for k, v in {
        "entity": entity_code,
        # period/department/cost center are accepted for forward-compat but not used by the current indexer yet
        "period_ym": body.period_ym,
        "department_id": body.department_id,
        "cost_center_id": body.cost_center_id,
    }.items() if v}
    out = await ask_copilot(
        db,
        body.question,
        current["email"],
        body.session_id,
        mode=body.mode,
        user_role=current.get("role"),
        scope=scope or None,
    )
    await audit_log(current["email"], "copilot_ask", "copilot_session", out["session_id"], {"q": body.question})
    return out


def _copilot_mode_for_role(role: str) -> str:
    r = (role or "").strip().lower()
    if "cfo" in r:
        return "cfo"
    if "controller" in r:
        return "controller"
    if "auditor" in r:
        return "auditor"
    if "compliance" in r:
        return "compliance"
    if "treasury" in r:
        return "treasury"
    return "controller"


@router.post("/copilot/generate-cfo-summary", response_model=CopilotAnswer)
async def copilot_generate_cfo_summary(body: Dict[str, Any], current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=body.get("entity_code"))
    period_ym = body.get("period_ym")
    q = (
        "Generate a CFO executive summary for the current period."
        + (f" Entity: {entity_code}." if entity_code else "")
        + (f" Period: {period_ym}." if period_ym else "")
        + " Include: liquidity watch, working capital, top exceptions/cases, compliance exposure, and recommended actions."
    )
    out = await ask_copilot(
        db,
        q,
        current["email"],
        body.get("session_id"),
        mode="cfo",
        user_role=current.get("role"),
        scope={"entity": entity_code} if entity_code else None,
    )
    await audit_log(current["email"], "copilot_generate_cfo_summary", "copilot_session", out["session_id"], {"entity_code": entity_code, "period_ym": period_ym})
    return out


@router.post("/copilot/generate-audit-procedure", response_model=CopilotAnswer)
async def copilot_generate_audit_procedure(body: Dict[str, Any], current=Depends(get_current_user)):
    # Use explicit prompt + retrieved evidence to generate an audit procedure checklist.
    topic = body.get("topic") or body.get("control_code") or body.get("subject") or "the specified control area"
    entity_code = body.get("entity_code")
    q = (
        f"Generate a practical audit procedure checklist for {topic}."
        + (f" Entity: {entity_code}." if entity_code else "")
        + " Include sampling guidance, evidence to request, red flags, and how to document conclusions."
    )
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=body.get("entity_code"))
    out = await ask_copilot(
        db,
        q,
        current["email"],
        body.get("session_id"),
        mode=_copilot_mode_for_role(current.get("role") or "auditor"),
        user_role=current.get("role"),
        scope={"entity": entity_code} if entity_code else None,
    )
    await audit_log(current["email"], "copilot_generate_audit_procedure", "copilot_session", out["session_id"], {"topic": topic, "entity_code": entity_code})
    return out


@router.post("/copilot/generate-board-summary", response_model=CopilotAnswer)
async def copilot_generate_board_summary(body: Dict[str, Any], current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=body.get("entity_code"))
    period_ym = body.get("period_ym")
    q = (
        "Generate an audit committee / board-ready summary."
        + (f" Entity: {entity_code}." if entity_code else "")
        + (f" Period: {period_ym}." if period_ym else "")
        + " Focus on material issues, trends, key risks, remediation status, and management actions. Keep it concise."
    )
    out = await ask_copilot(
        db,
        q,
        current["email"],
        body.get("session_id"),
        mode="cfo",
        user_role=current.get("role"),
        scope={"entity": entity_code} if entity_code else None,
    )
    await audit_log(current["email"], "copilot_generate_board_summary", "copilot_session", out["session_id"], {"entity_code": entity_code, "period_ym": period_ym})
    return out


@router.get("/copilot/sessions")
async def copilot_sessions(
    limit: int = 30,
    entity_code: Optional[str] = Query(None, description="Legal entity key; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return [s async for s in db.copilot_sessions.find(
        {"user_email": current["email"]}, {"_id": 0}
    ).sort("created_at", -1).limit(limit)]


@router.post("/copilot/rebuild-index")
async def copilot_rebuild_index(current=Depends(get_current_user)):
    if current["role"] == "External Auditor":
        raise HTTPException(403, "Read-only auditor role cannot rebuild indices")
    if await entity_scope_enforced(db) and current.get("role") != "Super Admin":
        raise HTTPException(403, "Entity scope violation")
    from app.services.governance_approval_service import require_approval_or_raise
    await require_approval_or_raise(db, action="copilot_rebuild_index", subject_type="copilot", subject_id="index")
    # Prefer semantic embeddings index rebuild; TF-IDF remains as fallback.
    from app.embeddings.indexer import rebuild_embedding_index

    out = await rebuild_embedding_index(db, scope=None)
    await audit_log(current["email"], "rebuild_index", "embedding_index", out["run_id"], out)
    # Backward compatible response for legacy tests/clients
    return {**out, "indexed_docs": out.get("chunks_indexed", 0)}


# Backwards/alt alias requested in Phase 37 checklist.
@router.post("/copilot/reindex")
async def copilot_reindex(current=Depends(get_current_user)):
    return await copilot_rebuild_index(current=current)


@router.post("/copilot/reindex-scope")
async def copilot_reindex_scope(
    body: Dict[str, Any],
    current=Depends(get_current_user),
):
    if current["role"] == "External Auditor":
        raise HTTPException(403, "Read-only auditor role cannot rebuild indices")
    if await entity_scope_enforced(db) and current.get("role") != "Super Admin":
        raise HTTPException(403, "Entity scope violation")
    from app.services.governance_approval_service import require_approval_or_raise
    await require_approval_or_raise(db, action="copilot_rebuild_index", subject_type="copilot", subject_id="index")
    from app.embeddings.indexer import rebuild_embedding_index

    scope = body.get("scope") or {}
    out = await rebuild_embedding_index(db, scope=scope)
    await audit_log(current["email"], "reindex_scope", "embedding_index", out["run_id"], {"scope": scope, **out})
    return {**out, "indexed_docs": out.get("chunks_indexed", 0)}


@router.get("/copilot/retrieval-configs")
async def copilot_retrieval_configs(
    entity_code: Optional[str] = Query(None, description="Legal entity key; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return [c async for c in db.retrieval_config_versions.find({}, {"_id": 0}).sort("created_at", -1).limit(20)]


@router.get("/copilot/index-status")
async def copilot_index_status(
    entity_code: Optional[str] = Query(None, description="Legal entity key; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    emb_count = await db.embedding_chunks.count_documents({})
    # Self-heal: if index is empty (e.g., first boot after DB reset), rebuild once.
    # When entity RBAC scope is on, avoid implicit org-wide reindex for non–Super Admin callers.
    if emb_count == 0:
        allow_heal = (not await entity_scope_enforced(db)) or current.get("role") == "Super Admin"
        if allow_heal:
            try:
                from app.embeddings.indexer import rebuild_embedding_index

                await rebuild_embedding_index(db, scope=None)
            except Exception:
                # Degrade gracefully; caller sees empty index status.
                pass
            emb_count = await db.embedding_chunks.count_documents({})

    last_run = [r async for r in db.embedding_index_runs.find({}, {"_id": 0}).sort("started_at", -1).limit(1)]
    # Backward compatible shape expected by iteration2 tests
    return {
        "indexed_docs": emb_count,
        "matrix_shape": [emb_count, 64],
        "algorithm": "Semantic embeddings (hash-v1) with TF-IDF fallback",
        "semantic": {"chunks": emb_count, "last_run": last_run[0] if last_run else None, "provider": "hash-v1"},
        "legacy_tfidf": {"enabled": True, "note": "Fallback only (requires sklearn runtime)"},
    }


@router.post("/anomaly/recalibrate")
async def anomaly_recalibrate(current=Depends(get_current_user)):
    if current["role"] not in ("CFO", "Controller", "Internal Auditor", "Super Admin"):
        raise HTTPException(403, "Insufficient permissions")
    if await entity_scope_enforced(db) and current.get("role") != "Super Admin":
        raise HTTPException(403, "Entity scope violation")
    from app.anomaly import recalibrate_anomaly_scores  # local: optional numeric stack

    result = await recalibrate_anomaly_scores(db)
    await audit_log(current["email"], "recalibrate_anomaly", "system", "anomaly", result)
    return result


@router.get("/drill/{type_}/{id_:path}")
async def drill_endpoint(type_: str, id_: str, current=Depends(get_current_user)):
    result = await drill(db, type_, id_)
    if result.get("error") == "not_found":
        raise HTTPException(404, f"{type_} '{id_}' not found")
    if result.get("error") == "unknown_type":
        raise HTTPException(400, f"Unknown drill type: {type_}")
    await enforce_drill_entity_scope(db, current=current, result=result)
    return result


@router.get("/insights/{section}")
async def insights_endpoint(
    section: str,
    refresh: bool = Query(False),
    entity_code: Optional[str] = Query(None, description="Phase 8 — scope all insight snapshots (matches dashboards)"),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    current=Depends(get_current_user),
):
    if section not in INSIGHT_SECTIONS:
        raise HTTPException(400, f"Unknown section. Supported: {', '.join(INSIGHT_SECTIONS.keys())}")
    if current["role"] == "External Auditor" and section not in ("evidence", "audit", "risk"):
        raise HTTPException(403, "Read-only auditor role cannot access this insight section")
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    scope = {k: v for k, v in {
        "entity_code": entity_code,
        "period_ym": period_ym,
        "department_id": department_id,
        "cost_center_id": cost_center_id,
    }.items() if v}
    result = await insights_get(
        db, section, current["email"], current["role"],
        force_refresh=refresh, scope=scope or None,
    )
    if result.get("error"):
        raise HTTPException(400, result["error"])
    return result


@router.get("/evidence-intelligence/summary")
async def evidence_intelligence_summary(
    entity_code: Optional[str] = Query(None, description="Legal entity key; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    ex_q: Dict[str, Any] = {"status": {"$ne": "closed"}}
    if await entity_scope_enforced(db) and current.get("role") != "Super Admin":
        user = await db.users.find_one({"id": current.get("user_id")}, {"_id": 0, "entity": 1})
        ue = (user or {}).get("entity")
        if ue:
            ex_q["entity"] = ue
    open_ex = await db.exceptions.count_documents(ex_q)
    return {
        "namespace": "evidence-intelligence",
        "open_exceptions": open_ex,
        "ocr_queue_depth": 0,
        "quality_score_avg": None,
        "notes": "Aligns with evidence AI + review queue (Wave 4).",
    }
