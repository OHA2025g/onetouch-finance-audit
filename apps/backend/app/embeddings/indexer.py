from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.embeddings.providers import EmbeddingProvider, HashEmbeddingProvider
from app.utils.timeutil import iso_utc


def _chunk_text(text: str, *, max_chars: int = 900) -> List[str]:
    t = (text or "").strip()
    if not t:
        return []
    if len(t) <= max_chars:
        return [t]
    chunks = []
    i = 0
    while i < len(t):
        chunks.append(t[i : i + max_chars])
        i += max_chars
    return chunks


def _risk_procedure_index_text(r: Dict[str, Any]) -> str:
    rp = r.get("racm_procedures") or []
    if rp:
        return " | ".join((p.get("title") or "") for p in rp if isinstance(p, dict))
    return " | ".join(r.get("audit_procedures") or [])


async def build_corpus(db, scope: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Return list of source items: {source_type, source_id, label, text, entity?, process?}."""
    scope = scope or {}
    out: List[Dict[str, Any]] = []
    # controls
    async for c in db.controls.find({}, {"_id": 0}):
        out.append(
            {
                "source_type": "control",
                "source_id": c["code"],
                "label": f"{c['code']} · {c['name']}",
                "text": f"Control {c['code']} {c['name']} — {c['description']} Process={c['process']} Risk={c['risk']} Criticality={c['criticality']} Framework={c.get('framework','')}",
                "entity": None,
                "process": c.get("process"),
            }
        )
    # exceptions
    q: Dict[str, Any] = {}
    if scope.get("entity"):
        q["entity"] = scope["entity"]
    if scope.get("process"):
        q["process"] = scope["process"]
    async for ex in db.exceptions.find(q, {"_id": 0}).limit(2000):
        exposure = float(ex.get("financial_exposure") or 0.0)
        sev = str(ex.get("severity") or "medium")
        out.append(
            {
                "source_type": "exception",
                "source_id": ex["id"],
                "label": f"EX-{ex['id'][:6]} · {ex['control_code']}",
                "text": f"Exception [{sev.upper()}] on {ex.get('control_code','')} ({ex.get('control_name','')}) "
                f"entity={ex.get('entity','')} process={ex.get('process','')} exposure=${exposure:,.2f} "
                f"anomaly={ex.get('anomaly_score', 0.0)} — {ex.get('title','')}. {ex.get('summary','')}",
                "entity": ex.get("entity"),
                "process": ex.get("process"),
            }
        )
    # policies
    async for p in db.policies.find({}, {"_id": 0}):
        out.append(
            {
                "source_type": "policy",
                "source_id": p["id"],
                "label": p["title"],
                "text": f"Policy '{p['title']}' effective {p['effective_date']}. Clauses: {' | '.join(p.get('clauses', []))}",
                "entity": None,
                "process": None,
            }
        )
    # cases
    cq: Dict[str, Any] = {}
    if scope.get("entity"):
        cq["entity"] = scope["entity"]
    if scope.get("process"):
        cq["process"] = scope["process"]
    async for ca in db.cases.find(cq, {"_id": 0}).limit(1000):
        exposure = float(ca.get("financial_exposure") or 0.0)
        out.append(
            {
                "source_type": "case",
                "source_id": ca["id"],
                "label": f"CASE-{ca['id'][:6]}",
                "text": f"Case status={ca['status']} priority={ca['priority']} owner={ca['owner_email']} "
                f"severity={ca.get('severity','')} exposure=${exposure:,.2f} — {ca.get('title','')} {ca.get('summary','')}",
                "entity": ca.get("entity"),
                "process": ca.get("process"),
            }
        )
    # CA audit engagements + RACM (for copilot / hybrid search)
    async for e in db.audit_engagements.find({}, {"_id": 0}).limit(200):
        out.append(
            {
                "source_type": "engagement",
                "source_id": e.get("engagement_id"),
                "label": f"Engagement {e.get('engagement_id')}",
                "text": (
                    f"Audit engagement {e.get('engagement_id')} entity={e.get('entity_name')} FY={e.get('financial_year')} "
                    f"type={e.get('audit_type')} status={e.get('status')} risk={e.get('risk_level')} "
                    f"scope={e.get('audit_scope','')} objectives={'; '.join(e.get('audit_objectives') or [])}"
                ),
                "entity": None,
                "process": None,
            }
        )
    async for r in db.ca_risks.find({}, {"_id": 0}).limit(2000):
        out.append(
            {
                "source_type": "risk",
                "source_id": r["id"],
                "label": f"RISK · {r.get('risk_title')}",
                "text": (
                    f"RACM risk [{r.get('risk_rating')}] {r.get('risk_title')} — {r.get('risk_description','')} "
                    f"category={r.get('risk_category')} process={r.get('process_area')} FS area={r.get('financial_statement_area')} "
                    f"inherent={r.get('inherent_risk_score')} residual={r.get('residual_risk_score')} "
                    f"procedures={_risk_procedure_index_text(r)}"
                ),
                "entity": None,
                "process": r.get("process_area"),
            }
        )
    async for wp in db.ca_working_papers.find({}, {"_id": 0}).limit(500):
        out.append(
            {
                "source_type": "working_paper",
                "source_id": wp["id"],
                "label": f"WP {wp.get('reference') or wp['id'][:8]}",
                "text": (
                    f"Working paper {wp.get('reference','')} engagement={wp.get('engagement_id')} title={wp.get('title','')} "
                    f"linked_cases={','.join(wp.get('linked_case_ids') or [])} linked_controls={','.join(wp.get('linked_control_ids') or [])}"
                ),
                "entity": None,
                "process": None,
            }
        )
    return out


async def rebuild_embedding_index(
    db,
    *,
    scope: Optional[Dict[str, Any]] = None,
    provider: Optional[EmbeddingProvider] = None,
) -> Dict[str, Any]:
    provider = provider or HashEmbeddingProvider()
    now = iso_utc(datetime.now(timezone.utc))
    run_id = f"eir-{uuid.uuid4().hex[:10]}"

    await db.embedding_index_runs.insert_one(
        {
            "id": run_id,
            "provider": provider.name,
            "dim": provider.dim,
            "scope": scope or {},
            "status": "running",
            "started_at": now,
            "ended_at": None,
            "chunks_indexed": 0,
            "sources_indexed": 0,
        }
    )

    if scope:
        # scoped rebuild: delete only matching chunks by metadata
        await db.embedding_chunks.delete_many({"metadata.entity": scope.get("entity"), "metadata.process": scope.get("process")})
    else:
        await db.embedding_chunks.delete_many({})

    sources = await build_corpus(db, scope=scope)
    texts: List[str] = []
    metas: List[Dict[str, Any]] = []
    for s in sources:
        for i, ch in enumerate(_chunk_text(s["text"])):
            texts.append(ch)
            metas.append(
                {
                    "source_type": s["source_type"],
                    "source_id": s["source_id"],
                    "label": s["label"],
                    "chunk_index": i,
                    "entity": s.get("entity"),
                    "process": s.get("process"),
                }
            )
    vecs = await provider.embed(texts) if texts else []

    chunk_docs = []
    for t, v, m in zip(texts, vecs, metas):
        chunk_docs.append(
            {
                "id": f"ech-{uuid.uuid4().hex[:12]}",
                "text": t,
                "vector": v,
                "provider": provider.name,
                "dim": provider.dim,
                "metadata": m,
                "created_at": now,
            }
        )
    if chunk_docs:
        await db.embedding_chunks.insert_many(chunk_docs)

    end = iso_utc(datetime.now(timezone.utc))
    await db.embedding_index_runs.update_one(
        {"id": run_id},
        {"$set": {"status": "success", "ended_at": end, "chunks_indexed": len(chunk_docs), "sources_indexed": len(sources)}},
    )
    return {"run_id": run_id, "provider": provider.name, "dim": provider.dim, "chunks_indexed": len(chunk_docs), "sources_indexed": len(sources)}

