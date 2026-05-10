import React, { useEffect, useState } from "react";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { drillTargetFromTxnId, useWorkbenchRowDrill } from "../lib/workbenchDrillNav";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import { StatCard } from "../components/StatCard";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { fmtUSD } from "../lib/format";

export default function DoaWorkbenchPage() {
  const { drillToTarget } = useWorkbenchRowDrill();
  const [d, setD] = useState(null);

  const params = useDashboardFilterParams();
  useEffect(() => {
    const breachParams = { ...params, limit: 35, offset: 0 };
    const openParams = { ...params, status: "open", limit: 1, offset: 0 };
    Promise.all([
      http.get("/doa/matrix", { params }),
      http.get("/doa/rules", { params }),
      http.get("/doa/breaches", { params: breachParams }),
      http.get("/doa/breaches", { params: openParams }),
    ])
      .then(([matrix, rules, breaches, openMeta]) =>
        setD({
          matrixCount: matrix.data?.count ?? 0,
          rulesCount: rules.data?.count ?? 0,
          breachTotal: breaches.data?.total ?? 0,
          openBreaches: openMeta.data?.total ?? 0,
          breachItems: breaches.data?.items || [],
        }),
      )
      .catch(() => toast.error("Failed to load DoA workbench"));
  }, [params]);

  if (!d) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="doa-workbench-loading">
        Loading delegation of authority workbench…
      </div>
    );
  }

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="doa-workbench-page" data-doa-phase30-surface="true">
        <PageHeader
          kicker="DELEGATION OF AUTHORITY · PHASE 30"
          title="Matrix · rules · breaches"
          subtitle="Exposure from limits engine — APIs: /doa/matrix · /doa/rules · /doa/breaches · validate-transaction."
        />

        <MastersFilterStrip className="mb-6" />

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          <StatCard label="Matrix rows" value={d.matrixCount} testId="doa30-kpi-matrix-rows" />
          <StatCard label="Rules" value={d.rulesCount} testId="doa30-kpi-rules" />
          <StatCard label="Breaches (total)" value={d.breachTotal} testId="doa30-kpi-breach-total" />
          <StatCard label="Open breaches" value={d.openBreaches} testId="doa30-kpi-open-breaches" />
        </div>

        <SectionCard kicker="BREACHES" title="DoA breaches (recent)">
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[58vh]" testId="doa-breaches-table">
            <DataTableHead>
              <tr>
                <DataTableTh>Category</DataTableTh>
                <DataTableTh>Txn</DataTableTh>
                <DataTableTh align="right">Amount</DataTableTh>
                <DataTableTh align="right">Limit</DataTableTh>
                <DataTableTh>Required role</DataTableTh>
                <DataTableTh>Status</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {d.breachItems.length === 0 ? (
                <tr>
                  <td colSpan={6} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                    No breaches in scope.
                  </td>
                </tr>
              ) : null}
              {d.breachItems.map((row) => (
                <DataTableRow key={row.id} testId={`doa-br-${row.id}`} onClick={() => drillToTarget(drillTargetFromTxnId(row.transaction_id))}>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{row.category || "—"}</DataTableTd>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{row.transaction_id || "—"}</DataTableTd>
                  <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                    {fmtUSD(row.amount)}
                  </DataTableTd>
                  <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                    {fmtUSD(row.limit)}
                  </DataTableTd>
                  <DataTableTd className="text-xs text-foreground">{row.required_approver_role || "—"}</DataTableTd>
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
