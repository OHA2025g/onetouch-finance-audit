import React, { useMemo } from "react";
import { toast } from "sonner";
import { SectionCard } from "../PageShell";
import EntityFilter from "./EntityFilter";
import PeriodFilter from "./PeriodFilter";
import DepartmentFilter from "./DepartmentFilter";
import CostCenterFilter from "./CostCenterFilter";
import { useMastersFilters } from "../../lib/MastersFilterContext";

/**
 * Hub card — master filters synced to URL query (`m_*`) for shareable deep links (Phase 3).
 */
export default function MastersFilterBar() {
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
    <SectionCard
      kicker="MASTER DATA"
      title="Finance context (Phase 3)"
      right={
        <button
          type="button"
          className="crt-num rounded-sm border border-zinc-300 bg-white px-3 py-1.5 text-[10px] uppercase tracking-wider text-muted-foreground hover:text-foreground dark:border-zinc-600 dark:bg-zinc-900"
          onClick={() => {
            clearAll();
            toast.message("Filters cleared");
          }}
        >
          Clear
        </button>
      }
    >
      <p className="mb-4 text-xs text-muted-foreground">
        Selections update the URL (<span className="font-mono text-foreground">m_entity</span>,{" "}
        <span className="font-mono text-foreground">m_period</span>, …) so you can bookmark or paste links. Data loads
        from <span className="font-mono text-foreground">/api/masters/*</span>.
      </p>
      <div className="flex flex-wrap items-end gap-4">
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
    </SectionCard>
  );
}
