"""RACM: normalize risk documents, audit-plan preview, default procedures for high-risk areas."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from app.services.ca_audit_domain import risk_scores

_CATEGORY_PROCEDURE_TEMPLATES: Dict[str, List[Dict[str, str]]] = {
    "Financial Reporting Risk": [
        {"title": "Expanded analytical procedures", "description": "Trend, ratio, and reasonableness tests on FS captions in this area."},
        {"title": "Journal entry testing (scope-up)", "description": "Target unusual or manual entries tied to the risk process."},
    ],
    "Fraud Risk": [
        {"title": "Fraud brainstorming & unpredictability", "description": "Document incentives, pressures, opportunities; link to controls override testing."},
        {"title": "Management override / journal control walkthrough", "description": "Verify design and sample operating effectiveness for privileged users."},
    ],
    "Compliance Risk": [
        {"title": "Regulatory filing reconciliation", "description": "Trace obligations to filings and board minutes."},
    ],
    "Operational Risk": [
        {"title": "Process walkthrough & key reports", "description": "Validate KPIs and exception reports feeding the FS assertion."},
    ],
    "IT/ERP Risk": [
        {"title": "ITGC / change management sample", "description": "Access, change, and operations controls around ERP paths for this risk."},
    ],
    "Tax Risk": [
        {"title": "Tax provision tie-out", "description": "Reconcile provision to returns and supporting workpapers."},
    ],
}


def procedure_titles_for_index(r: Dict[str, Any]) -> str:
    rp = r.get("racm_procedures") or []
    if rp:
        return " | ".join((p.get("title") or "") for p in rp if isinstance(p, dict))
    return " | ".join(r.get("audit_procedures") or [])


def normalize_risk_racm(r: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure racm_procedures exists; attach risk_score summary for API consumers."""
    out = dict(r)
    rp = out.get("racm_procedures")
    if not rp and out.get("audit_procedures"):
        rp = [
            {"id": f"legacy-{i}", "title": t, "description": "", "source": "manual"}
            for i, t in enumerate(out["audit_procedures"])
            if isinstance(t, str)
        ]
    out["racm_procedures"] = list(rp or [])
    out["audit_procedures"] = [p.get("title", "") for p in out["racm_procedures"] if isinstance(p, dict) and p.get("title")]
    out["risk_score"] = {
        "likelihood_score": int(out.get("likelihood_score") or 0),
        "impact_score": int(out.get("impact_score") or 0),
        "inherent_risk_score": int(out.get("inherent_risk_score") or 0),
        "control_effectiveness_score": out.get("control_effectiveness_score"),
        "residual_risk_score": int(out.get("residual_risk_score") or 0),
        "risk_rating": out.get("risk_rating") or "low",
        "formulas": {
            "inherent": "likelihood × impact",
            "residual": "inherent adjusted by (control_effectiveness ÷ 5) when a control score is set; else equals inherent",
        },
    }
    return out


def build_audit_plan_preview(risks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """High / critical risks drive the automatic audit plan view (procedures to emphasise)."""
    items: List[Dict[str, Any]] = []
    for r in risks:
        if r.get("risk_rating") not in ("high", "critical"):
            continue
        nr = normalize_risk_racm(r)
        for p in nr.get("racm_procedures") or []:
            if not isinstance(p, dict):
                continue
            items.append(
                {
                    "risk_id": r.get("id"),
                    "risk_title": r.get("risk_title"),
                    "risk_rating": r.get("risk_rating"),
                    "process_area": r.get("process_area"),
                    "financial_statement_area": r.get("financial_statement_area"),
                    "procedure_id": p.get("id"),
                    "procedure_title": p.get("title"),
                    "procedure_description": p.get("description") or "",
                    "procedure_source": p.get("source") or "manual",
                }
            )
    return items


def default_procedures_for_category(category: str) -> List[Dict[str, Any]]:
    templates = _CATEGORY_PROCEDURE_TEMPLATES.get(category) or _CATEGORY_PROCEDURE_TEMPLATES.get("Financial Reporting Risk", [])
    out: List[Dict[str, Any]] = []
    for t in templates[:2]:
        out.append(
            {
                "id": str(uuid.uuid4()),
                "title": t["title"],
                "description": t.get("description", ""),
                "source": "high_risk_auto",
            }
        )
    return out


def merge_racm_procedures_from_create(body_dump: Dict[str, Any]) -> tuple[List[Dict[str, Any]], List[str]]:
    """From create payload: structured procedures list and/or legacy string list."""
    structured = body_dump.get("procedures") or []
    titles_legacy = body_dump.get("audit_procedures") or []
    racm: List[Dict[str, Any]] = []
    for p in structured:
        if isinstance(p, dict):
            t = (p.get("title") or "").strip()
            if not t:
                continue
            racm.append(
                {
                    "id": p.get("id") or str(uuid.uuid4()),
                    "title": t,
                    "description": (p.get("description") or "").strip(),
                    "source": p.get("source") or "manual",
                }
            )
        else:
            s = str(p).strip()
            if s:
                racm.append({"id": str(uuid.uuid4()), "title": s, "description": "", "source": "manual"})
    for t in titles_legacy:
        if isinstance(t, str) and t.strip():
            if any(x.get("title") == t for x in racm):
                continue
            racm.append({"id": str(uuid.uuid4()), "title": t.strip(), "description": "", "source": "manual"})
    titles = [x["title"] for x in racm if x.get("title")]
    return racm, titles


def recompute_scores_if_needed(merged: Dict[str, Any]) -> None:
    """Update inherent/residual/rating when likelihood, impact, or control score present."""
    merged.update(
        risk_scores(
            int(merged.get("likelihood_score") or 1),
            int(merged.get("impact_score") or 1),
            merged.get("control_effectiveness_score"),
        )
    )
