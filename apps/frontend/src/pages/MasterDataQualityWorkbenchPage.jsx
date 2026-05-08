import React, { useEffect, useMemo, useState } from "react";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useMastersFilters } from "../lib/MastersFilterContext";
import { drillTargetMdqFinding, useWorkbenchRowDrill } from "../lib/workbenchDrillNav";
import { buildDashboardFilterParams } from "../lib/mastersDashboardParams";
import { StatCard } from "../components/StatCard";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";

export default function MasterDataQualityWorkbenchPage() {
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

  const countParams = useMemo(() => ({ ...params, limit: 1, offset: 0 }), [params]);

  useEffect(() => {
    Promise.all([
      http.get("/master-data-quality/summary"),
      http.get("/master-data-quality/vendors", { params: countParams }),
      http.get("/master-data-quality/customers", { params: countParams }),
      http.get("/master-data-quality/employees", { params: countParams }),
      http.get("/master-data-quality/gl", { params: countParams }),
      http.get("/master-data-quality/duplicates", { params: { ...params, limit: 500 } }),
      http.get("/master-data-quality/change-audit", { params: { ...params, limit: 500 } }),
      http.get("/master-data-quality/vendors", { params: { ...params, limit: 35 } }),
    ])
      .then(([summary, vend, cust, emp, gl, dup, audit, vendRows]) => {
        const bySev = summary.data?.open_by_severity || {};
        const critical = bySev.critical ?? bySev.CRITICAL ?? 0;
        const openScope =
          (vend.data?.total ?? 0) +
          (cust.data?.total ?? 0) +
          (emp.data?.total ?? 0) +
          (gl.data?.total ?? 0);
        setD({
          criticalGlobal: critical,
          openScope,
          duplicatesCount: dup.data?.count ?? 0,
          changeAuditCount: audit.data?.count ?? 0,
          vendorTotals: vend.data?.total ?? 0,
          findings: vendRows.data?.items || [],
        });
      })
      .catch(() => toast.error("Failed to load master data quality workbench"));
  }, [params, countParams]);

  if (!d) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="master-dq-workbench-loading">
        Loading master data quality workbench…
      </div>
    );
  }

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="master-dq-workbench-page" data-mdq-phase33-surface="true">
        <PageHeader
          kicker="MASTER DATA QUALITY · PHASE 33"
          title="DQ summary · entity-scoped queues · duplicates · change audit"
          subtitle={`Findings rollup + severity mix (critical global: ${d.criticalGlobal}) — APIs: /master-data-quality/summary · /vendors · /duplicates · /change-audit.`}
        />

        <MastersFilterStrip className="mb-6" />

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          <StatCard label="Open findings (scope)" value={d.openScope} testId="mdq33-kpi-open-scope" />
          <StatCard label="Vendor DQ (scope)" value={d.vendorTotals} testId="mdq33-kpi-vendors" />
          <StatCard label="Duplicate signals" value={d.duplicatesCount} testId="mdq33-kpi-duplicates" />
          <StatCard label="Change audit rows" value={d.changeAuditCount} testId="mdq33-kpi-change-audit" />
        </div>

        <SectionCard kicker="VENDOR FINDINGS" title="Open vendor DQ (scoped, top 35)">
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[58vh]" testId="mdq-vendor-findings-table">
            <DataTableHead>
              <tr>
                <DataTableTh>Severity</DataTableTh>
                <DataTableTh>Rule</DataTableTh>
                <DataTableTh>Object</DataTableTh>
                <DataTableTh>Message</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {d.findings.length === 0 ? (
                <tr>
                  <td colSpan={4} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                    No vendor findings in scope.
                  </td>
                </tr>
              ) : null}
              {d.findings.map((row) => (
                <DataTableRow key={row.id} testId={`mdq33-vf-${row.id}`} onClick={() => drillToTarget(drillTargetMdqFinding(row))}>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{row.severity || "—"}</DataTableTd>
                  <DataTableTd className="text-xs text-foreground">{row.rule_id || "—"}</DataTableTd>
                  <DataTableTd className="text-xs text-muted-foreground">{row.object_id || "—"}</DataTableTd>
                  <DataTableTd className="text-xs text-muted-foreground max-w-[360px] truncate" title={row.message}>
                    {row.message || "—"}
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
