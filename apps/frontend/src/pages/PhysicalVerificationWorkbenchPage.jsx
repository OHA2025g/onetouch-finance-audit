import React, { useEffect, useMemo, useState } from "react";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useMastersFilters } from "../lib/MastersFilterContext";
import { buildDashboardFilterParams } from "../lib/mastersDashboardParams";
import { StatCard } from "../components/StatCard";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { fmtUSD } from "../lib/format";

export default function PhysicalVerificationWorkbenchPage() {
  const { entityCode, periodYm, periodExplicit, departmentId, costCenterId } = useMastersFilters();
  const [d, setD] = useState(null);

  const params = useMemo(
    () =>
      buildDashboardFilterParams({
        entityCode,
        periodYm,
        periodExplicit,
        departmentId,
        costCenterId,
      }),
    [entityCode, periodYm, periodExplicit, departmentId, costCenterId],
  );

  useEffect(() => {
    const listParams = { ...params, limit: 50 };
    http
      .get("/physical-verification/cycles", { params: listParams })
      .then((res) => {
        const cycles = res.data?.items || [];
        const latestId = cycles[0]?.id;
        if (!latestId) {
          setD({ cycles, varianceItems: [], latestCycleId: null });
          return;
        }
        return http.get(`/physical-verification/${encodeURIComponent(latestId)}/variance`).then((v) =>
          setD({
            cycles,
            varianceItems: v.data?.items || [],
            latestCycleId: latestId,
          }),
        );
      })
      .catch(() => toast.error("Failed to load physical verification workbench"));
  }, [params]);

  if (!d) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="pv-workbench-loading">
        Loading physical verification workbench…
      </div>
    );
  }

  const total = d.cycles.length;
  const open = d.cycles.filter((c) => (c.status || "open").toLowerCase() === "open").length;
  const closed = d.cycles.filter((c) => (c.status || "").toLowerCase() === "closed").length;

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="pv-workbench-page" data-pv-workbench-surface="true">
        <PageHeader
          kicker="PHYSICAL VERIFICATION · PHASE 24"
          title="Count cycles · variance · approvals"
          subtitle="Cycles register + variance on latest cycle — APIs: /physical-verification/cycles · upload-count · variance · reason · approve."
        />

        <MastersFilterStrip className="mb-6" />

        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-8">
          <StatCard label="Cycles" value={total} testId="pv-kpi-cycle-count" />
          <StatCard label="Open" value={open} testId="pv-kpi-open-cycles" />
          <StatCard label="Closed" value={closed} testId="pv-kpi-closed-cycles" />
        </div>

        <SectionCard kicker="CYCLES" title="Physical verification cycles (scoped)">
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[36vh]" testId="pv-cycles-table">
            <DataTableHead>
              <tr>
                <DataTableTh>Cycle</DataTableTh>
                <DataTableTh>Name</DataTableTh>
                <DataTableTh>Entity</DataTableTh>
                <DataTableTh>Status</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {d.cycles.length === 0 ? (
                <tr>
                  <td colSpan={4} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                    No cycles yet — create via API or playbook.
                  </td>
                </tr>
              ) : null}
              {d.cycles.map((c) => (
                <DataTableRow key={c.id} testId={`pv-cycle-${c.id}`}>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{c.id}</DataTableTd>
                  <DataTableTd className="text-sm text-foreground">{c.name || "—"}</DataTableTd>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{c.entity || "—"}</DataTableTd>
                  <DataTableTd className="text-xs text-foreground">{c.status || "—"}</DataTableTd>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </SectionCard>

        <SectionCard
          kicker="VARIANCE"
          title={d.latestCycleId ? `Variance lines (latest: ${d.latestCycleId})` : "Variance lines"}
          className="mt-8"
        >
          {!d.latestCycleId ? (
            <p className="crt-num px-1 py-6 text-center text-xs text-muted-foreground">No cycle to analyze yet.</p>
          ) : (
            <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[36vh]" testId="pv-variance-table">
              <DataTableHead>
                <tr>
                  <DataTableTh>SKU</DataTableTh>
                  <DataTableTh align="right">Book</DataTableTh>
                  <DataTableTh align="right">Physical</DataTableTh>
                  <DataTableTh align="right">Δ qty</DataTableTh>
                  <DataTableTh align="right">Δ value</DataTableTh>
                  <DataTableTh>Workflow</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {d.varianceItems.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                      No variance for this cycle (upload counts to compare).
                    </td>
                  </tr>
                ) : null}
                {d.varianceItems.map((row) => (
                  <DataTableRow key={row.id} testId={`pv-var-${row.id}`}>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">{row.sku}</DataTableTd>
                    <DataTableTd align="right" className="crt-num tabular-nums">
                      {row.book_qty}
                    </DataTableTd>
                    <DataTableTd align="right" className="crt-num tabular-nums">
                      {row.physical_qty}
                    </DataTableTd>
                    <DataTableTd align="right" className="crt-num tabular-nums">
                      {row.variance_qty}
                    </DataTableTd>
                    <DataTableTd align="right" className="crt-num tabular-nums">
                      {fmtUSD(row.variance_value)}
                    </DataTableTd>
                    <DataTableTd className="text-xs text-foreground">
                      {row.approved ? "approved" : row.status || "open"}
                    </DataTableTd>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </DataTable>
          )}
        </SectionCard>
      </div>
    </PageShell>
  );
}
