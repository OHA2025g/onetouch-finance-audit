import { useMemo } from "react";
import {
  buildRunsSparklineByControl,
  deriveViewSummary,
  filterControls,
  firstControlIdByProcess,
  hasActiveListFilters,
  isCatalogAllGreen,
  sortControls,
} from "./auditWorkspaceSummary";

/**
 * Audit workspace list filters + derived KPI/chart summary for the current view.
 */
export function useAuditWorkspaceSummary(data, filter) {
  const allControls = data?.controls || [];

  const controls = useMemo(() => {
    const filtered = filterControls(allControls, filter);
    return sortControls(filtered, filter.sort);
  }, [allControls, filter]);

  const summary = useMemo(
    () => deriveViewSummary(data?.summary, controls, allControls, filter),
    [data?.summary, controls, allControls, filter]
  );

  const listFiltered = hasActiveListFilters(filter);
  const catalogEmpty = allControls.length === 0;
  const filterEmpty = !catalogEmpty && controls.length === 0;
  const allGreen = useMemo(
    () => isCatalogAllGreen(allControls, deriveViewSummary(data?.summary, allControls, allControls, {})),
    [data?.summary, allControls]
  );

  const sparklineByControl = useMemo(
    () => buildRunsSparklineByControl(data?.recent_runs || []),
    [data?.recent_runs]
  );

  const controlIdByProcess = useMemo(() => firstControlIdByProcess(controls), [controls]);

  return {
    controls,
    summary,
    listFiltered,
    catalogEmpty,
    filterEmpty,
    allGreen,
    sparklineByControl,
    controlIdByProcess,
  };
}
