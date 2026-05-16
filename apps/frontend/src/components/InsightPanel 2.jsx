import React, { useEffect, useState, useCallback, useMemo } from "react";
import { Link } from "react-router-dom";
import { http } from "../lib/api";
import { useMastersFilters } from "../lib/MastersFilterContext";
import { buildDashboardFilterParams } from "../lib/mastersDashboardParams";
import { pathForRelatedType } from "../lib/drillPaths";
import {
  Sparkle,
  ArrowsClockwise,
  Lightning,
  CheckSquare,
  Warning,
  CaretDown,
  CaretUp,
} from "@phosphor-icons/react";

const SEV_COLOR = {
  critical: "hsl(var(--destructive))",
  warning: "hsl(var(--chart-3))",
  info: "hsl(var(--chart-1))",
};
const IMPACT_COLOR = {
  high: "hsl(var(--destructive))",
  medium: "hsl(var(--chart-3))",
  low: "hsl(var(--chart-4))",
};
const PRIORITY_COLOR = {
  P1: "hsl(var(--destructive))",
  P2: "hsl(var(--chart-3))",
  P3: "hsl(var(--muted-foreground))",
};

export default function InsightPanel({ section, title = "AI Insights" }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(null);
  const [collapsed, setCollapsed] = useState(false);
  const { entityCode, periodYm, periodExplicit, departmentId, costCenterId } = useMastersFilters();
  const masterParams = useMemo(
    () =>
      buildDashboardFilterParams({
        entityCode,
        periodYm,
        periodExplicit,
        departmentId,
        costCenterId,
      }),
    [entityCode, periodYm, periodExplicit, departmentId, costCenterId]
  );

  const load = useCallback(
    async (refresh = false) => {
      setLoading(true);
      setErr(null);
      try {
        const params = { ...masterParams };
        if (refresh) params.refresh = true;
        const r = await http.get(`/insights/${section}`, { params });
        setData(r.data);
      } catch (e) {
        setErr(e?.response?.data?.detail || "Failed to load insights");
      } finally {
        setLoading(false);
      }
    },
    [section, masterParams]
  );

  useEffect(() => {
    load(false);
  }, [load]);

  const src = data?.source;
  const isLLM = typeof src === "string" && src.includes("gemini");
  const ageMin = data?.cache_age_sec ? Math.floor(data.cache_age_sec / 60) : 0;

  return (
    <section data-testid={`insight-panel-${section}`} className="crt-card mb-6 overflow-hidden">
      <div className="flex items-center justify-between border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-sm border border-zinc-200 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900/80">
            <Sparkle size={14} weight="fill" className="text-[hsl(var(--chart-1))]" />
          </div>
          <div className="min-w-0">
            <h3 className="font-display text-base font-semibold tracking-tight text-foreground">{title}</h3>
            <div className="crt-num text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
              {data?.section_label || section} ·{" "}
              {isLLM ? (
                <span className="text-[hsl(var(--primary))]">gemini · flash</span>
              ) : data?.source === "heuristic" ? (
                <span className="text-[hsl(var(--chart-3))]">heuristic · llm paused</span>
              ) : (
                <span>loading…</span>
              )}
              {data?.cached && <span className="text-muted-foreground/80"> · cached {ageMin}m</span>}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            data-testid={`insight-refresh-${section}`}
            onClick={() => load(true)}
            disabled={loading}
            title="Regenerate insights"
            className="crt-card flex h-8 items-center gap-1.5 px-3 font-mono text-[10px] uppercase tracking-wider text-muted-foreground transition-colors hover:text-foreground disabled:opacity-40"
          >
            <ArrowsClockwise size={12} className={loading ? "animate-spin" : ""} />
            <span>{loading ? "thinking…" : "refresh"}</span>
          </button>
          <button
            onClick={() => setCollapsed((c) => !c)}
            title={collapsed ? "Expand" : "Collapse"}
            className="crt-card flex h-8 w-8 items-center justify-center text-muted-foreground transition-colors hover:text-foreground"
            data-testid={`insight-collapse-${section}`}
          >
            {collapsed ? <CaretDown size={12} /> : <CaretUp size={12} />}
          </button>
        </div>
      </div>

      {!collapsed && (
        <div className="grid grid-cols-1 gap-4 p-4 lg:grid-cols-3">
          <Column
            icon={<Lightning size={12} weight="fill" className="text-[hsl(var(--chart-3))]" />}
            title="Insights"
            count={data?.insights?.length || 0}
          >
            {err && <EmptyState text={err} />}
            {!err && loading && !data && <Skeleton n={3} />}
            {data?.insights?.map((ins, i) => (
              <InsightCard key={i} item={ins} />
            ))}
            {!err && data && (data.insights || []).length === 0 && <EmptyState text="No insights yet." />}
          </Column>

          <Column
            icon={<Sparkle size={12} weight="fill" className="text-[hsl(var(--chart-1))]" />}
            title="Recommendations"
            count={data?.recommendations?.length || 0}
          >
            {!err && loading && !data && <Skeleton n={3} />}
            {data?.recommendations?.map((r, i) => (
              <RecCard key={i} item={r} />
            ))}
            {!err && data && (data.recommendations || []).length === 0 && <EmptyState text="No recommendations." />}
          </Column>

          <Column
            icon={<CheckSquare size={12} weight="fill" className="text-[hsl(var(--chart-4))]" />}
            title="Action Items"
            count={data?.action_items?.length || 0}
          >
            {!err && loading && !data && <Skeleton n={3} />}
            {data?.action_items?.map((a, i) => (
              <ActionCard key={i} item={a} />
            ))}
            {!err && data && (data.action_items || []).length === 0 && <EmptyState text="No actions required." />}
          </Column>
        </div>
      )}
    </section>
  );
}

