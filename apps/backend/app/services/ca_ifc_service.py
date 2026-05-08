"""IFC evaluation: library enrichment, effectiveness heatmap, case linkage helpers."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

_SCORE_RANK = {"ineffective": 1, "partially_effective": 2, "effective": 3, "deficient": 1, "pending": 0, "not_tested": 0}


def effectiveness_from_test_row(t: Dict[str, Any]) -> Optional[str]:
    raw = t.get("effectiveness_score") or t.get("result")
    if raw in ("effective", "partially_effective", "ineffective"):
        return raw
    if raw == "deficient":
        return "ineffective"
    return None


def effectiveness_numeric(eff: Optional[str]) -> int:
    if not eff:
        return 0
    return int(_SCORE_RANK.get(eff, 0))


def enrich_library_item(item: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(item)
    if not out.get("objectives"):
        out["objectives"] = [
            {
                "id": str(uuid.uuid4()),
                "statement": f"Mitigate misstatement risk addressed by control {out.get('code', '')}".strip(),
            }
        ]
    if not out.get("activities"):
        out["activities"] = [
            {"id": str(uuid.uuid4()), "description": "Perform control and retain evidence", "frequency": "per transaction / period"},
        ]
    if not out.get("owners"):
        out["owners"] = [{"email": "control.owner@entity.com", "name": "Control Owner", "role": "process_owner"}]
    return out


def normalize_library_write(body: Dict[str, Any]) -> Dict[str, Any]:
    """Assign ids to nested objectives/activities/owners on insert."""
    out = dict(body)
    objs = []
    for o in out.get("objectives") or []:
        if not isinstance(o, dict):
            continue
        objs.append({"id": o.get("id") or str(uuid.uuid4()), "statement": o.get("statement", "")})
    acts = []
    for a in out.get("activities") or []:
        if not isinstance(a, dict):
            continue
        acts.append(
            {
                "id": a.get("id") or str(uuid.uuid4()),
                "description": a.get("description", ""),
                "frequency": a.get("frequency"),
            }
        )
    own = []
    for u in out.get("owners") or []:
        if not isinstance(u, dict) or not u.get("email"):
            continue
        own.append(
            {
                "email": u["email"],
                "name": u.get("name"),
                "role": u.get("role"),
            }
        )
    out["objectives"] = objs
    out["activities"] = acts
    out["owners"] = own
    return out


def build_ifc_heatmap(tests: List[Dict[str, Any]], library_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Matrix: process (rows) vs effectiveness score (columns) — cell = count of tests in that bucket.
    """
    library_by_id: Dict[str, Dict[str, Any]] = {}
    for it in library_items:
        e = enrich_library_item(dict(it))
        if e.get("id"):
            library_by_id[str(e["id"])] = e
        if e.get("code"):
            library_by_id[str(e["code"])] = e
    cols = ["effective", "partially_effective", "ineffective", "pending"]
    matrix: Dict[str, Dict[str, int]] = {}
    for t in tests:
        lib_id = t.get("control_library_id") or t.get("control_id")
        lib = library_by_id.get(str(lib_id or ""), {})
        proc = t.get("process") or lib.get("process") or "Unassigned"
        eff = effectiveness_from_test_row(t)
        if eff is None and (t.get("result") in (None, "pending", "not_tested")):
            eff = "pending"
        if eff not in cols:
            eff = "pending"
        matrix.setdefault(proc, {c: 0 for c in cols})
        matrix[proc][eff] = matrix[proc].get(eff, 0) + 1
    processes = sorted(matrix.keys())
    return {"processes": processes, "columns": cols, "matrix": matrix}
