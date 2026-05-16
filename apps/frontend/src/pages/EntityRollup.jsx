import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { TreeStructure, ArrowsClockwise, CaretLeft, Info } from "@phosphor-icons/react";
import {
  BarChart,
  Bar,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ReferenceLine,
} from "recharts";
import clsx from "clsx";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import { useMastersFilters } from "../lib/MastersFilterContext";
import { StatCard } from "../components/StatCard";
import { fmtDateTime, fmtUSD } from "../lib/format";
import {
  ROLLUP_PRIMARY_KEYS,
  formatRollupMetricValue,
  statSeverityForRollupKey,
} from "../lib/rollupMetricUi";
import { RC_STROKE, RC_TICK, rcTooltipStyle } from "../lib/rechartsTheme";

const URL_NODE = "node_id";
const URL_PROCESS = "rollup_process";

/** API sometimes returns a single point object; Recharts expects an array of rows. */
function asSparklineSeries(v) {
  if (Array.isArray(v)) return v;
  if (v && typeof v === "object" && !Array.isArray(v) && v.value != null && ("as_of" in v || "at" in v)) return [v];
  return [];
}

function RollupSkeleton() {
  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div className="animate-pulse space-y-4 p-4">
        <div className="h-10 w-1/3 rounded bg-zinc-200 dark:bg-zinc-800" />
        <div className="h-24 rounded-xl bg-zinc-100 dark:bg-zinc-900" />
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <div className="h-64 rounded-xl bg-zinc-100 dark:bg-zinc-900" />
          <div className="h-64 rounded-xl bg-zinc-200 dark:bg-zinc-800 lg:col-span-2" />
        </div>
      </div>
    </PageShell>
  );
}

