import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { TreeStructure, ArrowsClockwise } from "@phosphor-icons/react";
import clsx from "clsx";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";

export default function EntityRollup() {
  const dashboardParams = useDashboardFilterParams();
  const [data, setData] = useState(null);
  const [drill, setDrill] = useState(null);
  const [nodeId, setNodeId] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data: d } = await http.get("/rollups/hierarchy", { params: dashboardParams });
      const root = d?.root || d?.node || null;
      const normalized = root ? { ...d, root } : d;
      setData(normalized);
      setNodeId((curr) => (curr ? curr : (root?.id || null)));
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to load rollup hierarchy");
      setData(null);
    }
  }, [dashboardParams]);

  useEffect(() => {
    load();
  }, [load]);

  const drillAt = async (nid, proc = null) => {
    setBusy(true);
    try {
      const q = proc
        ? { node_id: nid, process: proc, ...dashboardParams }
        : { node_id: nid, ...dashboardParams };
      const { data: d } = await http.get("/rollups/drilldown", { params: q });
      setDrill(d);
      setNodeId(nid);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Drilldown failed");
    }
    setBusy(false);
  };

  const recompute = async () => {
    setBusy(true);
    try {
      await http.post("/rollups/recompute");
      toast.success("Rollup snapshots refreshed");
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Recompute failed");
    }
    setBusy(false);
  };

  if (!data?.root) {
    return <div className="p-8 font-mono text-xs text-[#737373]">Loading hierarchy…</div>;
  }

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="entity-rollup">
        <PageHeader
          kicker="CONSOLIDATION"
          title="Entity rollups"
          icon={<TreeStructure size={18} />}
          subtitle={`Drill from organization → region → legal entity → process → cases. Reporting currency: ${data.reporting_ccy || "USD"}.`}
          right={
            <button
              type="button"
              onClick={recompute}
              disabled={busy}
              className="flex h-10 items-center gap-2 rounded-full border border-zinc-300 bg-zinc-100 px-4 text-xs font-mono uppercase tracking-wider text-zinc-900 transition-colors hover:bg-zinc-200 disabled:opacity-40 dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100 dark:hover:bg-zinc-700"
            >
              <ArrowsClockwise size={14} /> Recompute snapshots
            </button>
          }
        />

        <MastersFilterStrip className="mb-6" />

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <SectionCard className="lg:col-span-1" kicker="HIERARCHY" title="Org structure" bodyClassName="p-4">
            <div className="space-y-2">
              {(data.children || []).map((row) => (
                <button
                  key={row.hierarchy.id}
                  type="button"
                  onClick={() => drillAt(row.hierarchy.id)}
                  className={clsx(
                    "w-full rounded-xl border px-3 py-3 text-left text-xs font-mono transition-colors",
                    nodeId === row.hierarchy.id
                      ? "border-primary/35 bg-primary/5 ring-1 ring-primary/20"
                      : "border-zinc-200 bg-white hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900/40 dark:hover:bg-zinc-900/70"
                  )}
                >
                  <div className="text-foreground">{row.hierarchy.name}</div>
                  <div className="text-muted-foreground">{row.hierarchy.type} · readiness {row.metrics?.audit_readiness_pct}%</div>
                </button>
              ))}
            </div>
          </SectionCard>

          <SectionCard className="lg:col-span-2" kicker="ROLLUP" title="Metrics">
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs font-mono">
              {data.metrics && Object.entries(data.metrics).map(([k, v]) => (
                <div
                  key={k}
                  className="rounded-xl border border-zinc-200 bg-zinc-50/90 p-3 backdrop-blur dark:border-zinc-700 dark:bg-zinc-900/50"
                >
                  <div className="text-muted-foreground">{k.replace(/_/g, " ")}</div>
                  <div className="mt-1 text-lg text-foreground">{typeof v === "number" ? v : String(v)}</div>
                </div>
              ))}
            </div>

            {drill && (
              <div className="mt-6 border-t border-zinc-200 pt-4 dark:border-zinc-800">
                <div className="mb-2 font-mono text-[10px] uppercase text-muted-foreground">
                  Drill: {drill.drill} {drill.process ? `· ${drill.process}` : ""}
                </div>
              {drill.drill === "hierarchy" && (
                <div className="space-y-1">
                  {(drill.rows || []).map((row) => (
                    <button
                      key={row.hierarchy.id}
                      type="button"
                      onClick={() => drillAt(row.hierarchy.id)}
                      className="w-full rounded-xl border border-zinc-200 bg-zinc-50/80 px-3 py-2.5 text-left text-xs transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-900/35 dark:hover:bg-zinc-900/55"
                    >
                      {row.hierarchy.name} · readiness {row.metrics?.audit_readiness_pct}%
                    </button>
                  ))}
                </div>
              )}
              {drill.drill === "process" && (
                <div className="space-y-1">
                  {(drill.rows || []).map((row) => (
                    <button
                      key={row.process}
                      type="button"
                      onClick={() => drillAt(drill.node.id, row.process)}
                      className="w-full rounded-xl border border-zinc-200 bg-zinc-50/80 px-3 py-2.5 text-left text-xs transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-900/35 dark:hover:bg-zinc-900/55"
                    >
                      {row.process} · open cases {row.metrics?.open_cases}
                    </button>
                  ))}
                </div>
              )}
              {drill.drill === "case" && (
                <ul className="space-y-1 max-h-80 overflow-y-auto">
                  {(drill.cases || []).map((c) => (
                    <li key={c.id}>
                      <Link to={`/app/cases/${encodeURIComponent(c.id)}`} className="text-primary text-xs font-mono hover:underline">
                        {c.title}
                      </Link>
                      <span className="ml-2 text-muted-foreground">{c.severity} · {c.status}</span>
                    </li>
                  ))}
                </ul>
              )}
              </div>
            )}
          </SectionCard>
        </div>
      </div>
    </PageShell>
  );
}
