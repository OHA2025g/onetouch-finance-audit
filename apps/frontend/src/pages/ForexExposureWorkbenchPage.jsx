import React, { useEffect, useState } from "react";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import { StatCard } from "../components/StatCard";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { fmtUSD } from "../lib/format";

export default function ForexExposureWorkbenchPage() {
  const [d, setD] = useState(null);

  const params = useDashboardFilterParams();
  useEffect(() => {
    const listParams = { ...params, limit: 35, offset: 0 };
    Promise.all([http.get("/forex/summary", { params }), http.get("/forex/exposures", { params: listParams })])
      .then(([s, ex]) =>
        setD({
          summary: s.data || {},
          exposures: ex.data?.items || [],
        }),
      )
      .catch(() => toast.error("Failed to load forex exposure workbench"));
  }, [params]);

  if (!d) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="forex-exposure-workbench-loading">
        Loading forex exposure workbench…
      </div>
    );
  }

  const pairsTracked = Array.isArray(d.summary.items) ? d.summary.items.length : 0;

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="forex-exposure-workbench-page" data-forex-phase27-surface="true">
        <PageHeader
          kicker="FOREX · PHASE 27"
          title="Exposure · hedges · unhedged risk"
          subtitle="Summary + exposure register — APIs: /forex/summary · exposures · hedges · unhedged-risk · gain-loss."
        />

        <MastersFilterStrip className="mb-6" />

        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-8">
          <StatCard label="Open exposures" value={d.summary.exposure_count} testId="fx27-kpi-exposure-count" />
          <StatCard label="Active hedges" value={d.summary.hedge_count} testId="fx27-kpi-hedge-count" />
          <StatCard label="Pairs (summary)" value={pairsTracked} testId="fx27-kpi-pairs" />
        </div>

        <SectionCard kicker="EXPOSURES" title="FX exposure lines (scoped)">
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[58vh]" testId="fx-exposure-table">
            <DataTableHead>
              <tr>
                <DataTableTh>Pair</DataTableTh>
                <DataTableTh>Entity</DataTableTh>
                <DataTableTh>Direction</DataTableTh>
                <DataTableTh align="right">Notional (base)</DataTableTh>
                <DataTableTh>Maturity</DataTableTh>
                <DataTableTh>Status</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {d.exposures.length === 0 ? (
                <tr>
                  <td colSpan={6} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                    No exposures in scope.
                  </td>
                </tr>
              ) : null}
              {d.exposures.map((row) => (
                <DataTableRow key={row.id} testId={`fx-exp-${row.id}`}>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{row.pair}</DataTableTd>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{row.entity || "—"}</DataTableTd>
                  <DataTableTd className="text-xs text-foreground">{row.direction || "—"}</DataTableTd>
                  <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                    {fmtUSD(row.notional_base)}
                  </DataTableTd>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">
                    {row.maturity_date ? String(row.maturity_date).slice(0, 10) : "—"}
                  </DataTableTd>
                  <DataTableTd className="text-xs text-foreground">{row.status || "—"}</DataTableTd>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </SectionCard>
      </div>
    </PageShell>
  );
}
