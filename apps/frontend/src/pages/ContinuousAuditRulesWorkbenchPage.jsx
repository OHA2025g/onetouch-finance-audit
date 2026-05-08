import React, { useEffect, useMemo, useState } from "react";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useMastersFilters } from "../lib/MastersFilterContext";
import { drillTargetExceptionListRow, useWorkbenchRowDrill } from "../lib/workbenchDrillNav";
import { buildDashboardFilterParams } from "../lib/mastersDashboardParams";
import { StatCard } from "../components/StatCard";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { fmtUSD } from "../lib/format";

export default function ContinuousAuditRulesWorkbenchPage() {
  const { entityCode, periodYm, periodExplicit, departmentId, costCenterId } = useMastersFilters();
  const { drillToTarget } = useWorkbenchRowDrill();
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

  const countOne = useMemo(() => ({ ...params, limit: 1, offset: 0 }), [params]);

  useEffect(() => {
    Promise.all([
      http.get("/continuous-audit/rules", { params: { ...countOne, status: "active" } }),
      http.get("/continuous-audit/exceptions", { params: { ...params, limit: 35, offset: 0 } }),
      http.get("/continuous-audit/rule-performance", { params }),
    ])
      .then(([rules, caEx, perf]) => {
        const items = perf.data?.items || [];
        const totalRuns = items.reduce((acc, r) => acc + (r.run_count || 0), 0);
        const openAcrossRules = items.reduce((acc, r) => acc + (r.open_exceptions || 0), 0);
        setD({
          activeRules: rules.data?.total ?? 0,
          caExceptionTotal: caEx.data?.total ?? 0,
          totalRuleRuns: totalRuns,
          openExceptionsAcrossRules: openAcrossRules,
          exceptionRows: caEx.data?.items || [],
        });
      })
      .catch(() => toast.error("Failed to load continuous audit rules workbench"));
  }, [params, countOne]);

  if (!d) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="continuous-audit-rules-workbench-loading">
        Loading continuous audit rules workbench…
      </div>
    );
  }

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="continuous-audit-rules-workbench-page" data-ca-rules-phase35-surface="true">
        <PageHeader
          kicker="CONTINUOUS AUDIT · PHASE 35"
          title="Rules · runs · rule-scoped exceptions · performance"
          subtitle="CA exceptions use `control_code` CAR-* — /continuous-audit/rules · /run · /exceptions · /rule-performance."
        />

        <MastersFilterStrip className="mb-6" />

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          <StatCard label="Active rules" value={d.activeRules} testId="ca35-kpi-active-rules" />
          <StatCard label="Open CA exceptions" value={d.caExceptionTotal} testId="ca35-kpi-ca-exceptions" />
          <StatCard label="Rule runs (total)" value={d.totalRuleRuns} testId="ca35-kpi-rule-runs" />
          <StatCard label="Open (by rule)" value={d.openExceptionsAcrossRules} testId="ca35-kpi-open-by-rule" />
        </div>

        <SectionCard kicker="EXCEPTIONS" title="Continuous audit exceptions (CAR-*, recent)">
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[58vh]" testId="ca35-exceptions-table">
            <DataTableHead>
              <tr>
                <DataTableTh>Code</DataTableTh>
                <DataTableTh>Title</DataTableTh>
                <DataTableTh>Severity</DataTableTh>
                <DataTableTh align="right">Exposure</DataTableTh>
                <DataTableTh>Status</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {d.exceptionRows.length === 0 ? (
                <tr>
                  <td colSpan={5} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                    No CAR exceptions yet. Run POST /continuous-audit/rules/(rule_id)/run to generate seeded findings.
                  </td>
                </tr>
              ) : null}
              {d.exceptionRows.map((row) => (
                <DataTableRow key={row.id} testId={`ca35-ex-${row.id}`} onClick={() => drillToTarget(drillTargetExceptionListRow(row))}>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{row.control_code || "—"}</DataTableTd>
                  <DataTableTd className="text-xs text-foreground max-w-[280px] truncate" title={row.title}>
                    {row.title || "—"}
                  </DataTableTd>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{row.severity || "—"}</DataTableTd>
                  <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                    {fmtUSD(row.financial_exposure)}
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
