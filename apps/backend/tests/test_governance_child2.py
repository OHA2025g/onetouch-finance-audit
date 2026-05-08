"""Child prompt 2 — pure unit checks (no Mongo)."""
from datetime import datetime, timezone, timedelta

from app.governance.ensure_baseline import _hierarchy_docs
from app.services.rollup_service import _ent_filter


def test_hierarchy_seed_shape() -> None:
    docs = _hierarchy_docs()
    assert len(docs) >= 8
    roots = [d for d in docs if d["type"] == "organization"]
    assert len(roots) == 1
    entities = [d for d in docs if d.get("entity_code")]
    assert {d["entity_code"] for d in entities} == {"US-HQ", "UK-OPS", "IN-SVC", "SG-APAC"}


def test_ent_filter() -> None:
    assert _ent_filter(None) == {}
    assert _ent_filter({"US-HQ"}) == {"entity": {"$in": ["US-HQ"]}}


def test_retention_old_enough() -> None:
    from app.services import retention_service as rs

    now = datetime.now(timezone.utc)
    old = (now - timedelta(days=100)).isoformat()
    assert rs._old_enough(old, 30) is True
    assert rs._old_enough(now.isoformat(), 30) is False
