"""TF-IDF vector store for copilot RAG retrieval.

Lightweight, local, no external embedding calls. Rebuilt in-memory at startup and on demand.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class VectorDoc:
    doc_type: str
    doc_id: str
    label: str
    text: str


class VectorIndex:
    def __init__(self):
        self.docs: List[VectorDoc] = []
        self.matrix = None
        self.vectorizer: Optional[TfidfVectorizer] = None

    def _fit(self):
        if not self.docs:
            self.matrix = None
            self.vectorizer = None
            return
        self.vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            max_features=8000,
            sublinear_tf=True,
        )
        self.matrix = self.vectorizer.fit_transform([d.text for d in self.docs])

    async def rebuild(self, db) -> int:
        docs: List[VectorDoc] = []
        async for c in db.controls.find({}, {"_id": 0}):
            docs.append(VectorDoc(
                "control", c["code"],
                f"{c['code']} · {c['name']}",
                f"Control {c['code']} {c['name']} — {c['description']} Process={c['process']} Risk={c['risk']} Criticality={c['criticality']} Framework={c.get('framework','')}",
            ))
        async for ex in db.exceptions.find({}, {"_id": 0}).limit(1000):
            docs.append(VectorDoc(
                "exception", ex["id"],
                f"EX-{ex['id'][:6]} · {ex['control_code']}",
                f"Exception [{ex['severity'].upper()}] on {ex['control_code']} ({ex['control_name']}) "
                f"entity={ex['entity']} process={ex['process']} exposure=${ex['financial_exposure']:,.2f} "
                f"anomaly={ex['anomaly_score']} — {ex['title']}. {ex['summary']}",
            ))
        async for p in db.policies.find({}, {"_id": 0}):
            docs.append(VectorDoc(
                "policy", p["id"],
                p["title"],
                f"Policy '{p['title']}' effective {p['effective_date']}. Clauses: {' | '.join(p.get('clauses', []))}",
            ))
        async for ca in db.cases.find({}, {"_id": 0}).limit(200):
            docs.append(VectorDoc(
                "case", ca["id"],
                f"CASE-{ca['id'][:6]}",
                f"Case status={ca['status']} priority={ca['priority']} owner={ca['owner_email']} "
                f"severity={ca['severity']} exposure=${ca['financial_exposure']:,.2f} — {ca['title']} {ca.get('summary','')}",
            ))
        self.docs = docs
        self._fit()
        return len(docs)

    def search(self, query: str, k: int = 8) -> List[Dict[str, Any]]:
        if self.matrix is None or not self.docs:
            return []
        q_vec = self.vectorizer.transform([query])
        sims = cosine_similarity(q_vec, self.matrix)[0]
        # Top-k indices (non-zero similarity preferred)
        top_idx = np.argsort(-sims)[:k]
        results: List[Dict[str, Any]] = []
        for i in top_idx:
            score = float(sims[i])
            if score <= 0 and len(results) >= k // 2:
                break
            d = self.docs[i]
            results.append({
                "type": d.doc_type,
                "id": d.doc_id,
                "label": d.label,
                "text": d.text,
                "score": round(score, 4),
            })
        return results


# Shared singleton used by copilot
INDEX = VectorIndex()
