import React, { useMemo } from "react";
import { toast } from "sonner";
import EntityFilter from "./EntityFilter";
import PeriodFilter from "./PeriodFilter";
import DepartmentFilter from "./DepartmentFilter";
import CostCenterFilter from "./CostCenterFilter";
import { useMastersFilters } from "../../lib/MastersFilterContext";

/**
 * Compact inline strip — same URL-synced state as {@link MastersFilterBar}.
 */
export default function MastersFilterStrip({ className = "" }) {
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
        <div className="crt-overline text-muted-foreground">Reporting context · URL-synced</div>
        <button
          type="button"
          className="crt-num rounded-sm border border-zinc-300 bg-white px-2 py-1 text-[9px] uppercase tracking-wider text-muted-foreground hover:text-foreground dark:border-zinc-600 dark:bg-zinc-900"
          onClick={() => {
            clearAll();
            toast.message("Context cleared");
          }}
        >
          Clear
        </button>
      </div>
      <div className="flex flex-wrap items-end gap-3 md:gap-4">
        <EntityFilter value={entityCode} onChange={setEntityCode} />
        <PeriodFilter value={periodYm} onChange={setPeriodYm} />
        <DepartmentFilter
          entityCode={entityForChildren}
          value={departmentId}
          onChange={setDepartmentId}
        />
        <CostCenterFilter
          entityCode={entityForChildren}
          value={costCenterId}
          onChange={setCostCenterId}
        />
      </div>
    </div>
  );
}
