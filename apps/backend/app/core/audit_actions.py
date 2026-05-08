"""Canonical ``action_type`` values stored on ``audit_logs.action_type`` (Wave 0 standard).

Existing code may still emit legacy string labels; callers should migrate toward these
values for new workflows. `AUDIT_ACTION_TYPES` is the union of standard verbs and
common domain-prefixed actions already present in routers.
"""

from __future__ import annotations

from typing import FrozenSet

# Standard workflow verbs (plan: approve, reject, escalate, signoff, case_create, config_change)
_AUDIT_STANDARD: FrozenSet[str] = frozenset(
    {
        "approve",
        "reject",
        "escalate",
        "signoff",
        "case_create",
        "config_change",
    }
)

# Legacy / domain actions still used across the codebase (non-exhaustive; extend as needed).
_AUDIT_DOMAIN_PREFIXES: tuple[str, ...] = (
    "run_control",
    "run_all_controls",
    "connector_",
    "cfo_action_",
    "close_",
    "security_config",
    "org_backfill",
    "copilot_",
)

AUDIT_ACTION_TYPES: FrozenSet[str] = frozenset(_AUDIT_STANDARD)


def is_standard_audit_action(action: str) -> bool:
    if action in _AUDIT_STANDARD:
        return True
    if any(action.startswith(p) for p in _AUDIT_DOMAIN_PREFIXES):
        return True
    return False


def assert_known_audit_action(action: str, *, strict: bool, log_warning) -> None:
    """If ``strict`` and action is unknown, log a warning (enforcement hook for CI/tests)."""
    if strict and not is_standard_audit_action(action):
        log_warning("non_standard_audit_action: %s", action)
