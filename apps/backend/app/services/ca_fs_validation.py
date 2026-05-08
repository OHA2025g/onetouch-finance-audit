"""Trial balance and FS generation validation helpers (CA statutory workflow)."""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional, Tuple


def _net_movement(ln: Dict[str, Any]) -> float:
    return float(ln.get("debit") or 0) - float(ln.get("credit") or 0)


def validate_trial_balance_upload(lines: List[Dict[str, Any]]) -> Tuple[List[str], List[str]]:
    """Return (errors, warnings). Errors block insert; warnings are advisory."""
    errors: List[str] = []
    warnings: List[str] = []
    if not lines:
        errors.append("No rows parsed from file")
        return errors, warnings
    total_dr = sum(float(ln.get("debit") or 0) for ln in lines)
    total_cr = sum(float(ln.get("credit") or 0) for ln in lines)
    if abs(total_dr - total_cr) > 0.01:
        errors.append(
            f"Debit/credit imbalance: total debit {round(total_dr, 2)} vs total credit {round(total_cr, 2)} "
            f"(delta {round(total_dr - total_cr, 2)})"
        )
    codes = [str(ln.get("account_code") or "").strip() for ln in lines]
    if len(codes) != len(set(codes)):
        dupes = [c for c in set(codes) if c and codes.count(c) > 1]
        warnings.append(f"Duplicate account_code entries: {dupes[:8]}{'…' if len(dupes) > 8 else ''}")
    for ln in lines:
        dr = float(ln.get("debit") or 0)
        cr = float(ln.get("credit") or 0)
        code = str(ln.get("account_code") or "").strip()
        if not code:
            warnings.append("Row skipped: missing account_code")
            continue
        if dr > 0 and cr > 0:
            warnings.append(f"Both debit and credit on {code} — review classification")
        if dr == 0 and cr == 0:
            warnings.append(f"Zero debit and credit on {code}")
        oc_issues = opening_closing_issues(ln)
        for msg in oc_issues:
            warnings.append(f"{code}: {msg}")
    return errors, warnings


def opening_closing_issues(ln: Dict[str, Any]) -> List[str]:
    """If opening/closing columns exist, validate closing ≈ opening + period movement."""
    msgs: List[str] = []
    keys = ("opening_debit", "opening_credit", "closing_debit", "closing_credit")
    if not any(ln.get(k) is not None for k in keys):
        return msgs
    try:
        od = float(ln.get("opening_debit") or 0)
        ocr = float(ln.get("opening_credit") or 0)
        cd = float(ln.get("closing_debit") or 0)
        ccr = float(ln.get("closing_credit") or 0)
    except (TypeError, ValueError):
        return ["opening/closing columns could not be parsed as numbers"]
    if od == 0 and ocr == 0 and cd == 0 and ccr == 0:
        return msgs
    open_net = od - ocr
    close_net = cd - ccr
    movement = _net_movement(ln)
    expected_close = open_net + movement
    if abs(expected_close - close_net) > max(0.01, 0.0001 * max(abs(close_net), abs(expected_close), 1.0)):
        msgs.append(
            f"Opening/closing mismatch: expected closing net {round(expected_close, 2)} vs reported {round(close_net, 2)}"
        )
    return msgs


