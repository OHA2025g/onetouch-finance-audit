import React, { useEffect, useMemo, useState } from "react";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import { SeverityBadge } from "../components/Badges";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";

function countTotal(obj) {
  return Object.values(obj || {}).reduce((a, b) => a + Number(b || 0), 0);
}

export default function AdminMasterDataQualityPage() {
  const dashboardParams = useDashboardFilterParams();
  const [summary, setSummary] = useState(null);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = React.useCallback(() => {
    setLoading(true);
    Promise.all([
      http.get("/dq/masters/summary", { params: dashboardParams }),
      http.get("/dq/masters/findings", { params: { limit: 200, offset: 0, status: "open", ...dashboardParams } }),
    ])
      .then(([s, f]) => {
        setSummary(s?.data || null);
        setRows(f?.data?.items || []);
      })
      .catch((e) => toast.error(e?.response?.data?.detail || "Failed to load master DQ"))
      .finally(() => setLoading(false));
  }, [dashboardParams]);

  useEffect(() => {
    load();
  }, [load]);

  const ordered = useMemo(() => {
    const copy = [...(rows || [])];
    copy.sort((a, b) => String(b.at || "").localeCompare(String(a.at || "")));
    return copy;
  }, [rows]);

  const openBySev = summary?.open_by_severity || {};
  const openByType = summary?.open_by_type || {};

  return (
    <PageShell maxWidth="max-w-[1400px]">
      <div data-testid="admin-master-dq-page">
        <PageHeader
          kicker="ADMIN"
          title="Master data quality"
          subtitle="Deterministic DQ rules for demo masters (Phase 2 L4 hardening)."
        />

        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
          <SectionCard kicker="OPEN" title="Findings by severity">
            {loading && !summary ? (
              <div className="crt-overline text-muted-foreground">Loading…</div>
            ) : (
              <div className="space-y-2 text-sm">
                {["critical", "warning", "info"].map((k) => (
                  <div key={k} className="flex items-center justify-between">
                    <SeverityBadge severity={k} />
                    <span className="font-mono text-xs">{String(openBySev[k] || 0)}</span>
                  </div>
                ))}
                <div className="mt-3 flex items-center justify-between border-t border-zinc-200 pt-3 text-xs dark:border-zinc-800">
                  <span className="crt-num uppercase tracking-wider text-muted-foreground">Total open</span>
                  <span className="font-mono text-xs text-foreground">{String(countTotal(openBySev))}</span>
                </div>
              </div>
            )}
          </SectionCard>

          <SectionCard kicker="OPEN" title="Findings by master type" bodyClassName="p-0">
            {loading && !summary ? (
              <div className="crt-overline p-6 text-muted-foreground">Loading…</div>
            ) : (
              <div className="divide-y divide-zinc-200 dark:divide-zinc-800">
                {Object.entries(openByType).length ? (
                  Object.entries(openByType)
                    .sort((a, b) => Number(b[1]) - Number(a[1]))
                    .slice(0, 12)
                    .map(([k, v]) => (
                      <div key={k} className="flex items-center justify-between px-4 py-3">
                        <span className="crt-num text-xs uppercase tracking-wider text-muted-foreground">{k}</span>
                        <span className="font-mono text-xs text-foreground">{String(v)}</span>
                      </div>
                    ))
                ) : (
                  <div className="p-6 text-sm text-muted-foreground">No open findings.</div>
                )}
              </div>
            )}
          </SectionCard>

          <SectionCard kicker="ACTIONS" title="Recompute (server-side)">
            <p className="text-sm text-muted-foreground">
              Use the API <span className="font-mono text-xs text-foreground">POST /api/dq/masters/recompute</span> as
              Super Admin to refresh findings after seed updates or master edits.
            </p>
            <button
              type="button"
              className="mt-4 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
              onClick={() => load()}
            >
              Refresh
            </button>
          </SectionCard>
        </div>

        <SectionCard kicker="FINDINGS" title="Latest open findings" className="mt-4" bodyClassName="p-0">
          {loading && !rows.length ? (
            <div className="crt-overline p-8 text-muted-foreground">Loading findings…</div>
          ) : !rows.length ? (
            <div className="p-8 text-sm text-muted-foreground">
              No findings found. If this is a fresh DB, seed data and run recompute.
            </div>
          ) : (
            <DataTable>
              <DataTableHead>
                <DataTableRow>
                  <DataTableTh>At</DataTableTh>
                  <DataTableTh>Severity</DataTableTh>
                  <DataTableTh>Type</DataTableTh>
                  <DataTableTh>Object</DataTableTh>
                  <DataTableTh>Rule</DataTableTh>
                  <DataTableTh>Message</DataTableTh>
                </DataTableRow>
              </DataTableHead>
              <DataTableBody>
                {ordered.map((r) => (
                  <DataTableRow key={r.id}>
                    <DataTableTd className="font-mono text-xs">{r.at || "—"}</DataTableTd>
                    <DataTableTd>
                      <SeverityBadge severity={r.severity || "info"} />
                    </DataTableTd>
                    <DataTableTd className="text-sm">{r.master_type || "—"}</DataTableTd>
                    <DataTableTd className="font-mono text-xs">{r.object_id || "—"}</DataTableTd>
                    <DataTableTd className="font-mono text-xs">{r.rule_id || "—"}</DataTableTd>
                    <DataTableTd className="text-sm">{r.message || "—"}</DataTableTd>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </DataTable>
          )}
        </SectionCard>
      </div>
    </PageShell>
  );
}

