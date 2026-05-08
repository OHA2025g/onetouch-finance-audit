import React, { useEffect, useMemo, useState } from "react";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useMastersFilters } from "../lib/MastersFilterContext";
import { drillTargetPolicyBreach, useWorkbenchRowDrill } from "../lib/workbenchDrillNav";
import { buildDashboardFilterParams } from "../lib/mastersDashboardParams";
import { StatCard } from "../components/StatCard";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { fmtUSD } from "../lib/format";

export default function PolicyComplianceWorkbenchPage() {
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

  const attestationParams = useMemo(() => {
    const p = { ...params };
    delete p.entity_code;
    return p;
  }, [params]);

  useEffect(() => {
    Promise.all([
      http.get("/policies", { params }),
      http.get("/policies/attestations", { params: attestationParams }),
      http.get("/policies/attestations", { params: { ...attestationParams, status: "pending" } }),
      http.get("/policies/breaches", { params: { ...params, status: "open" } }),
      http.get("/policies/breaches", { params }),
    ])
      .then(([policies, attestations, pending, openBreaches, breachList]) =>
        setD({
          policyCount: policies.data?.count ?? 0,
          attestationTotal: attestations.data?.count ?? 0,
          pendingAttestations: pending.data?.count ?? 0,
          openBreaches: openBreaches.data?.count ?? 0,
          breachItems: (breachList.data?.items || []).slice(0, 35),
        }),
      )
      .catch(() => toast.error("Failed to load policy compliance workbench"));
  }, [params, attestationParams]);

  if (!d) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="policy-compliance-workbench-loading">
        Loading policy compliance workbench…
      </div>
    );
  }

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="policy-compliance-workbench-page" data-policy-compliance-phase31-surface="true">
        <PageHeader
          kicker="POLICY COMPLIANCE · PHASE 31"
          title="Library · attestations · breaches"
          subtitle="Governance attestations omit entity filter where seed rows are GLOBAL — APIs: /policies · /policies/attestations · /policies/breaches · attestation-campaign."
        />

        <MastersFilterStrip className="mb-6" />

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          <StatCard label="Active policies (scope)" value={d.policyCount} testId="pc31-kpi-policies" />
          <StatCard label="Attestations (all)" value={d.attestationTotal} testId="pc31-kpi-attestations" />
          <StatCard label="Pending attestations" value={d.pendingAttestations} testId="pc31-kpi-pending-attestations" />
          <StatCard label="Open breaches (scope)" value={d.openBreaches} testId="pc31-kpi-open-breaches" />
        </div>

        <SectionCard kicker="BREACHES" title="Policy breaches (recent)">
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[58vh]" testId="policy-breaches-table">
            <DataTableHead>
              <tr>
                <DataTableTh>Policy</DataTableTh>
                <DataTableTh>Type</DataTableTh>
                <DataTableTh>Severity</DataTableTh>
                <DataTableTh align="right">Exposure</DataTableTh>
                <DataTableTh>Status</DataTableTh>
                <DataTableTh>Summary</DataTableTh>
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
                <DataTableRow key={row.id} testId={`pc-br-${row.id}`} onClick={() => drillToTarget(drillTargetPolicyBreach(row))}>
                  <DataTableTd className="text-xs text-foreground">{row.policy_title || row.policy_id || "—"}</DataTableTd>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{row.breach_type || "—"}</DataTableTd>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{row.severity || "—"}</DataTableTd>
                  <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                    {fmtUSD(row.financial_exposure)}
                  </DataTableTd>
                  <DataTableTd className="text-xs text-foreground">{row.status || "—"}</DataTableTd>
                  <DataTableTd className="text-xs text-muted-foreground max-w-[280px] truncate" title={row.summary}>
                    {row.summary || "—"}
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
