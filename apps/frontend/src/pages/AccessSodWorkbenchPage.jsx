import React, { useEffect, useState } from "react";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { drillTargetAccessConflictRow, useWorkbenchRowDrill } from "../lib/workbenchDrillNav";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import { StatCard } from "../components/StatCard";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";

export default function AccessSodWorkbenchPage() {
  const { drillToTarget } = useWorkbenchRowDrill();
  const [d, setD] = useState(null);

  const params = useDashboardFilterParams();
  useEffect(() => {
    const userParams = { ...params, limit: 1, offset: 0 };
    Promise.all([
      http.get("/access/users", { params: userParams }),
      http.get("/access/roles"),
      http.get("/access/sod-rules"),
      http.get("/access/sod-conflicts", { params }),
      http.get("/access/dormant-users", { params: { ...params, dormant_days: 90 } }),
      http.get("/access/privileged-users", { params }),
    ])
      .then(([usersMeta, roles, rules, conflicts, dormant, privileged]) => {
        const conflictItems = conflicts.data?.items || [];
        setD({
          userTotal: usersMeta.data?.total ?? 0,
          rolesCount: roles.data?.count ?? 0,
          rulesCount: rules.data?.count ?? 0,
          conflictCount: conflicts.data?.count ?? 0,
          dormantCount: dormant.data?.count ?? 0,
          privilegedCount: privileged.data?.count ?? 0,
          conflictItems: conflictItems.slice(0, 35),
        });
      })
      .catch(() => toast.error("Failed to load access & SoD workbench"));
  }, [params]);

  if (!d) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="access-sod-workbench-loading">
        Loading access & segregation of duties workbench…
      </div>
    );
  }

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="access-sod-workbench-page" data-access-sod-phase32-surface="true">
        <PageHeader
          kicker="ACCESS & SoD · PHASE 32"
          title="Users · roles · conflicts · certification APIs"
          subtitle={`${d.rolesCount} roles · ${d.rulesCount} SoD rules in library — /access/users · /access/sod-conflicts · certification-campaign.`}
        />

        <MastersFilterStrip className="mb-6" />

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          <StatCard label="Users (scope)" value={d.userTotal} testId="ac32-kpi-users" />
          <StatCard label="SoD conflicts" value={d.conflictCount} testId="ac32-kpi-sod-conflicts" />
          <StatCard label="Dormant (90d)" value={d.dormantCount} testId="ac32-kpi-dormant" />
          <StatCard label="Privileged" value={d.privilegedCount} testId="ac32-kpi-privileged" />
        </div>

        <SectionCard kicker="CONFLICTS" title="SoD rule violations (computed)">
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[58vh]" testId="access-sod-conflicts-table">
            <DataTableHead>
              <tr>
                <DataTableTh>User</DataTableTh>
                <DataTableTh>Rule</DataTableTh>
                <DataTableTh>Severity</DataTableTh>
                <DataTableTh>Roles</DataTableTh>
                <DataTableTh>Status</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {d.conflictItems.length === 0 ? (
                <tr>
                  <td colSpan={5} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                    No SoD conflicts in scope.
                  </td>
                </tr>
              ) : null}
              {d.conflictItems.map((row) => (
                <DataTableRow key={row.id} testId={`ac32-sc-${row.id}`} onClick={() => drillToTarget(drillTargetAccessConflictRow(row))}>
                  <DataTableTd className="text-xs text-foreground">{row.user_email || row.user_id || "—"}</DataTableTd>
                  <DataTableTd className="text-xs text-muted-foreground">{row.rule_name || row.rule_id || "—"}</DataTableTd>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{row.severity || "—"}</DataTableTd>
                  <DataTableTd className="text-xs text-muted-foreground max-w-[240px] truncate" title={(row.conflicting_roles || []).join(", ")}>
                    {(row.conflicting_roles || []).join(", ") || "—"}
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
