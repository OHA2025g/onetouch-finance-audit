import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { fmtUSD } from "../lib/format";
import { useMastersFilters } from "../lib/MastersFilterContext";
import { buildDashboardFilterParams } from "../lib/mastersDashboardParams";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import InsightPanel from "../components/InsightPanel";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import clsx from "clsx";

function cellTone(r) {
  if (r.readiness >= 80) return "text-[hsl(var(--chart-4))]";
  if (r.readiness >= 60) return "text-[hsl(var(--chart-3))]";
  return "text-[hsl(var(--destructive))]";
}

export default function ProcessReadinessPage() {
  const [payload, setPayload] = useState(null);
  const nav = useNavigate();
  const [sp] = useSearchParams();
  const processLens = (sp.get("process") || "").trim();
  const { entityCode, periodYm, periodExplicit, departmentId, costCenterId, hrefWithMasterParams } = useMastersFilters();

  useEffect(() => {
    const params = buildDashboardFilterParams({
      entityCode,
      periodYm,
      periodExplicit,
      departmentId,
      costCenterId,
    });
    http
      .get("/readiness", { params })
      .then((r) => setPayload(r.data))
      .catch(() => toast.error("Failed to load readiness matrix"));
  }, [entityCode, periodYm, periodExplicit, departmentId, costCenterId]);

  const rows = payload?.rows ?? [];
  const applied = payload?.filters_applied ?? {};

  const displayRows = useMemo(() => {
    if (!processLens) return rows;
    return rows.filter((r) => r.process === processLens);
  }, [rows, processLens]);

  return (
    <PageShell maxWidth="max-w-[1700px]">
      <div data-testid="process-readiness-page">
        <PageHeader
          kicker="REPORTING"
          title="Process × entity readiness"
          subtitle="Weighted control, reconciliation, evidence, and issue signals — scoped by the global reporting context (Phase 12)."
          right={
            <Link
              to={hrefWithMasterParams("/app/risk-intelligence")}
              className="hidden items-center gap-2 rounded-sm border border-zinc-300 bg-white px-3 py-2 text-xs font-medium uppercase tracking-wider text-zinc-600 shadow-none transition-colors hover:bg-zinc-50 sm:inline-flex dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
              data-testid="readiness-risk-intelligence-header-link"
            >
              Risk intelligence
            </Link>
          }
        />

        <MastersFilterStrip className="mb-4" />

        {processLens ? (
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-sm border border-primary/30 bg-primary/5 px-3 py-2 text-xs">
            <span className="crt-num uppercase tracking-wider text-foreground">
              Phase 37–40 — Matrix filtered to process: <span className="font-medium">{processLens}</span>
            </span>
            <div className="flex flex-wrap items-center gap-3">
              <Link
                to={hrefWithMasterParams("/app/readiness")}
                className="crt-num uppercase tracking-wider text-primary hover:underline"
                data-testid="readiness-clear-process-lens"
              >
                Show all processes
              </Link>
              <Link
                to={(() => {
                  const b = hrefWithMasterParams("/app/risk-intelligence");
                  const sep = b.includes("?") ? "&" : "?";
                  return `${b}${sep}process=${encodeURIComponent(processLens)}`;
                })()}
                className="crt-num uppercase tracking-wider text-primary hover:underline"
                data-testid="readiness-to-risk-hub"
              >
                Risk hub (same lens) →
              </Link>
            </div>
          </div>
        ) : null}

        {Object.keys(applied).length > 0 ? (
          <p className="crt-num mb-4 text-[10px] uppercase tracking-wider text-muted-foreground">
            Filters applied:{" "}
            {Object.entries(applied)
              .map(([k, v]) => `${k}=${v}`)
              .join(" · ")}
          </p>
        ) : null}

        <InsightPanel section="cfo" title="Readiness context · AI Insights" />

        <SectionCard
          kicker="MATRIX"
          title="Readiness cells"
          right={
            <span className="crt-num text-xs text-muted-foreground">
              {displayRows.length} of {rows.length} combinations
            </span>
          }
          bodyClassName="p-0"
        >
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[72vh]" testId="readiness-matrix-table">
            <DataTableHead>
              <tr>
                <DataTableTh>Entity</DataTableTh>
                <DataTableTh>Process</DataTableTh>
                <DataTableTh align="right">Readiness %</DataTableTh>
                <DataTableTh align="right">Open crit/high</DataTableTh>
                <DataTableTh align="right">Exposure</DataTableTh>
                <DataTableTh className="w-36">Drill</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {displayRows.length === 0 ? (
                <tr>
                  <td colSpan={6} className="crt-num px-4 py-10 text-center text-xs text-muted-foreground">
                    {processLens && rows.length
                      ? `No rows for process “${processLens}” in this reporting context.`
                      : "No readiness rows match the current context."}
                  </td>
                </tr>
              ) : (
                displayRows.map((r, i) => (
                  <DataTableRow key={`${r.entity}-${r.process}-${i}`} testId={`readiness-row-${r.entity}-${i}`}>
                    <DataTableTd className="crt-num text-xs">{r.entity}</DataTableTd>
                    <DataTableTd className="text-sm text-foreground">{r.process}</DataTableTd>
                    <DataTableTd align="right" className={clsx("crt-num text-sm font-medium tabular-nums", cellTone(r))}>
                      {r.readiness?.toFixed?.(1) ?? r.readiness}
                    </DataTableTd>
                    <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                      {r.open_high ?? "—"}
                    </DataTableTd>
                    <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                      {r.exposure != null ? fmtUSD(r.exposure) : "—"}
                    </DataTableTd>
                    <DataTableTd>
                      <button
                        type="button"
                        className="crt-num text-[10px] uppercase tracking-wider text-primary hover:underline"
                        onClick={() =>
                          nav(
                            hrefWithMasterParams(
                              `/app/cases?entity=${encodeURIComponent(r.entity)}&process=${encodeURIComponent(r.process)}`,
                            ),
                          )
                        }
                      >
                        Cases →
                      </button>
                    </DataTableTd>
                  </DataTableRow>
                ))
              )}
            </DataTableBody>
          </DataTable>
        </SectionCard>
      </div>
    </PageShell>
  );
}
