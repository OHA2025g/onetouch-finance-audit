"""Unit tests for FS validation helpers (no DB)."""
from __future__ import annotations

from app.services.ca_fs_validation import (
    build_fs_validation_summary,
    prior_period_movement_issues,
    validate_trial_balance_upload,
)


def test_validate_trial_balance_upload_empty() -> None:
    err, warn = validate_trial_balance_upload([])
    assert err
    assert "No rows" in err[0]


def test_validate_trial_balance_upload_warns_duplicate_codes() -> None:
    lines = [
        {"account_code": "1000", "account_name": "Cash", "debit": 50, "credit": 0},
        {"account_code": "1000", "account_name": "Cash dup", "debit": 0, "credit": 50},
    ]
    err, warn = validate_trial_balance_upload(lines)
    assert not err
    assert any("Duplicate account_code" in w for w in warn)


def test_validate_trial_balance_upload_errors_on_imbalance() -> None:
    lines = [
        {"account_code": "1000", "account_name": "Cash", "debit": 100, "credit": 0},
        {"account_code": "2000", "account_name": "AP", "debit": 0, "credit": 50},
    ]
    err, _warn = validate_trial_balance_upload(lines)
    assert err
    assert any("imbalance" in e.lower() or "debit" in e.lower() for e in err)


def test_prior_period_movement_issues() -> None:
    ln = {"account_code": "4000", "account_name": "Revenue", "debit": 0, "credit": 500_000}
    prev = {"4000": 100_000.0}
    issues = prior_period_movement_issues(ln, prev, final_materiality=50_000.0)
    assert issues
    assert issues[0]["type"] == "large_movement_vs_prior_period"


def test_build_fs_validation_summary_equation() -> None:
    buckets_bs = {"assets": 1000.0, "liabilities": 400.0, "equity": 600.0}
    buckets_pl = {"revenue": 200.0, "expenses": 150.0}
    issues = [{"type": "suspense", "message": "x"}]
    s = build_fs_validation_summary(buckets_bs, buckets_pl, 1000.0, 1000.0, issues)
    assert s["trial_balance_balanced"] is True
    assert s["accounting_equation_delta"] == 0.0
    assert s["accounting_equation_ok"] is True
    assert s["issue_total"] == 1
    assert s["issue_counts"].get("suspense") == 1
