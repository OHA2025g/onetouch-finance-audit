from app.services.case_service import case_from_exception, merge_cases_master_filters


def test_case_from_exception_shape() -> None:
    ex = {
        "id": "ex-1",
        "control_code": "C-1",
        "control_name": "Test",
        "title": "T",
        "summary": "S",
        "severity": "critical",
        "financial_exposure": 1.0,
        "entity": "E1",
        "process": "P2P",
        "detected_at": "2020-01-01T00:00:00+00:00",
    }
    c = case_from_exception(ex, "a@b.com", "A B")
    assert c["status"] == "open"
    assert c["owner_email"] == "a@b.com"
    assert c["exception_id"] == "ex-1"
    assert c["priority"] == "P1"


def test_case_from_exception_copies_org_slice_from_exception() -> None:
    ex = {
        "id": "ex-2",
        "control_code": "C-1",
        "control_name": "Test",
        "title": "T",
        "summary": "S",
        "severity": "high",
        "financial_exposure": 2.0,
        "entity": "E1",
        "process": "P2P",
        "detected_at": "2020-01-01T00:00:00+00:00",
        "dept_id": "D-42",
        "cc_id": "CC-9",
    }
    c = case_from_exception(ex, "a@b.com", "A B")
    assert c["department_id"] == "D-42"
    assert c["cost_center_id"] == "CC-9"


def test_merge_cases_master_filters_department_and_entity() -> None:
    q = merge_cases_master_filters(
        {"status": "open"},
        entity_code="US-HQ",
        department_id="D1",
        cost_center_id=None,
    )
    assert "$and" in q
    inner = q["$and"][0]
    assert inner["status"] == "open"
    assert inner["entity"] == "US-HQ"