def analyze_trial_balance_line(
    ln: Dict[str, Any],
    *,
    final_materiality: float,
) -> List[Dict[str, Any]]:
    """Return zero or more issue dicts for a single TB line."""
    issues: List[Dict[str, Any]] = []
    dr = float(ln.get("debit") or 0)
    cr = float(ln.get("credit") or 0)
    net = dr - cr
    code = (ln.get("account_code") or "").upper()
    name = (ln.get("account_name") or "").lower()

    if dr > 0 and cr > 0:
        issues.append({"type": "both_debit_and_credit", "line": ln, "severity": "medium", "message": "Line has both debit and credit"})

    if "suspense" in name or "suspense" in code.lower() or "misc" in name:
        issues.append({"type": "suspense_or_misc", "line": ln, "severity": "medium", "message": "Suspense / miscellaneous account — reclassify before sign-off"})

    if net < 0 and ("asset" in name or code.startswith("1")):
        issues.append({"type": "negative_asset", "line": ln, "severity": "high", "message": "Negative balance in asset-type account"})

    if net > 0 and ("liab" in name or "payable" in name or code.startswith("2")):
        issues.append({"type": "positive_liability_unusual", "line": ln, "severity": "medium", "message": "Unusual debit balance in liability-type account"})

    if final_materiality and abs(net) >= final_materiality:
        issues.append({"type": "material_balance", "line": ln, "severity": "medium", "message": "Balance exceeds overall materiality"})

    if final_materiality and abs(net) >= 3 * final_materiality:
        issues.append({"type": "large_balance", "line": ln, "severity": "high", "message": "Balance exceeds 3× materiality — review FS line mapping"})

    # Classification hint: code prefix vs name keywords
    if code.startswith("4") and "expense" not in name and "cost" not in name and "revenue" not in name and "income" not in name:
        issues.append({"type": "classification_mismatch", "line": ln, "severity": "low", "message": "Series-4 account without typical P&L keywords in name"})

    if code.startswith("2") and ("asset" in name or "receivable" in name):
        issues.append({"type": "classification_mismatch", "line": ln, "severity": "medium", "message": "Liability-series code with asset keywords — reclassify"})

    if code.startswith("1") and ("payable" in name or "liab" in name):
        issues.append({"type": "classification_mismatch", "line": ln, "severity": "medium", "message": "Asset-series code with liability keywords — reclassify"})

    return issues


def prior_period_movement_issues(
    ln: Dict[str, Any],
    prev_net_by_code: Dict[str, float],
    *,
    final_materiality: float,
) -> List[Dict[str, Any]]:
    """Flag large movement vs prior trial balance / snapshot balances."""
    issues: List[Dict[str, Any]] = []
    code = str(ln.get("account_code") or "").strip()
    if not code or not prev_net_by_code or code not in prev_net_by_code:
        return issues
    cur = _net_movement(ln)
    prev = float(prev_net_by_code.get(code) or 0)
    delta = cur - prev
    if final_materiality and abs(delta) >= final_materiality:
        issues.append(
            {
                "type": "large_movement_vs_prior_period",
                "line": ln,
                "severity": "medium",
                "message": f"Net change {round(delta, 2)} vs prior period exceeds overall materiality",
            }
        )
    if final_materiality and abs(delta) >= 3 * final_materiality:
        issues.append(
            {
                "type": "large_movement_vs_prior_period",
                "line": ln,
                "severity": "high",
                "message": f"Net change {round(delta, 2)} exceeds 3× materiality — extended substantive work",
            }
        )
    return issues


def opening_closing_snapshot_issues(ln: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Structured issues for FS snapshot from opening/closing validation."""
    out: List[Dict[str, Any]] = []
    for msg in opening_closing_issues(ln):
        out.append({"type": "opening_closing_mismatch", "line": ln, "severity": "high", "message": msg})
    return out


def build_fs_validation_summary(
    buckets_bs: Dict[str, float],
    buckets_pl: Dict[str, float],
    total_debit: float,
    total_credit: float,
    issues: List[Dict[str, Any]],
) -> Dict[str, Any]:
    assets = buckets_bs.get("assets") or 0.0
    liab = buckets_bs.get("liabilities") or 0.0
    eq = buckets_bs.get("equity") or 0.0
    equation_delta = round(assets - liab - eq, 2)
    counts = Counter(i.get("type") or "unknown" for i in issues)
    return {
        "trial_balance_balanced": abs(total_debit - total_credit) < 0.01,
        "total_debit": round(total_debit, 2),
        "total_credit": round(total_credit, 2),
        "accounting_equation_delta": equation_delta,
        "accounting_equation_ok": abs(equation_delta) < max(1.0, 0.001 * max(abs(assets), 1.0)),
        "revenue": round(buckets_pl.get("revenue") or 0.0, 2),
        "expenses": round(buckets_pl.get("expenses") or 0.0, 2),
        "pl_reasonableness": (buckets_pl.get("revenue") or 0) > 0 or (buckets_pl.get("expenses") or 0) == 0,
        "issue_counts": dict(counts),
        "issue_total": len(issues),
    }
