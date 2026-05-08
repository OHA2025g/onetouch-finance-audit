from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.embeddings.providers import HashEmbeddingProvider, cosine


async def semantic_search(
    db,
    *,
    query: str,
    k: int = 8,
    scope: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Return chunks with citations compatible with existing copilot format."""
    provider = HashEmbeddingProvider()
    qv = (await provider.embed([query]))[0]
    scope = scope or {}
    q: Dict[str, Any] = {}
    if scope.get("entity"):
        q["metadata.entity"] = scope["entity"]
    if scope.get("process"):
        q["metadata.process"] = scope["process"]

    # Pull a bounded set from Mongo; this is a simple implementation (can be replaced by vector DB later).
    chunks = [c async for c in db.embedding_chunks.find(q, {"_id": 0}).limit(5000)]
    scored = []
    for c in chunks:
        s = cosine(qv, c.get("vector") or [])
        scored.append((s, c))
    scored.sort(key=lambda x: -x[0])
    out: List[Dict[str, Any]] = []
    for s, c in scored[:k]:
        m = c.get("metadata") or {}
        out.append(
            {
                "type": m.get("source_type"),
                "id": m.get("source_id"),
                "label": m.get("label"),
                "text": c.get("text"),
                "score": round(float(s), 4),
                "chunk_id": c.get("id"),
            }
        )
    return out


async def hybrid_search(db, *, query: str, k: int = 8) -> List[Dict[str, Any]]:
    """Hybrid placeholder: semantic only today; keep function so we can merge TF-IDF later."""
    return await semantic_search(db, query=query, k=k)

