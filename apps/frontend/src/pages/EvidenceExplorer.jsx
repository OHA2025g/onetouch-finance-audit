import React, { useEffect, useState, useMemo, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { SeverityBadge } from "../components/Badges";
import { fmtUSD } from "../lib/format";
import { MagnifyingGlass, Graph as GraphIcon, Table as TableIcon } from "@phosphor-icons/react";
import clsx from "clsx";
import InsightPanel from "../components/InsightPanel";
import DrillContextBar from "../components/DrillContextBar";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import { graphNodeDrillPath } from "../lib/drillPaths";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";

const LIST_PAGE = 120;

/** Accent strokes on light cards; transaction uses zinc so it stays visible on white fill. */
const NODE_STROKE = {
  exception: "hsl(var(--destructive))",
  control: "hsl(var(--primary))",
  transaction: "#a1a1aa",
  policy: "hsl(var(--chart-3))",
  case: "hsl(var(--chart-4))",
  user: "#71717a",
  test: "#71717a",
  working_paper: "#a16207",
};

export default function EvidenceExplorer() {
  const { exceptionId } = useParams();
  const nav = useNavigate();
  const [exceptions, setExceptions] = useState([]);
  const [totalCount, setTotalCount] = useState(null);
  const [nextOffset, setNextOffset] = useState(0);
  const [listLoading, setListLoading] = useState(false);
  const [query, setQuery] = useState("");
  const [graph, setGraph] = useState(null);
  const [view, setView] = useState("graph");

  const scopeParams = useDashboardFilterParams();

  const loadMore = useCallback(async () => {
    if (listLoading || totalCount == null || nextOffset >= totalCount) return;
    setListLoading(true);
    try {
      const listRes = await http.get("/exceptions", { params: { limit: LIST_PAGE, offset: nextOffset, ...scopeParams } });
      const rows = listRes.data;
      setExceptions((prev) => [...prev, ...rows]);
      setNextOffset((o) => o + rows.length);
    } catch {
      toast.error("Failed to load exceptions");
    } finally {
      setListLoading(false);
    }
  }, [scopeParams, nextOffset, listLoading, totalCount]);

  useEffect(() => {
    setNextOffset(0);
    (async () => {
      setListLoading(true);
      try {
        const [countRes, listRes] = await Promise.all([
          http.get("/exceptions/count", { params: scopeParams }),
          http.get("/exceptions", { params: { limit: LIST_PAGE, offset: 0, ...scopeParams } }),
        ]);
        setTotalCount(countRes.data.count);
        const rows = listRes.data;
        setExceptions(rows);
        setNextOffset(rows.length);
      } catch {
        toast.error("Failed to load exceptions");
      } finally {
        setListLoading(false);
      }
    })();
  }, [scopeParams]);

  useEffect(() => {
    if (exceptionId || exceptions.length === 0) return;
    nav(`/app/evidence/${encodeURIComponent(exceptions[0].id)}`, { replace: true });
  }, [exceptionId, exceptions, nav]);

  useEffect(() => {
    if (!exceptionId) {
      setGraph(null);
      return;
    }
    const ac = new AbortController();
    setGraph(null);
    const path = `/evidence/${encodeURIComponent(exceptionId)}`;
    http
      .get(path, { signal: ac.signal })
      .then((r) => setGraph(r.data))
      .catch((err) => {
        if (err?.code === "ERR_CANCELED" || err?.name === "CanceledError") return;
        setGraph(null);
        const detail = err?.response?.data?.detail || err?.message || "Unknown error";
        toast.error(`Evidence graph failed to load: ${detail}`);
      });
    return () => ac.abort();
  }, [exceptionId]);

  const filtered = useMemo(() => {
    const q = query.toLowerCase();
    return exceptions.filter(
      (e) =>
        !q ||
        e.title.toLowerCase().includes(q) ||
        e.control_code.toLowerCase().includes(q) ||
        (e.entity && e.entity.toLowerCase().includes(q))
    );
  }, [exceptions, query]);

  const canLoadMore = totalCount != null && nextOffset < totalCount;

  return (
    <PageShell maxWidth="max-w-[1800px]">
      <div data-testid="evidence-explorer">
        <PageHeader
          kicker="INVESTIGATION"
          title="Evidence explorer"
          subtitle="Follow the record chain behind exceptions, drill into transactions and access events, and export defensible evidence."
        />

        <MastersFilterStrip className="mb-4" />

        <InsightPanel section="evidence" title="Evidence · AI Insights" />

        {exceptionId ? (
          <DrillContextBar
            crumbs={[
              { label: "App", to: "/app" },
              { label: "Evidence", to: "/app/evidence" },
              { label: `Exception ${exceptionId.slice(0, 12)}…` },
            ]}
          />
        ) : null}

        <div className="grid min-h-[600px] grid-cols-1 gap-4 lg:grid-cols-4">
          {/* Left: Exception picker */}
          <SectionCard className="lg:col-span-1" kicker="EXCEPTIONS" title="Pick an exception" bodyClassName="p-0">
            <div className="border-b border-zinc-200 p-4 dark:border-zinc-800">
              <div className="relative">
                <MagnifyingGlass size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <input
                  data-testid="evidence-search"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search exceptions…"
                  className="h-10 w-full rounded-sm border border-zinc-300 bg-white pl-9 pr-3 text-sm text-foreground placeholder:text-zinc-400 outline-none focus:border-primary focus:ring-1 focus:ring-primary dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100 dark:placeholder:text-zinc-500"
                />
              </div>
              {totalCount != null && (
                <div className="crt-num mt-2 text-[10px] uppercase tracking-wider text-muted-foreground">
                  Loaded {exceptions.length} of {totalCount}
                </div>
              )}
            </div>
            <div className="max-h-[640px] flex-1 divide-y divide-zinc-200 overflow-y-auto dark:divide-zinc-800">
              {filtered.slice(0, 80).map((e) => (
                <button
                  key={e.id}
                  type="button"
                  onClick={() => nav(`/app/evidence/${encodeURIComponent(e.id)}`)}
                  data-testid={`evidence-pick-${e.id}`}
                  className={clsx(
                    "w-full p-4 text-left transition-colors",
                    exceptionId === e.id
                      ? "bg-zinc-100 ring-1 ring-inset ring-primary/25 dark:bg-zinc-900/80 dark:ring-primary/35"
                      : "hover:bg-zinc-50 dark:hover:bg-zinc-900/50"
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium text-zinc-900 dark:text-zinc-50">{e.title}</div>
                      <div className="crt-num mt-0.5 text-[10px] text-zinc-600 dark:text-zinc-400">
                        {e.control_code} · {e.entity}
                        {e.department_id || e.cost_center_id ? (
                          <span className="block truncate text-muted-foreground">
                            {e.department_id ? `dept ${String(e.department_id).slice(0, 8)}…` : null}
                            {e.department_id && e.cost_center_id ? " · " : null}
                            {e.cost_center_id ? `cc ${String(e.cost_center_id).slice(0, 8)}…` : null}
                          </span>
                        ) : null}
                      </div>
                    </div>
                    <SeverityBadge severity={e.severity} />
                  </div>
                  <div className="crt-num mt-1 text-[10px] tabular-nums text-zinc-700 dark:text-zinc-300">
                    {fmtUSD(e.financial_exposure)}
                  </div>
                </button>
              ))}
            </div>
            {canLoadMore ? (
              <div className="border-t border-zinc-200 p-3 dark:border-zinc-800">
                <button
                  type="button"
                  data-testid="evidence-load-more"
                  disabled={listLoading}
                  onClick={() => loadMore()}
                  className="crt-num w-full rounded-sm border border-zinc-300 py-2 text-xs uppercase tracking-wider text-foreground transition-colors hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-600 dark:hover:bg-zinc-900/60"
                >
                  {listLoading ? "Loading…" : "Load more"}
                </button>
              </div>
            ) : null}
          </SectionCard>

          {/* Right: Graph view */}
          <SectionCard
            className="flex flex-col lg:col-span-3"
            kicker="EVIDENCE"
            title="Graph & table"
            right={
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setView("graph")}
                  data-testid="view-graph-btn"
                  className={clsx(
                    "crt-num flex h-10 items-center gap-1 rounded-sm px-4 text-xs uppercase tracking-wider transition-colors",
                    view === "graph"
                      ? "border border-primary bg-primary text-white"
                      : "border border-zinc-300 bg-white text-zinc-600 hover:bg-zinc-50 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800"
                  )}
                >
                  <GraphIcon size={12} /> Graph
                </button>
                <button
                  type="button"
                  onClick={() => setView("table")}
                  data-testid="view-table-btn"
                  className={clsx(
                    "crt-num flex h-10 items-center gap-1 rounded-sm px-4 text-xs uppercase tracking-wider transition-colors",
                    view === "table"
                      ? "border border-primary bg-primary text-white"
                      : "border border-zinc-300 bg-white text-zinc-600 hover:bg-zinc-50 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800"
                  )}
                >
                  <TableIcon size={12} /> Table
                </button>
              </div>
            }
            bodyClassName="p-0"
          >
            <div className="flex items-center justify-between border-b border-zinc-200 px-5 py-3 dark:border-zinc-800">
              <div className="text-sm text-foreground">
                {graph ? `${graph.nodes.length} nodes · ${graph.edges.length} edges` : "—"}
              </div>
              <div className="crt-num text-[10px] uppercase tracking-wider text-muted-foreground">
                {exceptionId ? `exception: ${exceptionId.slice(0, 10)}…` : "select an exception"}
              </div>
            </div>
            <div className="relative overflow-auto p-6">
              {graph?.governance && (graph.governance.worm || graph.governance.legal_hold) && (
                <div className="crt-num mb-4 flex flex-wrap gap-2 text-xs">
                  {graph.governance.worm && (
                    <span className="rounded-sm border border-zinc-200 bg-amber-50 px-3 py-2 uppercase text-amber-900 dark:border-zinc-700 dark:bg-amber-950/40 dark:text-amber-200">
                      WORM / finalized evidence
                    </span>
                  )}
                  {graph.governance.legal_hold && (
                    <span className="rounded-sm border border-zinc-200 bg-blue-50 px-3 py-2 uppercase text-blue-900 dark:border-zinc-700 dark:bg-blue-950/40 dark:text-blue-200">
                      Legal hold
                    </span>
                  )}
                </div>
              )}
              {graph &&
                (view === "graph" ? (
                  <GraphView key={exceptionId} graph={graph} />
                ) : (
                  <TableView key={exceptionId} graph={graph} exceptionId={exceptionId} />
                ))}
            </div>
          </SectionCard>
        </div>
      </div>
    </PageShell>
  );
}

function GraphView({ graph }) {
  const nav = useNavigate();
  // Radial layout: exception in middle, others around
  const nodes = graph.nodes;
  const centerNode = nodes.find((n) => n.type === "exception") || nodes[0];
  const others = nodes.filter((n) => n.id !== centerNode.id);
  const W = 800,
    H = 520,
    cx = W / 2,
    cy = H / 2;
  const positions = { [centerNode.id]: { x: cx, y: cy } };
  others.forEach((n, i) => {
    const angle = (i / others.length) * Math.PI * 2 - Math.PI / 2;
    const r = 200;
    positions[n.id] = { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
  });

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="mx-auto w-full max-w-5xl" data-testid="evidence-svg">
      {/* Edges */}
      {graph.edges.map((e, i) => {
        const a = positions[e.source],
          b = positions[e.target];
        if (!a || !b) return null;
        const mx = (a.x + b.x) / 2,
          my = (a.y + b.y) / 2;
        return (
          <g key={`${e.source}-${e.target}-${e.relation}-${i}`}>
            <line
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              className="stroke-zinc-300 dark:stroke-zinc-600"
              strokeWidth="1"
            />
            <text
              x={mx}
              y={my - 4}
              className="fill-zinc-500 dark:fill-zinc-400"
              fontSize="9"
              fontFamily="JetBrains Mono, ui-monospace, monospace"
              textAnchor="middle"
            >
              {e.relation}
            </text>
          </g>
        );
      })}
      {/* Nodes */}
      {nodes.map((n) => {
        const p = positions[n.id];
        if (!p) return null;
        const stroke = NODE_STROKE[n.type] || "#71717a";
        const path = graphNodeDrillPath(n);
        const onDrill = (e) => {
          if (!path) return;
          e.preventDefault();
          e.stopPropagation();
          nav(path);
        };
        return (
          <g
            key={n.id}
            transform={`translate(${p.x}, ${p.y})`}
            style={{ cursor: path ? "pointer" : "default" }}
            data-testid={`graph-node-${n.type}-${n.id.slice(0, 12)}`}
          >
            {/* Hit target on rect; text uses pointer-events:none so label clicks still drill */}
            <rect
              x="-80"
              y="-28"
              width="160"
              height="56"
              className="fill-white dark:fill-zinc-900"
              stroke={stroke}
              strokeWidth="1.5"
              onClick={onDrill}
              onKeyDown={(e) => {
                if (!path) return;
                if (e.key === "Enter" || e.key === " ") {
                  onDrill(e);
                }
              }}
              role={path ? "button" : undefined}
              tabIndex={path ? 0 : undefined}
            />
            <text
              x="0"
              y="-10"
              className="fill-zinc-500 dark:fill-zinc-400"
              fontSize="9"
              fontFamily="JetBrains Mono, ui-monospace, monospace"
              textAnchor="middle"
              style={{ textTransform: "uppercase", letterSpacing: "0.1em", pointerEvents: "none" }}
            >
              {n.type}
            </text>
            <text
              x="0"
              y="8"
              className="fill-zinc-900 dark:fill-zinc-100"
              fontSize="11"
              fontFamily="IBM Plex Sans, system-ui, sans-serif"
              textAnchor="middle"
              style={{ pointerEvents: "none" }}
            >
              {truncate(n.label, 22)}
            </text>
            {n.subtitle ? (
              <text
                x="0"
                y="22"
                className="fill-zinc-500 dark:fill-zinc-400"
                fontSize="9"
                fontFamily="IBM Plex Sans, system-ui, sans-serif"
                textAnchor="middle"
                style={{ pointerEvents: "none" }}
              >
                {truncate(n.subtitle, 26)}
              </text>
            ) : null}
          </g>
        );
      })}
    </svg>
  );
}

const truncate = (s, n) => (s && s.length > n ? s.slice(0, n - 1) + "…" : s);

function TableView({ graph, exceptionId }) {
  const nav = useNavigate();
  return (
    <div className="space-y-6">
      {exceptionId ? (
        <DrillContextBar
          crumbs={[
            { label: "App", to: "/app" },
            { label: "Evidence", to: "/app/evidence" },
            { label: "Graph table" },
          ]}
        />
      ) : null}
      <div>
        <h4 className="crt-num mb-2 text-[10px] uppercase tracking-[0.15em] text-muted-foreground">Nodes ({graph.nodes.length})</h4>
        <DataTable maxHeightClassName="max-h-[45vh]" testId="evidence-graph-nodes-table">
          <DataTableHead>
            <tr>
              <DataTableTh>Type</DataTableTh>
              <DataTableTh>Label</DataTableTh>
              <DataTableTh>Subtitle</DataTableTh>
            </tr>
          </DataTableHead>
          <DataTableBody>
            {graph.nodes.map((n) => {
              const path = graphNodeDrillPath(n);
              return (
                <DataTableRow
                  key={n.id}
                  onClick={() => path && nav(path)}
                  className={path ? "cursor-pointer" : ""}
                  testId={`evidence-node-row-${n.type}`}
                >
                  <DataTableTd className="crt-num text-xs uppercase" style={{ color: NODE_STROKE[n.type] || "#71717a" }}>
                    {n.type}
                  </DataTableTd>
                  <DataTableTd className="text-foreground">
                    {n.label}
                    {path ? <span className="crt-num ml-2 text-[9px] text-primary">open →</span> : null}
                  </DataTableTd>
                  <DataTableTd className="text-xs text-zinc-600 dark:text-zinc-400">{n.subtitle || "—"}</DataTableTd>
                </DataTableRow>
              );
            })}
          </DataTableBody>
        </DataTable>
      </div>
      <div>
        <h4 className="crt-num mb-2 text-[10px] uppercase tracking-[0.15em] text-muted-foreground">Edges ({graph.edges.length})</h4>
        <DataTable maxHeightClassName="max-h-[45vh]" testId="evidence-graph-edges-table">
          <DataTableHead>
            <tr>
              <DataTableTh>Source</DataTableTh>
              <DataTableTh>Relation</DataTableTh>
              <DataTableTh>Target</DataTableTh>
            </tr>
          </DataTableHead>
          <DataTableBody>
            {graph.edges.map((e, i) => (
              <DataTableRow key={i}>
                <DataTableTd className="crt-num text-xs text-zinc-800 dark:text-zinc-200">{e.source.slice(0, 12)}</DataTableTd>
                <DataTableTd className="crt-num text-xs text-primary">{e.relation}</DataTableTd>
                <DataTableTd className="crt-num text-xs text-zinc-800 dark:text-zinc-200">{e.target.slice(0, 12)}</DataTableTd>
              </DataTableRow>
            ))}
          </DataTableBody>
        </DataTable>
      </div>
    </div>
  );
}
