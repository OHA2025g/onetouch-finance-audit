from __future__ import annotations

from typing import Any, Dict, List, Tuple


def validate_required_fields(schema: Dict[str, Any], records: List[Dict[str, Any]]) -> Tuple[bool, Dict[str, Any]]:
    required = list(schema.get("required") or [])
    if not required:
        return True, {"required": [], "violations": 0}
    violations = 0
    missing_examples: List[Dict[str, Any]] = []
    for r in records[:500]:
        missing = [k for k in required if k not in r or r.get(k) in (None, "")]
        if missing:
            violations += 1
            if len(missing_examples) < 5:
                missing_examples.append({"id": r.get("id"), "missing": missing})
    ok = violations == 0
    return ok, {"required": required, "violations": violations, "missing_examples": missing_examples}

