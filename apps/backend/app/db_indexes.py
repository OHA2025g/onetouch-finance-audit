"""Idempotent MongoDB indexes for workflow-heavy collections (integrations, close, recon, copilot)."""


async def ensure_workflow_indexes(db) -> None:
    """Create indexes if missing; safe to call on every startup."""
    await db.close_tasks.create_index([("cycle_id", 1), ("status", 1)])
    await db.close_cycles.create_index([("period_ym", -1)])
    await db.close_cycles.create_index([("entity_code", 1), ("period_ym", -1)])
    await db.reconciliations.create_index([("entity", 1), ("period", 1), ("status", 1)])
    await db.budget_variances.create_index([("entity", 1), ("abs_variance", -1)])
    await db.connector_runs.create_index([("connector_id", 1), ("run_start", -1)])
    await db.connector_errors.create_index([("connector_id", 1), ("created_at", -1)])
    await db.connector_quarantine.create_index([("connector_id", 1), ("created_at", -1)])
    await db.continuous_audit_rule_runs.create_index([("rule_id", 1), ("started_at", -1)])
    await db.bank_recon_statements.create_index([("entity", 1), ("created_at", -1)])
    await db.master_data_quality_findings.create_index([("entity", 1), ("severity", 1)])
    await db.copilot_usage_buckets.create_index([("id", 1)], unique=True)
    await db.kpi_snapshots.create_index([("scope_key", 1), ("recorded_at", -1)])
    await db.kpi_snapshots.create_index([("scope_key", 1), ("week_key", 1)])
    await db.cfo_cockpit_visits.create_index([("user_email", 1), ("scope_key", 1)], unique=True)
    await db.cfo_action_queue.create_index([("status", 1), ("entity", 1), ("score", 1)])
    await db.cfo_action_queue.create_index([("status", 1), ("priority", 1), ("updated_at", -1)])
    await db.cfo_action_queue.create_index([("type", 1), ("status", 1)])
    await db.cfo_action_queue.create_index([("id", 1)], unique=True)
    await db.cfo_action_queue_snapshots.create_index([("scope_key", 1), ("recorded_at", -1)])
    await db.cfo_action_queue_usage.create_index([("id", 1)], unique=True)
    await db.rollup_snapshots.create_index([("node_id", 1)])
    await db.rollup_snapshot_history.create_index([("node_id", 1), ("as_of", -1)])
    await db.ca_assurance_snapshots.create_index([("engagement_id", 1), ("captured_at", -1)])
