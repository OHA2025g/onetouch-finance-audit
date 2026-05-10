import { useMemo } from "react";
import { useMastersFilters } from "./MastersFilterContext";
import { useAuth } from "./auth";
import { buildDashboardFilterParams } from "./mastersDashboardParams";

/**
 * URL-synced masters context plus logged-in ``user.entity`` as default ``entity_code`` for API calls.
 * Use everywhere you previously called {@link buildDashboardFilterParams} with strip fields only.
 */
export function useDashboardFilterParams() {
  const auth = useAuth();
  const user = auth?.user;
  const { entityCode, periodYm, periodExplicit, departmentId, costCenterId } = useMastersFilters();
  const defaultEntityCode =
    user?.role === "CFO" ? undefined : user?.entity;
  return useMemo(
    () =>
      buildDashboardFilterParams({
        entityCode,
        periodYm,
        periodExplicit,
        departmentId,
        costCenterId,
        defaultEntityCode,
      }),
    [entityCode, periodYm, periodExplicit, departmentId, costCenterId, defaultEntityCode],
  );
}
