/**
 * Phase 4 — map URL-synced master filter context to ``/dashboard/*`` query params.
 * ``period_ym`` is sent only when the user pinned a non-default month in the URL (`m_period`).
 */
export function buildDashboardFilterParams({ entityCode, periodYm, periodExplicit, departmentId, costCenterId }) {
  const p = {};
  if (entityCode) p.entity_code = entityCode;
  if (periodExplicit && periodYm) p.period_ym = periodYm;
  if (departmentId) p.department_id = departmentId;
  if (costCenterId) p.cost_center_id = costCenterId;
  return p;
}
