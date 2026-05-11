import React, { useMemo } from "react";
import { toast } from "sonner";
import EntityFilter from "./EntityFilter";
import PeriodFilter from "./PeriodFilter";
import DepartmentFilter from "./DepartmentFilter";
import CostCenterFilter from "./CostCenterFilter";
import { useMastersFilters } from "../../lib/MastersFilterContext";

/**
 * Compact inline strip — same URL-synced state as {@link MastersFilterBar}.
 *
 * @param {React.ReactNode} [extraFilters] — Optional trailing controls (e.g. process facet) kept on the same row.
 */
export default function MastersFilterStrip({ className = "", extraFilters = null }) {
  const {
    entityCode,
    periodYm,
    departmentId,
    costCenterId,
    setEntityCode,
    setPeriodYm,
    setDepartmentId,
    setCostCenterId,
    clearAll,
  } = useMastersFilters();

  const entityForChildren = useMemo(() => (entityCode || undefined), [entityCode]);

  return (
    <div
      className={`crt-card border border-zinc-200 bg-white/90 p-4 dark:border-zinc-800 dark:bg-zinc-950/50 ${className}`}
      data-testid="masters-filter-strip"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="crt-overline text-muted-foreground">Reporting Context · URL-Synced</div>
        <button
          type="button"
          className="crt-num shrink-0 rounded-none border border-zinc-300 bg-white px-2 py-1 text-[9px] tracking-wide text-muted-foreground hover:text-foreground dark:border-zinc-600 dark:bg-zinc-900"
          onClick={() => {
            clearAll();
            toast.message("Context cleared");
          }}
        >
          Clear
        </button>
      </div>
      <div
        className={`grid w-full min-w-0 grid-cols-2 items-end gap-2 pb-0.5 sm:grid-cols-3 md:gap-3 ${
          extraFilters ? "md:grid-cols-5" : "md:grid-cols-4"
        }`}
      >
        <div className="min-w-0">
          <EntityFilter variant="strip" value={entityCode} onChange={setEntityCode} />
        </div>
        <div className="min-w-0">
          <PeriodFilter variant="strip" value={periodYm} onChange={setPeriodYm} />
        </div>
        <div className="min-w-0">
          <DepartmentFilter
            variant="strip"
            entityCode={entityForChildren}
            value={departmentId}
            onChange={setDepartmentId}
          />
        </div>
        <div className="min-w-0">
          <CostCenterFilter
            variant="strip"
            entityCode={entityForChildren}
            value={costCenterId}
            onChange={setCostCenterId}
          />
        </div>
        {extraFilters ? (
          <div className="flex min-w-0 flex-wrap items-end gap-2">{extraFilters}</div>
        ) : null}
      </div>
    </div>
  );
}
