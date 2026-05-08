"""AI Copilot RAG over controls/exceptions/cases/policies using emergentintegrations + Gemini.

Retrieval is TF-IDF vector search over the finance-audit corpus (see vector_store.py).
For each answer we produce citations and flag material conclusions for human review.
"""
from __future__ import annotations
import os
import uuid
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

try:
    # Optional dependency: local dev/test should still import the app without it.
    from emergentintegrations.llm.chat import LlmChat, UserMessage  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    LlmChat = None  # type: ignore
    UserMessage = None  # type: ignore


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


MODEL_PROVIDER = "gemini"
MODEL_NAME = "gemini-3-flash-preview"

SYSTEM_PROMPT = (
    "You are One Touch Audit AI Copilot — a finance-audit assistant for CFOs, controllers, internal auditors, and statutory audit teams. "
    "You may receive context on controls, exceptions, cases, policies, audit engagements, RACM risks, materiality, working papers, and compliance checklists. "
    "Rules:\n"
    "1. Answer ONLY from the provided CONTEXT. If the context is insufficient, say so and recommend what additional evidence is needed.\n"
    "2. Cite every numeric or control-specific claim inline using [#n] where n is the index of the source in the CONTEXT list.\n"
    "3. Quantify financial exposure when possible. Prefer concise, executive language; translate audit jargon for CFO questions.\n"
    "4. For control weaknesses, suggest practical remediation and monitoring.\n"
    "5. For any materially impactful recommendation, end with: 'ACTION_REVIEW: human approval required.'\n"
    "6. Never fabricate transaction IDs, control codes, dollar amounts, or user names."
)


async def _retrieve_context(db, question: str, k: int = 8) -> List[Dict[str, Any]]:
    """Retrieval via semantic embeddings, with TF-IDF fallback if embeddings not built."""
    try:
        from app.embeddings.retrieval import hybrid_search

        # If embeddings are empty, do not auto-rebuild here (admins control index lifecycle).
        count = await db.embedding_chunks.count_documents({})
        if count > 0:
            return await hybrid_search(db, query=question, k=k)
    except Exception:
        pass
    # Fallback to legacy TF-IDF (may require sklearn; keep lazy import)
    from .vector_store import INDEX
    if INDEX.matrix is None or not INDEX.docs:
        await INDEX.rebuild(db)
    return INDEX.search(question, k=k)


MODE_PROMPTS: Dict[str, str] = {
    "cfo": "Mode: CFO — emphasize liquidity, materiality, committee-ready narrative, and escalation paths.",
    "controller": "Mode: Controller — emphasize close quality, reconciliations, JE risk, and policy compliance.",
    "auditor": "Mode: Auditor — emphasize control evidence, sampling, and exception defensibility.",
    "compliance": "Mode: Compliance — emphasize policy, SoD, regulatory hooks, and attestation language.",
    "treasury": "Mode: Treasury — emphasize cash, funding, covenants, and bank controls.",
}


async def ask_copilot(
    db,
    question: str,
    user_email: str,
    session_id: Optional[str] = None,
    mode: Optional[str] = None,
) -> Dict[str, Any]:
    api_key = os.environ.get("EMERGENT_LLM_KEY", "")
    session_id = session_id or str(uuid.uuid4())

    context = await _retrieve_context(db, question, k=8)
    context_block = "\n".join([f"[#{i+1}] ({c['type']}) {c['label']}\n{c['text']}" for i, c in enumerate(context)])

    user_prompt = (
        f"CONTEXT (top-{len(context)} retrieved items):\n{context_block}\n\n"
        f"QUESTION: {question}\n\n"
        "Answer concisely with inline [#n] citations. If the question asks for totals, compute from the context."
    )

    confidence = 0.6
    needs_review = False
    answer_text = ""
    system_message = SYSTEM_PROMPT
    if mode:
        m = mode.strip().lower()
        hint = MODE_PROMPTS.get(m)
        if hint:
            system_message = f"{SYSTEM_PROMPT}\n\n{hint}"
    try:
        if LlmChat is None or UserMessage is None:
            raise RuntimeError("Optional dependency 'emergentintegrations' is not installed")
        chat = LlmChat(api_key=api_key, session_id=session_id, system_message=system_message).with_model(MODEL_PROVIDER, MODEL_NAME)
        response = await chat.send_message(UserMessage(text=user_prompt))
        answer_text = str(response).strip()
        # Simple heuristic: confidence scales with number of citations referenced
        cited = len(set(re.findall(r"\[#(\d+)\]", answer_text)))
        confidence = min(0.95, 0.5 + cited * 0.07)
        needs_review = "ACTION_REVIEW" in answer_text or any(
            kw in question.lower() for kw in ["material", "write off", "close", "committee", "restate"]
        )
    except Exception as e:
        err_msg = str(e)
        # Detect known budget exhaustion case for a clean operator-friendly message
        if "budget" in err_msg.lower() or "BadRequestError" in err_msg:
            friendly = "AI generation is paused (model budget exhausted). Please top up the Emergent LLM key from Profile → Universal Key → Add Balance."
        else:
            friendly = "AI generation is temporarily unavailable. Retrieved evidence context is shown below — human review recommended."
        answer_text = (
            f"{friendly}\n\nRelevant context retrieved:\n\n"
            + context_block[:1800]
        )
        confidence = 0.2
        needs_review = True

    citations = [
        {
            "source_type": c["type"],
            "source_id": c["id"],
            "label": c["label"],
            "snippet": c["text"][:220],
        }
        for c in context
    ]

    now = _iso(datetime.now(timezone.utc))
    session_doc = {
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "user_email": user_email,
        "model": f"{MODEL_PROVIDER}/{MODEL_NAME}",
        "prompt_version": "P-001",
        "question": question,
        "answer": answer_text,
        "confidence": confidence,
        "needs_human_review": needs_review,
        "citations": citations,
        "created_at": now,
        "mode": mode,
    }
    await db.copilot_sessions.insert_one(dict(session_doc))

    return {
        "session_id": session_id,
        "question": question,
        "answer": answer_text,
        "confidence": confidence,
        "model": f"{MODEL_PROVIDER}/{MODEL_NAME}",
        "citations": citations,
        "needs_human_review": needs_review,
        "created_at": now,
        "mode": mode,
    }