export default function EntityRollup() {
  const dashboardParams = useDashboardFilterParams();
  const { hrefWithMasterParams } = useMastersFilters();
  const [searchParams, setSearchParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [drill, setDrill] = useState(null);
  const [nodeId, setNodeId] = useState(null);
  const [pathStack, setPathStack] = useState([]);
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState(null);
  const [chartHier, setChartHier] = useState(null);
  const [scatter, setScatter] = useState(null);
  const [boundariesOpen, setBoundariesOpen] = useState(false);
  const [hierarchyFocusIdx, setHierarchyFocusIdx] = useState(0);
  const hierBtnRefs = useRef([]);
  const drillSummaryRef = useRef(null);

  const syncUrl = useCallback(
    (nextNodeId, nextProcess) => {
      const next = new URLSearchParams(searchParams);
      if (nextNodeId) next.set(URL_NODE, nextNodeId);
      else next.delete(URL_NODE);
      if (nextProcess) next.set(URL_PROCESS, nextProcess);
      else next.delete(URL_PROCESS);
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data: d } = await http.get("/rollups/hierarchy", { params: dashboardParams });
      const root = d?.root || d?.node || null;
      setData(root ? { ...d, root } : d);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to load rollup hierarchy");
      setData(null);
    }
    setLoading(false);
  }, [dashboardParams]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!data?.root) return undefined;
    const root = data.root;
    const urlNode = searchParams.get(URL_NODE);
    const urlProc = searchParams.get(URL_PROCESS);
    if (!urlNode || urlNode === root.id) {
      setNodeId(root.id);
      setPathStack([{ id: root.id, name: root.name }]);
      setDrill(null);
      return undefined;
    }
    let cancelled = false;
    (async () => {
      try {
        const q = urlProc
          ? { node_id: urlNode, process: urlProc, ...dashboardParams }
          : { node_id: urlNode, ...dashboardParams };
        const { data: drillData } = await http.get("/rollups/drilldown", { params: q });
        if (cancelled) return;
        setDrill(drillData);
        setNodeId(urlNode);
        setPathStack([
          { id: root.id, name: root.name },
          { id: urlNode, name: drillData.node?.name || urlNode },
        ]);
      } catch {
        if (!cancelled) toast.error("Could not restore drill from URL");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [data?.root?.id, dashboardParams, searchParams.toString()]);

  const fetchViz = useCallback(
    async (nid) => {
      if (!nid) return;
      try {
        const [h, s, hist] = await Promise.all([
          http.get("/rollups/chart/hierarchy", { params: { node_id: nid, ...dashboardParams } }),
          http.get("/rollups/chart/scatter", { params: { node_id: nid, ...dashboardParams } }),
          http.get("/rollups/snapshots/history", { params: { node_id: nid, limit: 48, ...dashboardParams } }),
        ]);
        setChartHier(h.data);
        setScatter(s.data);
        setHistory(hist.data);
      } catch {
        setChartHier(null);
        setScatter(null);
        setHistory(null);
      }
    },
    [dashboardParams],
  );

  useEffect(() => {
    const nid = drill?.node?.id || nodeId || data?.root?.id;
    if (nid) fetchViz(nid);
  }, [drill?.node?.id, nodeId, data?.root?.id, fetchViz]);

  const drillAt = async (nid, proc = null, options = {}) => {
    const { mode = "push", baseStack = null } = options;
    setBusy(true);
    try {
      const q = proc ? { node_id: nid, process: proc, ...dashboardParams } : { node_id: nid, ...dashboardParams };
      const { data: d } = await http.get("/rollups/drilldown", { params: q });
      setDrill(d);
      setNodeId(nid);
      syncUrl(nid, proc || null);
      const name = d.node?.name || nid;
      if (mode === "replace" && Array.isArray(baseStack)) {
        setPathStack([...baseStack, { id: nid, name }]);
      } else {
        setPathStack((prev) => {
          if (prev.length && prev[prev.length - 1].id === nid) return prev;
          return [...prev, { id: nid, name }];
        });
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Drilldown failed");
    }
    setBusy(false);
  };

  const goBack = async () => {
    if (pathStack.length <= 1) return;
    const nextStack = pathStack.slice(0, -1);
    const parent = nextStack[nextStack.length - 1];
    setPathStack(nextStack);
    syncUrl(parent.id, null);
    setBusy(true);
    try {
      const { data: d } = await http.get("/rollups/drilldown", {
        params: { node_id: parent.id, ...dashboardParams },
      });
      setDrill(d);
      setNodeId(parent.id);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not load parent");
    }
    setBusy(false);
  };

  const recompute = async () => {
    setBusy(true);
    try {
      await http.post("/rollups/recompute");
      toast.success("Rollup snapshots refreshed");
      await load();
      const nid = drill?.node?.id || nodeId || data?.root?.id;
      if (nid) await fetchViz(nid);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Recompute failed");
    }
    setBusy(false);
  };

  const definitions = data?.metric_definitions || {};
  const targets = data?.rollup_targets || {};
  const framing = drill?.executive_framing || data?.executive_framing;
  const selectedMetrics = drill?.selected_node_metrics || drill?.metrics || data?.metrics || {};
  const reportingCcy = data?.reporting_ccy || "USD";

  const scalarMetricEntries = useMemo(() => {
    const skip = new Set([
      "case_severity_mix",
      "exception_severity_mix_open",
      "top_repeat_control_codes",
      "remediation_close_buckets",
      "top_entities_by_exposure",
    ]);
    const entries = Object.entries(selectedMetrics).filter(
      ([k, v]) => !skip.has(String(k)) && (typeof v === "number" || v === null),
    );
    const order = Array.isArray(ROLLUP_PRIMARY_KEYS) ? [...ROLLUP_PRIMARY_KEYS] : [];
    const pri = entries
      .filter(([k]) => order.includes(String(k)))
      .sort((a, b) => order.indexOf(String(a[0])) - order.indexOf(String(b[0])));
    const rest = entries.filter(([k]) => !order.includes(String(k))).sort(([a], [b]) => String(a).localeCompare(String(b)));
    return [...pri, ...rest];
  }, [selectedMetrics]);

  const barData = useMemo(
    () =>
      (chartHier?.children || []).map((c) => ({
        name: c.name || c.id,
        value: Number(c.value) || 0,
        id: c.id,
      })),
    [chartHier],
  );

  const scatterData = useMemo(
    () =>
      (scatter?.points || []).map((p) => ({
        entity: p.entity_code,
        readiness: Number(p.readiness) || 0,
        exposure: Number(p.exposure) || 0,
      })),
    [scatter],
  );

  const readinessTrend = useMemo(
    () => asSparklineSeries(history?.sparklines?.audit_readiness_pct),
    [history?.sparklines?.audit_readiness_pct],
  );

  useEffect(() => {
    const ch = data?.children || [];
    const ix = ch.findIndex((r) => r.hierarchy.id === nodeId);
    if (ix >= 0) setHierarchyFocusIdx(ix);
  }, [nodeId, data?.children]);

  useEffect(() => {
    if (!drill) return undefined;
    const t = window.setTimeout(() => drillSummaryRef.current?.focus(), 0);
    return () => window.clearTimeout(t);
  }, [drill?.drill, drill?.node?.id, drill?.process]);

  const handleHierarchyItemKeyDown = (e, idx) => {
    const ch = data?.children || [];
    const n = ch.length;
    if (!n) return;
    const focusAt = (j) => {
      requestAnimationFrame(() => hierBtnRefs.current[j]?.focus());
    };
    if (e.key === "ArrowDown") {
      e.preventDefault();
      const next = Math.min(n - 1, idx + 1);
      setHierarchyFocusIdx(next);
      focusAt(next);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      const next = Math.max(0, idx - 1);
      setHierarchyFocusIdx(next);
      focusAt(next);
    } else if (e.key === "Home") {
      e.preventDefault();
      setHierarchyFocusIdx(0);
      focusAt(0);
    } else if (e.key === "End") {
      e.preventDefault();
      const last = n - 1;
      setHierarchyFocusIdx(last);
      focusAt(last);
    } else if (e.key === "Enter" || e.key === " ") {
      const r = data?.root || data?.node;
      if (!r) return;
      e.preventDefault();
      const row = ch[idx];
      if (row) {
        drillAt(row.hierarchy.id, null, {
          mode: "replace",
          baseStack: [{ id: r.id, name: r.name }],
        });
      }
    }
  };

  const formatDeltaLine = (metricKey, deltaPack) => {
    if (!deltaPack || typeof deltaPack.delta !== "number") return null;
    const mk = metricKey == null ? "" : String(metricKey);
    const label = definitions[mk]?.label || mk.replace(/_/g, " ");
    const d = deltaPack.delta;
    const arrow = d >= 0 ? "▲" : "▼";
    let suffix = "";
    if (mk.includes("exposure")) suffix = ` (${formatRollupMetricValue(mk, Math.abs(d))} vs prior)`;
    else suffix = ` (${Math.abs(d).toFixed(2)} vs prior)`;
    return `${label}: ${arrow} ${suffix}`;
  };

  if (loading && !data) {
    return <RollupSkeleton />;
  }

  const root = data?.root || data?.node;

  if (!root && data?.error) {
    return (
      <PageShell maxWidth="max-w-[1600px]">
        <div className="p-8 text-sm text-muted-foreground" role="alert">
          {data.error}. Seed organization hierarchy to enable rollups.
        </div>
      </PageShell>
    );
  }

  if (!root) {
    return <RollupSkeleton />;
  }

  const cockpitHref = hrefWithMasterParams("/app/cfo");

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="entity-rollup">
        <PageHeader
          kicker="CONSOLIDATION"
          title="Entity rollups"
          icon={<TreeStructure size={18} />}
          subtitle={`Roll up governance KPIs across legal entities (${
            reportingCcy
          } reporting). Schema v${data?.schema_version ?? "—"}.`}
          right={
            <div className="flex flex-wrap items-center gap-2">
              <Link
                to={cockpitHref}
                className="crt-num hidden rounded-full border border-zinc-300 px-3 py-2 text-[10px] uppercase tracking-wider text-primary hover:bg-zinc-50 sm:inline-block dark:border-zinc-600 dark:hover:bg-zinc-900"
                data-testid="entity-rollup-open-cfo-cockpit"
              >
                CFO cockpit
              </Link>
              <button
                type="button"
                onClick={recompute}
                disabled={busy}
                className="flex h-10 items-center gap-2 rounded-full border border-zinc-300 bg-zinc-100 px-4 text-xs font-mono uppercase tracking-wider text-zinc-900 transition-colors hover:bg-zinc-200 disabled:opacity-40 dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100 dark:hover:bg-zinc-700"
              >
                <ArrowsClockwise size={14} /> Recompute
              </button>
            </div>
          }
        />

        <MastersFilterStrip className="mb-4" />

        {framing?.headline ? (
          <section
            className="mb-4 rounded-xl border border-zinc-200 bg-gradient-to-br from-zinc-50 to-white p-4 dark:border-zinc-800 dark:from-zinc-950 dark:to-zinc-900"
            aria-labelledby="rollup-exec-summary"
          >
            <p id="rollup-exec-summary" className="font-display text-base font-semibold text-foreground">
              {framing.headline}
            </p>
            {framing.worst_segments?.length ? (
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                {framing.worst_segments.map((w, i) => (
                  <li key={`${w.label}-${i}`}>
                    <span className="font-medium text-foreground">{w.label}</span>
                    {w.exposure != null ? ` · exposure ${formatRollupMetricValue("unresolved_high_risk_exposure", w.exposure)}` : ""}
                    {w.readiness != null ? ` · readiness ${formatRollupMetricValue("audit_readiness_pct", w.readiness)}` : ""}
                  </li>
                ))}
              </ul>
            ) : null}
            <div className="crt-num mt-2 text-[10px] uppercase tracking-wider text-muted-foreground">
              As of {fmtDateTime(drill?.as_of || data?.as_of)}
            </div>
          </section>
        ) : null}

        <button
          type="button"
          className="crt-num mb-4 flex items-center gap-1 text-[10px] uppercase tracking-wider text-primary hover:underline"
          aria-expanded={boundariesOpen}
          onClick={() => setBoundariesOpen((o) => !o)}
        >
          <Info size={14} aria-hidden /> How to read this rollup
        </button>
        {boundariesOpen ? (
          <div className="mb-4 rounded-lg border border-zinc-200 bg-white p-4 text-sm text-muted-foreground dark:border-zinc-700 dark:bg-zinc-950">
            <p>{data?.boundaries?.datasets}</p>
            <p className="mt-2">{data?.boundaries?.fx}</p>
          </div>
        ) : null}

        <nav aria-label="Rollup breadcrumb" className="mb-4 flex flex-wrap items-center gap-1 text-xs">
          {pathStack.map((seg, idx) => (
            <React.Fragment key={seg.id}>
              {idx > 0 ? <span className="text-muted-foreground">›</span> : null}
              <button
                type="button"
                className={clsx(
                  "rounded px-1 py-0.5 hover:bg-zinc-100 dark:hover:bg-zinc-900",
                  idx === pathStack.length - 1 ? "font-semibold text-foreground" : "text-muted-foreground",
                )}
                onClick={() =>
                  drillAt(seg.id, null, { mode: "replace", baseStack: pathStack.slice(0, idx) })
                }
              >
                {seg.name}
              </button>
            </React.Fragment>
          ))}
          {pathStack.length > 1 ? (
            <button
              type="button"
              onClick={() => goBack()}
              className="crt-num ml-2 inline-flex items-center gap-1 rounded border border-zinc-300 px-2 py-1 text-[10px] uppercase hover:bg-zinc-50 dark:border-zinc-600 dark:hover:bg-zinc-900"
            >
              <CaretLeft size={12} /> Back
            </button>
          ) : null}
        </nav>

        <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <SectionCard kicker="TARGETS" title="Readiness vs goal" bodyClassName="p-4">
            <div className="space-y-3">
              {["audit_readiness_pct", "remediation_sla_pct", "evidence_completeness_pct"].map((key) => {
                const cur = Number(selectedMetrics[key]);
                const tgt = Number(targets[key]);
                const pct = tgt > 0 ? Math.min(100, (cur / tgt) * 100) : 0;
                return (
                  <div key={key}>
                    <div className="flex justify-between text-[10px] uppercase text-muted-foreground">
                      <span>{definitions[key]?.label || key}</span>
                      <span>
                        {formatRollupMetricValue(key, cur)} / goal {formatRollupMetricValue(key, tgt)}
                      </span>
                    </div>
                    <div className="mt-1 h-2 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800">
                      <div
                        className="h-full rounded-full bg-[hsl(var(--chart-4))] transition-all"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </SectionCard>
          <SectionCard kicker="TREND" title="Audit readiness (snapshots)" bodyClassName="p-4">
            {readinessTrend.length > 1 ? (
              <div className="h-40 w-full min-h-[160px] min-w-0">
                <ResponsiveContainer width="100%" height={160} minWidth={0}>
                  <LineChart data={readinessTrend} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid stroke={RC_STROKE} strokeDasharray="3 3" />
                    <XAxis dataKey="as_of" tick={{ ...RC_TICK, fontSize: 9 }} />
                    <YAxis domain={[0, 100]} tick={{ ...RC_TICK, fontSize: 9 }} />
                    <Tooltip contentStyle={rcTooltipStyle} />
                    <ReferenceLine
                      y={targets.audit_readiness_pct}
                      stroke={RC_STROKE}
                      strokeDasharray="4 4"
                      label={{ value: "Goal", ...RC_TICK, fontSize: 9 }}
                    />
                    <Line type="monotone" dataKey="value" stroke="hsl(var(--chart-1))" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                Run <strong>Recompute snapshots</strong> at least twice to build readiness trend lines.
              </p>
            )}
            {history?.deltas_latest_pair && Object.keys(history.deltas_latest_pair).length ? (
              <ul className="crt-num mt-2 space-y-1 text-[10px] uppercase tracking-wider text-muted-foreground">
                {Object.entries(history.deltas_latest_pair).map(([k, pack]) => {
                  const line = formatDeltaLine(k, pack);
                  return line ? <li key={k}>{line}</li> : null;
                })}
              </ul>
            ) : null}
          </SectionCard>
        </div>

        <div className="mb-6 grid grid-cols-1 gap-4 xl:grid-cols-2">
          <SectionCard kicker="TREE" title="Exposure by child segment" bodyClassName="p-4">
            {barData.length ? (
              <div className="h-56 w-full min-h-[224px] min-w-0">
                <ResponsiveContainer width="100%" height={224} minWidth={0}>
                  <BarChart layout="vertical" data={barData} margin={{ top: 4, right: 16, left: 8, bottom: 4 }}>
                    <CartesianGrid stroke={RC_STROKE} strokeDasharray="3 3" />
                    <XAxis type="number" tick={{ ...RC_TICK, fontSize: 10 }} />
                    <YAxis type="category" dataKey="name" width={120} tick={{ ...RC_TICK, fontSize: 10 }} />
                    <Tooltip contentStyle={rcTooltipStyle} />
                    <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                      {barData.map((entry, i) => (
                        <Cell key={entry.id || i} cursor="pointer" fill="hsl(var(--chart-1) / 0.85)" />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No child segments or zero exposure in current view.</p>
            )}
          </SectionCard>
          <SectionCard kicker="RISK MAP" title="Entity readiness vs exposure" bodyClassName="p-4">
            {scatterData.length ? (
              <div className="h-56 w-full min-h-[224px] min-w-0">
                <ResponsiveContainer width="100%" height={224} minWidth={0}>
                  <ScatterChart margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
                    <CartesianGrid stroke={RC_STROKE} strokeDasharray="3 3" />
                    <XAxis type="number" dataKey="readiness" name="Readiness %" domain={[0, 100]} tick={{ ...RC_TICK, fontSize: 10 }} />
                    <YAxis type="number" dataKey="exposure" name="Exposure" tick={{ ...RC_TICK, fontSize: 10 }} />
                    <Tooltip
                      cursor={{ strokeDasharray: "3 3" }}
                      contentStyle={rcTooltipStyle}
                      formatter={(v, name) => [v, name]}
                    />
                    <Scatter data={scatterData} fill="hsl(var(--chart-3))" />
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No leaf entities under this node.</p>
            )}
          </SectionCard>
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <SectionCard
            className="lg:col-span-1"
            kicker="HIERARCHY"
            title="Org structure"
            bodyClassName="p-4"
          >
            <div className="space-y-2" role="tree" aria-label="Organization hierarchy">
              {(data.children || []).map((row, idx) => (
                <button
                  key={row.hierarchy.id}
                  ref={(el) => {
                    hierBtnRefs.current[idx] = el;
                  }}
                  type="button"
                  role="treeitem"
                  tabIndex={idx === hierarchyFocusIdx ? 0 : -1}
                  aria-selected={nodeId === row.hierarchy.id}
                  onKeyDown={(e) => handleHierarchyItemKeyDown(e, idx)}
                  onClick={() => {
                    setHierarchyFocusIdx(idx);
                    drillAt(row.hierarchy.id, null, {
                      mode: "replace",
                      baseStack: [{ id: root.id, name: root.name }],
                    });
                  }}
                  className={clsx(
                    "w-full rounded-xl border px-3 py-3 text-left text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
                    nodeId === row.hierarchy.id
                      ? "border-primary/35 bg-primary/5 ring-1 ring-primary/20"
                      : "border-zinc-200 bg-white hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900/40 dark:hover:bg-zinc-900/70",
                  )}
                >
                  <div className="text-foreground">{row.hierarchy.name}</div>
                  <div className="text-muted-foreground">
                    {row.hierarchy.type} · readiness {row.metrics?.audit_readiness_pct}%
                  </div>
                  {readinessTrend.length > 1 && nodeId === row.hierarchy.id ? (
                    <div className="mt-2 h-8 w-full min-h-[32px] min-w-0">
                      <ResponsiveContainer width="100%" height={32} minWidth={0}>
                        <LineChart data={readinessTrend}>
                          <Line type="monotone" dataKey="value" stroke="hsl(var(--chart-4))" strokeWidth={1} dot={false} />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  ) : null}
                </button>
              ))}
              {!data.children?.length ? (
                <p className="text-sm text-muted-foreground">No child segments under organization root.</p>
              ) : null}
            </div>
          </SectionCard>

          <SectionCard className="lg:col-span-2" kicker="ROLLUP" title="Metrics at selected node" bodyClassName="p-4">
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
              {scalarMetricEntries.map(([key, val]) => {
                const sk = String(key);
                const def = definitions[sk];
                const label = def?.label || sk.replace(/_/g, " ");
                const formatted = formatRollupMetricValue(sk, val);
                const sev = statSeverityForRollupKey(sk, typeof val === "number" ? val : null);
                return (
                  <div key={sk} title={def?.description || undefined} className="min-w-0">
                    <StatCard
                      label={label}
                      value={formatted}
                      severity={sev}
                      compact
                      testId={`rollup-metric-${sk}`}
                    />
                  </div>
                );
              })}
            </div>

            {selectedMetrics.case_severity_mix && Object.keys(selectedMetrics.case_severity_mix).length ? (
              <div className="mt-4">
                <p className="crt-num mb-2 text-[10px] uppercase text-muted-foreground">Open case severity mix</p>
                <div className="flex flex-wrap gap-2 text-xs">
                  {Object.entries(selectedMetrics.case_severity_mix).map(([k, v]) => (
                    <span key={k} className="rounded border border-zinc-200 px-2 py-1 dark:border-zinc-700">
                      {k}: {v}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}

            {Array.isArray(selectedMetrics.top_entities_by_exposure) && selectedMetrics.top_entities_by_exposure.length ? (
              <div className="mt-4">
                <p className="crt-num mb-2 text-[10px] uppercase text-muted-foreground">Top entities by high-severity exposure</p>
                <ul className="space-y-1 text-sm">
                  {selectedMetrics.top_entities_by_exposure.slice(0, 5).map((row) => (
                    <li key={row.entity_code}>
                      <span className="font-medium">{row.entity_code}</span>
                      <span className="text-muted-foreground"> · {fmtUSD(row.exposure)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {selectedMetrics.exception_severity_mix_open &&
            Object.keys(selectedMetrics.exception_severity_mix_open).length ? (
              <div className="mt-4">
                <p className="crt-num mb-2 text-[10px] uppercase text-muted-foreground">
                  {definitions.exception_severity_mix_open?.label || "Open exception severity mix"}
                </p>
                <div className="flex flex-wrap gap-2 text-xs">
                  {Object.entries(selectedMetrics.exception_severity_mix_open).map(([k, v]) => (
                    <span key={k} className="rounded border border-zinc-200 px-2 py-1 dark:border-zinc-700">
                      {k}: {v}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}

            {Array.isArray(selectedMetrics.top_repeat_control_codes) &&
            selectedMetrics.top_repeat_control_codes.length ? (
              <div className="mt-4">
                <p className="crt-num mb-2 text-[10px] uppercase text-muted-foreground">
                  {definitions.top_repeat_control_codes?.label || "Repeat control codes"}
                </p>
                <ul className="space-y-1 font-mono text-xs">
                  {selectedMetrics.top_repeat_control_codes.map((r) => (
                    <li key={r.control_code}>
                      <span className="font-medium text-foreground">{r.control_code}</span>
                      <span className="text-muted-foreground"> · {r.count} open findings</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {selectedMetrics.remediation_close_buckets &&
            typeof selectedMetrics.remediation_close_buckets === "object" ? (
              <div className="mt-4">
                <p className="crt-num mb-2 text-[10px] uppercase text-muted-foreground">
                  {definitions.remediation_close_buckets?.label || "Remediation time (closed cases)"}
                </p>
                <div className="flex flex-wrap gap-3 text-xs">
                  {Object.entries(selectedMetrics.remediation_close_buckets).map(([k, v]) => (
                    <span key={k} className="rounded border border-zinc-200 px-2 py-1 dark:border-zinc-700">
                      {k.replace(/_/g, " ")}: {v}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}

            {Number(selectedMetrics.action_queue_open_count) > 0 ? (
              <div className="mt-4 rounded-lg border border-primary/20 bg-primary/5 px-3 py-2 dark:bg-primary/10">
                <p className="crt-num text-[10px] uppercase text-muted-foreground">CFO action queue</p>
                <p className="text-sm text-foreground">
                  {selectedMetrics.action_queue_open_count} open · queue exposure{" "}
                  {formatRollupMetricValue("action_queue_open_exposure_usd", selectedMetrics.action_queue_open_exposure_usd)}
                </p>
                <Link
                  to={hrefWithMasterParams("/app/cfo-action-queue")}
                  className="crt-num mt-1 inline-block text-[10px] uppercase tracking-wider text-primary hover:underline"
                  data-testid="entity-rollup-open-action-queue"
                >
                  Open action queue →
                </Link>
              </div>
            ) : null}

            {drill && (
              <div className="mt-6 border-t border-zinc-200 pt-4 dark:border-zinc-800" aria-live="polite">
                <div
                  ref={drillSummaryRef}
                  tabIndex={-1}
                  className="mb-2 rounded-sm font-mono text-[10px] uppercase text-muted-foreground outline-none focus-visible:ring-2 focus-visible:ring-primary"
                >
                  Drill: {drill.drill} {drill.process ? `· ${drill.process}` : ""}
                </div>
                {drill.drill === "hierarchy" && (
                  <div className="space-y-1">
                    {(drill.rows || []).length === 0 ? (
                      <p className="text-sm text-muted-foreground">No nested segments.</p>
                    ) : (
                      (drill.rows || []).map((row) => (
                        <button
                          key={row.hierarchy.id}
                          type="button"
                          onClick={() => drillAt(row.hierarchy.id)}
                          className="w-full rounded-xl border border-zinc-200 bg-zinc-50/80 px-3 py-2.5 text-left text-xs transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-900/35 dark:hover:bg-zinc-900/55"
                        >
                          {row.hierarchy.name} · readiness {row.metrics?.audit_readiness_pct}% · exp{" "}
                          {formatRollupMetricValue("unresolved_high_risk_exposure", row.metrics?.unresolved_high_risk_exposure)}
                        </button>
                      ))
                    )}
                  </div>
                )}
                {drill.drill === "process" && (
                  <div className="space-y-1">
                    {(drill.rows || []).length === 0 ? (
                      <p className="text-sm text-muted-foreground">No processes with cases in scope.</p>
                    ) : (
                      (drill.rows || []).map((row) => (
                        <button
                          key={row.process}
                          type="button"
                          onClick={() => drillAt(drill.node.id, row.process)}
                          className="w-full rounded-xl border border-zinc-200 bg-zinc-50/80 px-3 py-2.5 text-left text-xs transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-900/35 dark:hover:bg-zinc-900/55"
                        >
                          {row.process} · open cases {row.metrics?.open_cases}
                        </button>
                      ))
                    )}
                  </div>
                )}
                {drill.drill === "case" && (
                  <ul className="max-h-80 space-y-1 overflow-y-auto">
                    {(drill.cases || []).length === 0 ? (
                      <li className="text-sm text-muted-foreground">No cases for this process in scope.</li>
                    ) : (
                      (drill.cases || []).map((c) => (
                        <li key={c.id}>
                          <Link to={`/app/cases/${encodeURIComponent(c.id)}`} className="text-xs font-mono text-primary hover:underline">
                            {c.title}
                          </Link>
                          <span className="ml-2 text-muted-foreground">
                            {c.severity} · {c.status}
                          </span>
                        </li>
                      ))
                    )}
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
