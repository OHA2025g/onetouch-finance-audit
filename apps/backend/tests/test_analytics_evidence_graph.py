"""evidence_graph() working-paper linkage (fake async DB, no Mongo)."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from app.analytics import evidence_graph


class FakeCursor:
    def __init__(self, items: List[Dict[str, Any]]):
        self._items = items
        self._i = 0

    def __aiter__(self):
        self._i = 0
        return self

    async def __anext__(self) -> Dict[str, Any]:
        if self._i >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._i]
        self._i += 1
        return item


class FakeCollection:
    def __init__(self, *, find_one_result: Any = None, find_items: Optional[List[Dict[str, Any]]] = None):
        self._find_one_result = find_one_result
        self._find_items = find_items if find_items is not None else []

    async def find_one(self, *args: Any, **kwargs: Any) -> Any:
        return self._find_one_result

    def find(self, *args: Any, **kwargs: Any) -> FakeCursor:
        return FakeCursor(self._find_items)


class FakeDB:
    def __init__(self, mapping: Dict[str, FakeCollection]) -> None:
        self._mapping = mapping

    def __getattr__(self, name: str) -> FakeCollection:
        return self._mapping.get(name, FakeCollection())


def test_evidence_graph_adds_working_paper_when_case_on_engagement() -> None:
    ex: Dict[str, Any] = {
        "id": "ex-wp",
        "control_id": "ctl1",
        "control_code": "C-AP-01",
        "title": "Exposure",
        "severity": "high",
        "financial_exposure": 100.0,
        "source_record_type": "user",
        "source_record_id": "u1",
    }
    ctl = {"id": "ctl1", "code": "C-AP", "name": "AP control", "criticality": "high"}
    case = {
        "id": "case-99",
        "title": "Investigation",
        "status": "open",
        "engagement_id": "ENG-1",
        "exception_id": "ex-wp",
    }
    wp = {
        "id": "wp-1",
        "reference": "WP-001",
        "title": "Fieldwork memo",
        "engagement_id": "ENG-1",
        "linked_case_ids": ["case-99"],
    }

    db = FakeDB(
        {
            "exceptions": FakeCollection(find_one_result=ex),
            "controls": FakeCollection(find_one_result=ctl),
            "cases": FakeCollection(find_one_result=case),
            "policies": FakeCollection(find_one_result=None),
            "ca_working_papers": FakeCollection(find_items=[wp]),
        }
    )

    async def run() -> Dict[str, Any]:
        return await evidence_graph(db, "ex-wp")

    g = asyncio.run(run())
    types = {n["type"] for n in g["nodes"]}
    assert "working_paper" in types
    assert any(e.get("relation") == "documents_case" for e in g["edges"])
    wp_nodes = [n for n in g["nodes"] if n["type"] == "working_paper"]
    assert wp_nodes[0]["meta"].get("engagement_id") == "ENG-1"
