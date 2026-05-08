"""Cross-module linkage view for an audit engagement (parent graph)."""
from __future__ import annotations

from typing import Any, Dict, List


async def build_integration_map(db, engagement_id: str) -> Dict[str, Any]:
    """Summarize how risks, controls, tests, WPs, exceptions, cases, observations, and reporting connect."""
    risks = [r async for r in db.ca_risks.find({"engagement_id": engagement_id}, {"_id": 0}).limit(100)]
    risk_ids = [r.get("id") for r in risks if r.get("id")]
    rcm = (
        [m async for m in db.ca_risk_control_map.find({"risk_id": {"$in": risk_ids}}, {"_id": 0}).limit(500)]
        if risk_ids
        else []
    )
    rcm_by_risk: Dict[str, List[str]] = {}
    for m in rcm:
        if m.get("risk_id") and m.get("control_id"):
            rcm_by_risk.setdefault(m["risk_id"], []).append(m.get("control_id"))

    tests = [t async for t in db.ca_control_tests.find({"engagement_id": engagement_id}, {"_id": 0}).limit(200)]
    tests_by_control: Dict[str, List[str]] = {}
    for t in tests:
        cid = t.get("control_id")
        if cid:
            tests_by_control.setdefault(cid, []).append(t.get("id"))

    wps = [p async for p in db.ca_working_papers.find({"engagement_id": engagement_id}, {"_id": 0}).limit(200)]
    exs = [e async for e in db.exceptions.find({"engagement_id": engagement_id}, {"_id": 0}).limit(200)]
    cases = [c async for c in db.cases.find({"engagement_id": engagement_id}, {"_id": 0}).limit(200)]
    obs = [o async for o in db.ca_audit_observations.find({"engagement_id": engagement_id}, {"_id": 0}).limit(200)]
    reports = await db.ca_final_reports.count_documents({"engagement_id": engagement_id})

    case_by_id = {c.get("id"): c for c in cases}
    obs_for_case = []
    for o in obs:
        sid = o.get("source_id")
        if sid and sid in case_by_id:
            obs_for_case.append({"observation_id": o.get("id"), "case_id": sid, "title": o.get("title")})

    ex_to_case = []
    for e in exs:
        exid = e.get("id")
        for c in cases:
            if c.get("exception_id") == exid:
                ex_to_case.append({"exception_id": exid, "case_id": c.get("id")})
                break

    risk_chains: List[Dict[str, Any]] = []
    for r in risks[:15]:
        rid = r.get("id")
        cids = list({*(r.get("linked_controls") or []), *(rcm_by_risk.get(rid) or [])})
        test_ids: List[str] = []
        for cid in cids:
            test_ids.extend(tests_by_control.get(cid) or [])
        wp_ids = [p.get("id") for p in wps if rid in (p.get("linked_risk_ids") or []) or any(c in (p.get("linked_control_ids") or []) for c in cids)]
        risk_chains.append(
            {
                "risk_id": rid,
                "risk_title": r.get("risk_title") or r.get("title"),
                "control_ids": cids[:12],
                "control_test_ids": test_ids[:20],
                "working_paper_ids": [x for x in wp_ids if x][:12],
            }
        )

    return {
        "engagement_id": engagement_id,
        "narrative": (
            "Audit engagement is the parent object. Risks map to controls (RACM + control library). "
            "Control tests evidence working papers via linked risks/controls/cases. Exceptions raise cases; "
            "cases and other sources feed observations; observations roll into the final auditor's report."
        ),
        "counts": {
            "risks": len(risks),
            "risk_control_links": len(rcm),
            "control_tests": len(tests),
            "working_papers": len(wps),
            "exceptions": len(exs),
            "cases": len(cases),
            "observations": len(obs),
            "final_reports": reports,
        },
        "risk_control_test_wp_chains": risk_chains,
        "exceptions_to_cases": ex_to_case[:50],
        "cases_to_observations": obs_for_case[:50],
    }
