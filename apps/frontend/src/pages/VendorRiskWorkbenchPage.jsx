import React, { useEffect, useState } from "react";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useWorkbenchRowDrill } from "../lib/workbenchDrillNav";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import { StatCard } from "../components/StatCard";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";

export default function VendorRiskWorkbenchPage() {
  const { drillToTarget } = useWorkbenchRowDrill();
  const [d, setD] = useState(null);

  const params = useDashboardFilterParams();
  useEffect(() => {
    const listParams = { ...params, limit: 30, offset: 0 };
    Promise.all([http.get("/vendor-risk/summary", { params }), http.get("/vendor-risk/vendors", { params: listParams })])
      .then(([s, v]) =>
        setD({
          summary: s.data,
          vendors: v.data?.items || [],
        }),
      )
      .catch(() => toast.error("Failed to load vendor risk workbench"));
  }, [params]);

  if (!d) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="vr-workbench-loading">
        Loading vendor risk workbench…
      </div>
    );
  }

  const k = d.summary?.kpis || {};

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="vr-workbench-page" data-vendor-risk-surface="true">
        <PageHeader
          kicker="VENDOR RISK · PHASE 19"
          title="Vendor risk & procurement audit"
          subtitle="Summary + vendor master slice — APIs: /vendor-risk/summary · /vendor-risk/vendors · duplicates · bank-change-alerts · non-po-spend."
        />

        <MastersFilterStrip className="mb-6" />

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
          <StatCard label="Vendors" value={k.vendor_count} testId="vr-kpi-vendor-count" />
          <StatCard label="Dup signals" value={k.duplicate_vendor_signals} severity="warning" testId="vr-kpi-dup-signals" />
          <StatCard label="Recent bank changes" value={k.recent_bank_changes} testId="vr-kpi-bank-changes" />
        </div>

        <SectionCard kicker="MASTER" title="Vendors in scope">
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[58vh]" testId="vr-vendors-table">
            <DataTableHead>
              <tr>
                <DataTableTh>Code</DataTableTh>
                <DataTableTh>Name</DataTableTh>
                <DataTableTh>Entity</DataTableTh>
                <DataTableTh>PAN</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {d.vendors.length === 0 ? (
                <tr>
                  <td colSpan={4} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                    No vendors in scope.
                  </td>
                </tr>
              ) : null}
              {d.vendors.map((v) => (
                <DataTableRow key={v.id} testId={`vr-v-${v.id}`} onClick={() => drillToTarget(v.id ? { type: "vendor", id: String(v.id) } : null)}>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{v.vendor_code || v.id}</DataTableTd>
                  <DataTableTd className="text-sm text-foreground">{v.vendor_name || "—"}</DataTableTd>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{v.entity || "—"}</DataTableTd>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{v.pan || "—"}</DataTableTd>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </SectionCard>
      </div>
    </PageShell>
  );
}
