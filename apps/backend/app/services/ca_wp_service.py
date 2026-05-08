"""CA digital working papers: reference codes, folder slugs, sampling helpers."""
from __future__ import annotations

import random
import re
import uuid
from typing import Any, Dict, List


def folder_code_from_name(name: str) -> str:
    """Build WP-XXX prefix segment from folder name (e.g. Planning -> PLA)."""
    n = (name or "GEN").strip()
    parts = re.split(r"[\s/]+", n)
    letters = "".join(p[:1] for p in parts if p)[:3].upper()
    if len(letters) < 3:
        letters = (n.replace(" ", "")[:3] or "GEN").upper()
    return letters[:3]


async def next_working_paper_reference(db, engagement_id: str, folder_id: str) -> str:
    """Allocate next cross-reference e.g. WP-PLA-001 within engagement + folder group."""
    folder = await db.ca_wp_folders.find_one({"id": folder_id, "engagement_id": engagement_id}, {"_id": 0})
    code = folder_code_from_name((folder or {}).get("name") or "General")
    prefix = f"WP-{code}"
    pat = f"^{re.escape(prefix)}-\\d{{3}}$"
    existing = await db.ca_working_papers.count_documents({"engagement_id": engagement_id, "reference": {"$regex": pat}})
    return f"{prefix}-{existing + 1:03d}"


def sample_rows_for_plan(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Demo sample transactions for vouching / MUS-style listing."""
    n = min(int(plan.get("sample_size") or 5), max(1, int(plan.get("population_size") or 5)))
    rng = random.Random(plan.get("seed") if plan.get("seed") is not None else 42)
    rows: List[Dict[str, Any]] = []
    for i in range(n):
        amt = round(5000 + rng.random() * 250_000, 2)
        rows.append(
            {
                "id": str(uuid.uuid4()),
                "sampling_plan_id": plan.get("id"),
                "idx": i + 1,
                "amount": amt,
                "transaction_ref": f"TXN-{plan.get('id', 'PLAN')[:6]}-{i + 1:04d}",
                "document_ref": f"INV-{rng.randint(10000, 99999)}",
                "selection_reason": plan.get("method") or "random",
            }
        )
    return rows
