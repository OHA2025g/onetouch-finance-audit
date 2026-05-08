from app.services.ca_report_opinion_engine import recommend_opinion, build_report_sections


def test_recommend_unqualified_clean():
    r = recommend_opinion([], {"compliance_non_compliant": 0, "critical_high_deficiencies": 0, "open_cases": 0, "fs_issue_strings": [], "compliance_pending_evidence": 0})
    assert r["suggested_opinion"] == "unqualified"
    assert "unqualified" in r["opinion_display"].lower()


def test_recommend_qualified_from_virtual_compliance():
    obs = [{"title": "X", "material": True, "pervasive": False, "resolved": False, "severity": "high", "source": "manual"}]
    sig = {"compliance_non_compliant": 0, "critical_high_deficiencies": 0, "open_cases": 0, "fs_issue_strings": [], "compliance_pending_evidence": 0}
    r = recommend_opinion(obs, sig)
    assert r["suggested_opinion"] == "qualified"


def test_build_sections_keys():
    eng = {"entity_name": "Demo Co", "financial_year": "2025-26"}
    op = {"suggested_opinion": "unqualified", "opinion_display": "clean / unqualified"}
    sections = build_report_sections(eng, op, [], {"responses": [{"clause_id": "3(i)", "response": "ok"}]}, {"materiality": {"final_materiality": 1e7}})
    assert "opinion" in sections
    assert "basis_for_opinion" in sections
    assert sections.get("caro_annexure")
