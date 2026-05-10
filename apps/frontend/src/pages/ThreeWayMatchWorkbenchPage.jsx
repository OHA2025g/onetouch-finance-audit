import React, { useEffect, useState } from "react";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { drillTargetThreeWayMatchRow, useWorkbenchRowDrill } from "../lib/workbenchDrillNav";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import { StatCard } from "../components/StatCard";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { fmtUSD } from "../lib/format";

export default function ThreeWayMatchWorkbenchPage() {
  const { drillToTarget } = useWorkbenchRowDrill();
  const [d, setD] = useState(null);

  const params = useDashboardFilterParams();
  useEffect(() => {
    const exParams = { ...params, limit: 40 };
    Promise.all([
      http.get("/three-way-match/tolerances"),
      http.get("/three-way-match/summary", { params }),
      http.get("/three-way-match/exceptions", { params: exParams }),
    ])
      .then(([t, s, e]) =>
        setD({
          tolerances: t.data?.tolerances || {},
          summary: s.data || {},
          exceptions: e.data?.items || [],
        }),
      )
      .catch(() => toast.error("Failed to load three-way match workbench"));
  }, [params]);

  if (!d) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="twm-workbench-loading">
        Loading three-way match workbench…
      </div>
    );
  }

  const tol = d.tolerances;
  const openEx = d.summary?.open_exceptions ?? 0;

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="twm-workbench-page" data-three-way-match-surface="true">
        <PageHeader
          kicker="THREE-WAY MATCH · PHASE 20"
          title="PO · GRN · Invoice matching"
          subtitle="Tolerances, summary, exceptions — APIs: /three-way-match/tolerances · /run · /summary · /exceptions."
        />

        <MastersFilterStrip className="mb-6" />

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
          <StatCard label="Open exceptions" value={openEx} severity={openEx > 0 ? "warning" : undefined} testId="twm-kpi-open-exceptions" />
          <StatCard label="Tol. %" value={tol.amount_tolerance_pct ?? "—"} testId="twm-kpi-tol-pct" />
          <StatCard label="Tol. abs" value={fmtUSD(tol.amount_tolerance_abs)} testId="twm-kpi-tol-abs" />
        </div>

        <SectionCard kicker="EXCEPTIONS" title="Three-way match variances">
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[58vh]" testId="twm-exceptions-table">
            <DataTableHead>
              <tr>
                <DataTableTh>Exception</DataTableTh>
                <DataTableTh>Entity</DataTableTh>
                <DataTableTh>Invoice</DataTableTh>
                <DataTableTh>Severity</DataTableTh>
                <DataTableTh align="right">Inv−PO</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {d.exceptions.length === 0 ? (
                <tr>
                  <td colSpan={5} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                    No three-way match exceptions in scope (run the engine from the API or seed data).
                  </td>
                </tr>
              ) : null}
              {d.exceptions.map((x) => (
                <DataTableRow key={x.id} testId={`twm-ex-${x.id}`} onClick={() => drillToTarget(drillTargetThreeWayMatchRow(x))}>
                  <DataTableTd className="crt-num text-xs font-mono text-muted-foreground">{x.id}</DataTableTd>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{x.entity || "—"}</DataTableTd>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{x.invoice_id || "—"}</DataTableTd>
                  <DataTableTd className="crt-num text-xs uppercase text-muted-foreground">{x.severity || "—"}</DataTableTd>
                  <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                    {fmtUSD(x.variance_inv_po)}
                  </DataTableTd>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </SectionCard>
      </div>
    </PageShell>
  );
}