function Column({ icon, title, count, children }) {
  return (
    <div className="flex min-w-0 flex-col">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          {icon}
          <h4 className="crt-overline text-muted-foreground">{title}</h4>
        </div>
        <span className="crt-num text-[10px] uppercase tracking-wider text-muted-foreground">{count}</span>
      </div>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function InsightCard({ item }) {
  const color = SEV_COLOR[item.severity] || SEV_COLOR.info;
  return (
    <div className="crt-card rounded-sm border-l-2 p-3" style={{ borderLeftColor: color }}>
      <div className="flex items-start justify-between gap-2">
        <div className="text-sm leading-snug text-foreground">{item.title}</div>
        {item.metric && (
          <div className="crt-num whitespace-nowrap text-xs font-medium tabular-nums text-foreground">{item.metric}</div>
        )}
      </div>
      {item.detail && (
        <div className="crt-num mt-1.5 text-[11px] leading-relaxed text-muted-foreground">{item.detail}</div>
      )}
      {item.severity && (
        <div className="crt-num mt-2 text-[9px] uppercase tracking-wider" style={{ color }}>
          {item.severity}
        </div>
      )}
    </div>
  );
}

function RecCard({ item }) {
  const color = IMPACT_COLOR[item.impact] || IMPACT_COLOR.medium;
  return (
    <div className="crt-card rounded-sm p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="text-sm leading-snug text-foreground">{item.title}</div>
        <span
          className="crt-num border px-1.5 py-0.5 text-[9px] uppercase tracking-wider"
          style={{ color, borderColor: color }}
        >
          {item.impact || "med"}
        </span>
      </div>
      {item.detail && (
        <div className="crt-num mt-1.5 text-[11px] leading-relaxed text-muted-foreground">{item.detail}</div>
      )}
    </div>
  );
}

function ActionCard({ item }) {
  const color = PRIORITY_COLOR[item.priority] || PRIORITY_COLOR.P3;
  const path = pathForRelatedType(item.related_type, item.related_id);
  const Body = (
    <div className="crt-card rounded-sm p-3 transition-colors hover:bg-zinc-50/80 dark:hover:bg-zinc-800/50">
      <div className="flex items-start justify-between gap-2">
        <div className="text-sm leading-snug text-foreground">{item.title}</div>
        <span
          className="crt-num whitespace-nowrap border px-1.5 py-0.5 text-[9px] uppercase tracking-wider"
          style={{ color, borderColor: color }}
        >
          {item.priority || "P3"}
        </span>
      </div>
      <div className="crt-num mt-1.5 truncate text-[10px] text-muted-foreground">
        {item.owner_hint ? `→ ${item.owner_hint}` : "owner tba"}
        {item.related_id && (
          <span className="ml-2 text-[hsl(var(--chart-1))]">
            {item.related_type}:{String(item.related_id).slice(0, 14)}
          </span>
        )}
      </div>
    </div>
  );
  return path ? <Link to={path}>{Body}</Link> : Body;
}

function EmptyState({ text }) {
  return (
    <div className="rounded-sm border border-dashed border-zinc-300 bg-zinc-50/80 p-4 text-center dark:border-zinc-700 dark:bg-zinc-900/40">
      <Warning size={14} className="mx-auto text-muted-foreground" />
      <div className="crt-overline mt-1.5 text-muted-foreground">{text}</div>
    </div>
  );
}

function Skeleton({ n = 3 }) {
  return (
    <>
      {Array.from({ length: n }).map((_, i) => (
        <div key={i} className="crt-card animate-pulse rounded-sm p-3">
          <div className="mb-2 h-3 w-3/4 rounded-sm bg-muted" />
          <div className="mb-1 h-2 w-full rounded-sm bg-muted" />
          <div className="h-2 w-2/3 rounded-sm bg-muted" />
        </div>
      ))}
    </>
  );
}
