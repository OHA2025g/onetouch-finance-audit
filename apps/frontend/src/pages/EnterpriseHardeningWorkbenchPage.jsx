import React, { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { useAuth } from "../lib/auth";
import { drillTargetAuditLogObject, useWorkbenchRowDrill } from "../lib/workbenchDrillNav";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { StatCard } from "../components/StatCard";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";

export default function EnterpriseHardeningWorkbenchPage() {
  const { user } = useAuth();
  const { drillToTarget } = useWorkbenchRowDrill();
  const [d, setD] = useState(null);

  useEffect(() => {
    if (user?.role !== "Super Admin") return undefined;

    const load = async () => {
      try {
        const [liveRes, healthRes, logsRes, cfgRes] = await Promise.all([
          http.get("/system/health/live"),
          http.get("/system/health"),
          http.get("/system/audit-logs", { params: { limit: 25 } }),
          http.get("/system/security-config"),
        ]);
        const live = liveRes.data || {};
        const health = healthRes.data || {};
        const logItems = logsRes.data?.items || [];
        const cfg = cfgRes.data?.config || {};
        const counts = health.counts || {};
        const tracked = Object.keys(counts).filter((k) => counts[k] >= 0).length;

        setD({
          liveStatus: live.status || "—",
          deepStatus: health.status || "—",
          auditTotal: logsRes.data?.total ?? logItems.length,
          auditPage: logItems.length,
          securityKeys: Object.keys(cfg).length,
          configJson: JSON.stringify(cfg, null, 2),
          logItems: logItems.slice(0, 25),
          trackedCollections: tracked,
        });
      } catch {
        toast.error("Failed to load enterprise hardening workbench");
      }
    };

    load();
    return undefined;
  }, [user]);

  if (!user) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="enterprise-hardening-workbench-loading">
        Loading…
      </div>
    );
  }

  if (user.role !== "Super Admin") {
    return <Navigate to="/app/cfo" replace />;
  }

  if (!d) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="enterprise-hardening-workbench-loading">
        Loading Phase 40 system surfaces…
      </div>
    );
  }

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="enterprise-hardening-workbench-page" data-enterprise-hardening-phase40-surface="true">
        <PageHeader
          kicker="ENTERPRISE · PHASE 40"
          title="Health · audit logs · security config"
          subtitle="Super Admin only — matches L4: public /system/health/live; protected /system/health, /audit-logs, /security-config."
        />

        <MastersFilterStrip className="mb-6" />

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          <StatCard label="Liveness (public)" value={d.liveStatus} testId="eh40-kpi-live" />
          <StatCard label="Deep health" value={d.deepStatus} testId="eh40-kpi-deep-health" />
          <StatCard label="Audit log rows (page)" value={d.auditPage} subtle={`total ${d.auditTotal}`} testId="eh40-kpi-audit-page" />
          <StatCard label="Config top-level keys" value={d.securityKeys} subtle={`${d.trackedCollections} collections counted`} testId="eh40-kpi-security-keys" />
        </div>

        <SectionCard kicker="SECURITY CONFIG" title="Singleton (read-only in UI)">
          <pre
            className="crt-num max-h-[28vh] overflow-auto rounded-md border border-border bg-muted/30 p-3 text-[11px] leading-relaxed"
            data-testid="eh40-security-config-pre"
          >
            {d.configJson}
          </pre>
        </SectionCard>

        <SectionCard kicker="AUDIT LOG" title="Recent events (system/* listing)">
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[40vh]" testId="eh40-audit-table">
            <DataTableHead>
              <tr>
                <DataTableTh>Time</DataTableTh>
                <DataTableTh>Action</DataTableTh>
                <DataTableTh>Actor</DataTableTh>
                <DataTableTh>Object</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {d.logItems.length === 0 ? (
                <tr>
                  <td colSpan={4} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                    No audit rows in this window.
                  </td>
                </tr>
              ) : null}
              {d.logItems.map((row, i) => {
                const rk = row.event_ts || row.id || `row-${i}`;
                return (
                  <DataTableRow key={rk} testId={`eh40-audit-${i}`} onClick={() => drillToTarget(drillTargetAuditLogObject(row))}>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">{row.event_ts || "—"}</DataTableTd>
                    <DataTableTd className="text-xs text-foreground">{row.action_type || "—"}</DataTableTd>
                    <DataTableTd className="text-xs text-muted-foreground">{row.actor_user_email || "—"}</DataTableTd>
                    <DataTableTd className="text-xs text-foreground">
                      {[row.object_type, row.object_id].filter(Boolean).join(" · ") || "—"}
                    </DataTableTd>
                  </DataTableRow>
                );
              })}
            </DataTableBody>
          </DataTable>
        </SectionCard>
      </div>
    </PageShell>
  );
}
