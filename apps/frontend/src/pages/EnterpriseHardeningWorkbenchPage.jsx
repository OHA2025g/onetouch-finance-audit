import React, { useEffect, useMemo, useState } from "react";
import { Navigate } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { useAuth } from "../lib/auth";
import { drillTargetAuditLogObject, useWorkbenchRowDrill } from "../lib/workbenchDrillNav";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { StatCard } from "../components/StatCard";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import WaveProgramDeliveryPanel from "../components/WaveProgramDeliveryPanel";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";

function eh40ScopeLabel(row) {
  if (!row) return "—";
  if (row.scope_label) return row.scope_label;
  if (row.entity_code != null && String(row.entity_code).trim() !== "") return String(row.entity_code);
  return "ALL ENTITIES";
}

function eh40Snapshot(label, row) {
  if (!row) return "—";
  if (label === "RPT register") {
    return `${row.related_parties_count ?? 0} parties · ${row.rpt_transactions_count ?? 0} txns`;
  }
  if (label === "DOA rules") {
    return `${row.rules_count ?? 0} rules · ${row.matrix_rows ?? 0} matrix rows`;
  }
  if (label === "SoD campaigns") {
    return `${row.campaigns_total ?? 0} campaign(s)`;
  }
  if (label === "MDQ summary") {
    return `${row.open_findings ?? 0} open findings`;
  }
  return "—";
}

export default function EnterpriseHardeningWorkbenchPage() {
  const { user } = useAuth();
  const { drillToTarget } = useWorkbenchRowDrill();
  const [d, setD] = useState(null);
  const dashboardParams = useDashboardFilterParams();
  const complianceDepthParams = useMemo(() => {
    const ec = dashboardParams.entity_code;
    return ec ? { entity_code: ec } : {};
  }, [dashboardParams.entity_code]);
  const [govDepth, setGovDepth] = useState(null);

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

  useEffect(() => {
    if (user?.role !== "Super Admin") {
      setGovDepth(null);
      return undefined;
    }
    let cancelled = false;
    const paths = ["/compliance-depth/rpt/register", "/compliance-depth/doa/rules", "/compliance-depth/sod/campaigns", "/compliance-depth/mdq/summary"];
    Promise.all(paths.map((p) => http.get(p, { params: complianceDepthParams })))
      .then(([rpt, doa, sod, mdq]) => {
        if (cancelled) return;
        setGovDepth({ rpt: rpt.data, doa: doa.data, sod: sod.data, mdq: mdq.data });
      })
      .catch(() => {
        if (!cancelled) setGovDepth(null);
      });
    return () => {
      cancelled = true;
    };
  }, [user?.role, complianceDepthParams]);

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
          title="Wave program · health · audit · security"
          subtitle="Super Admin only — parallel waves 0–8 (40 modules) plus live L4 surfaces: /system/health/live; /system/health, /audit-logs, /security-config."
        />

        <WaveProgramDeliveryPanel />

        <MastersFilterStrip className="mb-6" />

        {govDepth ? (
          <SectionCard
            kicker="COMPLIANCE DEPTH · L4"
            title="Governance depth APIs — live counts (masters entity_code when set)"
            bodyClassName="p-0"
            className="mb-6"
          >
            <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[240px]" testId="eh40-gov-depth-table">
              <DataTableHead>
                <tr>
                  <DataTableTh>Surface</DataTableTh>
                  <DataTableTh>Scope</DataTableTh>
                  <DataTableTh>Live snapshot</DataTableTh>
                  <DataTableTh>Summary</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {[
                  { key: "rpt", label: "RPT register", row: govDepth.rpt },
                  { key: "doa", label: "DOA rules", row: govDepth.doa },
                  { key: "sod", label: "SoD campaigns", row: govDepth.sod },
                  { key: "mdq", label: "MDQ summary", row: govDepth.mdq },
                ].map(({ key, label, row }) => (
                  <DataTableRow key={key} testId={`eh40-gov-depth-${key}`}>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">{label}</DataTableTd>
                    <DataTableTd className="crt-num text-xs text-foreground">{eh40ScopeLabel(row)}</DataTableTd>
                    <DataTableTd className="crt-num text-xs text-foreground">{eh40Snapshot(label, row)}</DataTableTd>
                    <DataTableTd className="text-xs text-muted-foreground max-w-[360px] truncate" title={row?.note}>
                      {row?.note || "—"}
                    </DataTableTd>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </DataTable>
          </SectionCard>
        ) : null}

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
