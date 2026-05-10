/**
 * Phase 4 — map URL-synced master filter context to ``/dashboard/*`` query params.
 * ``period_ym`` is sent only when the user pinned a non-default month in the URL (`m_period`).
 *
 * @param {string} [defaultEntityCode] Logged-in user's legal entity (`user.entity`) when the URL has no `m_entity`.
 *   CFO omits this so consolidated dashboards request all entities unless `m_entity` is set.
 *   Improves audit trails and client toasts; the API still enforces RBAC when entity scope is on.
 */
export function buildDashboardFilterParams({
  entityCode,
  periodYm,
  periodExplicit,
  departmentId,
  costCenterId,
  defaultEntityCode,
}) {
  const p = {};
  const ec = (entityCode && String(entityCode).trim()) || (defaultEntityCode && String(defaultEntityCode).trim()) || "";
  if (ec) p.entity_code = ec;
  if (periodExplicit && periodYm) p.period_ym = periodYm;
  if (departmentId) p.department_id = departmentId;
  if (costCenterId) p.cost_center_id = costCenterId;
  return p;
}
