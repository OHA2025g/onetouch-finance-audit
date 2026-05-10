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

export default function O2cAuditWorkbenchPage() {
  const { drillToTarget } = useWorkbenchRowDrill();
  const [d, setD] = useState(null);

  const params = useDashboardFilterParams();
  useEffect(() => {
    const listParams = { ...params, limit: 35, offset: 0 };
    Promise.all([http.get("/o2c/summary", { params }), http.get("/o2c/customers", { params: listParams })])
      .then(([s, c]) =>
        setD({
          summary: s.data || {},
          customers: c.data?.items || [],
        }),
      )
      .catch(() => toast.error("Failed to load O2C audit workbench"));
  }, [params]);

  if (!d) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="o2c-workbench-loading">
        Loading O2C audit workbench…
      </div>
    );
  }

  const k = d.summary?.kpis || {};

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="o2c-workbench-page" data-o2c-audit-surface="true">
        <PageHeader
          kicker="O2C AUDIT · PHASE 21"
          title="Order-to-cash & revenue context"
          subtitle="Customers + AR snapshot — APIs: /o2c/summary · /o2c/customers · revenue-cutoff · credit-limit-breaches · concentration."
        />

        <MastersFilterStrip className="mb-6" />

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
          <StatCard label="Customers" value={k.customer_count} testId="o2c-kpi-customers" />
          <StatCard label="AR invoices" value={k.ar_invoice_count} testId="o2c-kpi-ar-invoices" />
          <StatCard label="AR open" value={fmtUSD(k.ar_open_amount)} testId="o2c-kpi-ar-open" />
        </div>

        <SectionCard kicker="CUSTOMERS" title="Customer master (scoped)">
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[58vh]" testId="o2c-customers-table">
            <DataTableHead>
              <tr>
                <DataTableTh>Code</DataTableTh>
                <DataTableTh>Name</DataTableTh>
                <DataTableTh>Entity</DataTableTh>
                <DataTableTh align="right">Credit limit</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {d.customers.length === 0 ? (
                <tr>
                  <td colSpan={4} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                    No customers in scope.
                  </td>
                </tr>
              ) : null}
              {d.customers.map((c) => (
                <DataTableRow key={c.id} testId={`o2c-cust-${c.id}`} onClick={() => drillToTarget(c.id ? { type: "customer", id: String(c.id) } : null)}>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{c.customer_code || c.id}</DataTableTd>
                  <DataTableTd className="text-sm text-foreground">{c.customer_name || "—"}</DataTableTd>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{c.entity || "—"}</DataTableTd>
                  <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                    {fmtUSD(c.credit_limit)}
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
