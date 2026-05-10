import React, { useEffect, useState } from "react";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useWorkbenchRowDrill } from "../lib/workbenchDrillNav";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import { StatCard } from "../components/StatCard";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { fmtUSD } from "../lib/format";

export default function FixedAssetsCapexWorkbenchPage() {
  const { drillToTarget } = useWorkbenchRowDrill();
  const [d, setD] = useState(null);

  const params = useDashboardFilterParams();
  useEffect(() => {
    const listParams = { ...params, limit: 35, offset: 0 };
    Promise.all([http.get("/fixed-assets-audit/summary", { params }), http.get("/fixed-assets-audit/assets", { params: listParams })])
      .then(([s, a]) =>
        setD({
          summary: s.data || {},
          assets: a.data?.items || [],
        }),
      )
      .catch(() => toast.error("Failed to load fixed assets & CAPEX workbench"));
  }, [params]);

  if (!d) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="fa-capex-workbench-loading">
        Loading fixed assets & CAPEX workbench…
      </div>
    );
  }

  const k = d.summary?.kpis || {};

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="fa-capex-workbench-page" data-fa-capex-workbench-surface="true">
        <PageHeader
          kicker="FIXED ASSETS & CAPEX · PHASE 25"
          title="Register · depreciation · capex overrun"
          subtitle="Summary + asset register — APIs: /fixed-assets-audit/summary · assets · depreciation-exceptions · cwip-ageing · capex-overrun · disposals."
        />

        <MastersFilterStrip className="mb-6" />

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          <StatCard label="Assets" value={k.asset_count} testId="fa-kpi-asset-count" />
          <StatCard label="Disposed" value={k.disposed_assets} testId="fa-kpi-disposed" />
          <StatCard label="Capex projects" value={k.capex_projects} testId="fa-kpi-capex-projects" />
          <StatCard label="Over budget" value={k.capex_over_budget} testId="fa-kpi-capex-over-budget" />
        </div>

        <SectionCard kicker="REGISTER" title="Fixed assets (scoped)">
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[58vh]" testId="fa-assets-table">
            <DataTableHead>
              <tr>
                <DataTableTh>Code</DataTableTh>
                <DataTableTh>Name</DataTableTh>
                <DataTableTh>Category</DataTableTh>
                <DataTableTh align="right">Cost</DataTableTh>
                <DataTableTh>Status</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {d.assets.length === 0 ? (
                <tr>
                  <td colSpan={5} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                    No assets in scope.
                  </td>
                </tr>
              ) : null}
              {d.assets.map((row) => (
                <DataTableRow key={row.id} testId={`fa-asset-${row.id}`} onClick={() => drillToTarget(row.id ? { type: "fixed_asset", id: String(row.id) } : null)}>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{row.asset_code || row.id}</DataTableTd>
                  <DataTableTd className="text-sm text-foreground">{row.asset_name || "—"}</DataTableTd>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{row.category || "—"}</DataTableTd>
                  <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                    {fmtUSD(row.cost)}
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
