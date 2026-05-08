import React, { useEffect, useState } from "react";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { StatCard } from "../components/StatCard";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";

export default function IntegrationHubWorkbenchPage() {
  const [d, setD] = useState(null);

  useEffect(() => {
    const load = async () => {
      try {
        const [listRes, logsRes, matrixRes] = await Promise.all([
          http.get("/integrations/connectors"),
          http.get("/integrations/connectors/sync-logs", { params: { limit: 100 } }),
          http.get("/integrations/connectors/matrix"),
        ]);
        const connectors = Array.isArray(listRes.data) ? listRes.data : [];
        const logItems = logsRes.data?.items || [];
        const catalog = matrixRes.data?.catalog || [];
        const configured = matrixRes.data?.configured || [];

        let firstRuns = 0;
        let firstHealthStatus = "—";
        if (connectors[0]?.id) {
          const cid = connectors[0].id;
          try {
            const [h, r] = await Promise.all([
              http.get(`/integrations/connectors/${cid}/health`),
              http.get(`/integrations/connectors/${cid}/runs`),
            ]);
            const runs = Array.isArray(r.data) ? r.data : [];
            firstRuns = runs.length;
            firstHealthStatus = h.data?.connector?.status || h.data?.last_run?.status || "—";
          } catch {
            /* first connector may be missing in rare DB states */
          }
        }

        setD({
          connectorCount: connectors.length,
          syncLogCount: logsRes.data?.count ?? logItems.length,
          catalogSize: catalog.length,
          configuredCount: Array.isArray(configured) ? configured.length : 0,
          firstConnectorLabel: connectors[0] ? `${connectors[0].name || connectors[0].id} (${connectors[0].provider || "?"})` : "—",
          firstConnectorRuns: firstRuns,
          firstHealthStatus,
          connectors: connectors.slice(0, 25),
          logItems: logItems.slice(0, 30),
        });
      } catch {
        toast.error("Failed to load integration hub workbench");
      }
    };
    load();
  }, []);

  if (!d) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="integration-hub-workbench-loading">
        Loading production integration hub…
      </div>
    );
  }

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="integration-hub-workbench-page" data-integration-hub-phase38-surface="true">
        <PageHeader
          kicker="INTEGRATIONS · PHASE 38"
          title="Connectors · sync logs · health"
          subtitle="SRS paths GET /integrations/connectors, /sync-logs, /matrix — first connector health + runs when instances exist."
        />

        <MastersFilterStrip className="mb-6" />

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          <StatCard label="Configured connectors" value={d.connectorCount} testId="int38-kpi-connectors" />
          <StatCard label="Sync log rows" value={d.syncLogCount} testId="int38-kpi-sync-logs" />
          <StatCard label="Catalog systems" value={d.catalogSize} testId="int38-kpi-catalog" />
          <StatCard label="Matrix configured" value={d.configuredCount} testId="int38-kpi-matrix-configured" />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-6 text-xs text-muted-foreground crt-num px-1">
          <div data-testid="int38-first-connector-summary">
            First instance: {d.firstConnectorLabel} · runs: {d.firstConnectorRuns} · status: {d.firstHealthStatus}
          </div>
        </div>

        <SectionCard kicker="INSTANCES" title="Connectors (top 25)">
          <DataTable className="rounded-none border-0 bg-transparent mb-10" maxHeightClassName="max-h-[36vh]" testId="int38-connectors-table">
            <DataTableHead>
              <tr>
                <DataTableTh>ID</DataTableTh>
                <DataTableTh>Name</DataTableTh>
                <DataTableTh>Provider</DataTableTh>
                <DataTableTh>Status</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {d.connectors.length === 0 ? (
                <tr>
                  <td colSpan={4} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                    No connectors. POST /integrations/connectors to register SAP or Oracle (demo).
                  </td>
                </tr>
              ) : null}
              {d.connectors.map((row) => (
                <DataTableRow key={row.id} testId={`int38-conn-${row.id}`}>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{row.id}</DataTableTd>
                  <DataTableTd className="text-xs text-foreground">{row.name || "—"}</DataTableTd>
                  <DataTableTd className="text-xs text-muted-foreground">{row.provider || "—"}</DataTableTd>
                  <DataTableTd className="text-xs text-foreground">{row.status || "—"}</DataTableTd>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </SectionCard>

        <SectionCard kicker="SYNC LOGS" title="Recent connector runs (global)">
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[40vh]" testId="int38-sync-logs-table">
            <DataTableHead>
              <tr>
                <DataTableTh>Run</DataTableTh>
                <DataTableTh>Connector</DataTableTh>
                <DataTableTh>Started</DataTableTh>
                <DataTableTh>Status</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {d.logItems.length === 0 ? (
                <tr>
                  <td colSpan={4} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                    No sync runs logged yet.
                  </td>
                </tr>
              ) : null}
              {d.logItems.map((row) => {
                const rk = row.id || `${row.connector_id}-${row.run_start}-${row.status || ""}`;
                return (
                <DataTableRow key={rk} testId={`int38-log-${rk}`}>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{row.id || "—"}</DataTableTd>
                  <DataTableTd className="text-xs text-foreground">{row.connector_id || "—"}</DataTableTd>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{row.run_start || "—"}</DataTableTd>
                  <DataTableTd className="text-xs text-foreground">{row.status || "—"}</DataTableTd>
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
