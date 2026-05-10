import React, { useEffect, useMemo, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";

const DEMO = "ENG-DEMO-IN-2025";

export default function CaCommandCenter() {
  const dashboardParams = useDashboardFilterParams();
  const [params] = useSearchParams();
  const eid = params.get("engagement_id") || DEMO;
  const [dash, setDash] = useState(null);
  const [fallbackTiles, setFallbackTiles] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const execLink = useMemo(
    () => `/app/executive-review?engagement_id=${encodeURIComponent(eid)}`,
    [eid]
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const { data } = await http.get(`/audit-engagements/${encodeURIComponent(eid)}/ca-dashboard`, { params: dashboardParams });
        if (!cancelled) setDash(data);
      } catch {
        try {
          const { data } = await http.get(`/audit-engagements/${encodeURIComponent(eid)}/ca-command-center`, { params: dashboardParams });
          if (!cancelled) {
            setDash(null);
            setFallbackTiles(data);
          }
        } catch {
          if (!cancelled) {
            setError("Could not load dashboard — check engagement id or sign in.");
            toast.error("Load failed");
          }
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [eid, dashboardParams]);

  const tiles = dash?.tiles || fallbackTiles?.tiles;
  const scores = dash?.scores;

  return (
    <PageShell maxWidth="max-w-[1200px]">
      <PageHeader
        kicker="CA · COMMAND CENTER"
        title="Engagement oversight"
        subtitle={`Engagement ${eid}. Aggregated tiles, continuous assurance, integration map, and CFO advisory — pass ?engagement_id=`}
        right={
          <div className="flex flex-wrap gap-2 justify-end">
            <Link to="/app/audit-planning" className="text-xs font-mono uppercase text-[#0A84FF]">All engagements</Link>
            <Link to={`/app/audit-planning/engagements/${encodeURIComponent(eid)}`} className="text-xs font-mono uppercase text-[#0A84FF] hover:underline">Engagement hub</Link>
            <Link
              to={execLink}
              className="rounded-sm border border-zinc-300 bg-zinc-100 px-2 py-1 text-xs font-mono uppercase text-zinc-800 transition-colors hover:bg-zinc-200 dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100 dark:hover:bg-zinc-700"
            >
              Executive review
            </Link>
            <Link to="/app/evidence" className="text-xs font-mono uppercase text-[#0A84FF] hover:underline">Evidence</Link>
          </div>
        }
      />

      {loading ? (
        <div className="font-mono text-xs text-[#737373] uppercase tracking-wider py-8">Loading command center…</div>
      ) : null}

      {error && !loading ? (
        <SectionCard kicker="ERROR" title="Unable to load" bodyClassName="p-6 text-sm text-red-600 dark:text-red-300">
          {error}
        </SectionCard>
      ) : null}

      {!loading && !error && !tiles ? (
        <SectionCard kicker="EMPTY" title="No tile data" bodyClassName="p-6 text-sm text-[#737373]">
          No engagement aggregate returned. Open Audit Planning and pick a valid engagement id.
        </SectionCard>
      ) : null}

      {tiles ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          {Object.entries(tiles).map(([k, v]) => (
            <div
              key={k}
              className="rounded-xl border border-zinc-200 bg-zinc-50/90 p-4 dark:border-zinc-700 dark:bg-zinc-900/50"
            >
              <div className="font-mono text-[10px] uppercase text-muted-foreground">{k.replace(/_/g, " ")}</div>
              <div className="mt-1 text-2xl text-foreground">{v}</div>
            </div>
          ))}
        </div>
      ) : null}

      {scores ? (
        <SectionCard kicker="SCORES" title="Continuous assurance" bodyClassName="p-6">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 font-mono text-xs">
            {Object.entries(scores).filter(([k]) => k.endsWith("_score") || k === "continuous_assurance_score").map(([k, v]) => (
              <div key={k} className="rounded-sm border border-zinc-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-950/40">
                <span className="text-muted-foreground">{k.replace(/_/g, " ")}</span>
                <div className="text-lg text-foreground">{String(v)}</div>
              </div>
            ))}
          </div>
        </SectionCard>
      ) : null}

      {dash?.integration?.counts ? (
        <SectionCard kicker="INTEGRATION" title="Cross-module chain (counts)" bodyClassName="mt-4 p-6 text-sm text-muted-foreground">
          <p className="mb-3 text-foreground">{dash.integration.narrative}</p>
          <pre className="overflow-x-auto rounded-md border border-zinc-200 bg-zinc-50 p-3 font-mono text-xs text-foreground dark:border-zinc-800 dark:bg-zinc-950">
            {JSON.stringify(dash.integration.counts, null, 2)}
          </pre>
        </SectionCard>
      ) : null}

      {dash?.advisory?.key_risks_summary?.length ? (
        <SectionCard kicker="ADVISORY" title="Key risks (CFO language)" bodyClassName="p-6 mt-4">
          <ul className="list-disc space-y-2 pl-5 text-sm text-foreground">
            {dash.advisory.key_risks_summary.slice(0, 6).map((x, i) => (
              <li key={i}>{x}</li>
            ))}
          </ul>
        </SectionCard>
      ) : null}

      {dash?.workflow_steps?.length ? (
        <SectionCard kicker="WORKFLOW" title="Statutory audit path" bodyClassName="p-6 mt-4">
          <ol className="space-y-2 text-sm">
            {dash.workflow_steps.map((s) => (
              <li key={s.phase} className="flex flex-wrap gap-2 items-baseline">
                <span className="font-mono text-[#0A84FF] w-40 shrink-0">{s.phase}</span>
                <Link to={s.path} className="text-muted-foreground underline-offset-2 hover:text-foreground hover:underline">
                  {s.note}
                </Link>
              </li>
            ))}
          </ol>
        </SectionCard>
      ) : null}

      <SectionCard kicker="AI ADVISORY" title="Deeper narrative and copilot" bodyClassName="p-6 mt-4">
        <p className="mb-3 text-sm text-muted-foreground">
          Use the Executive review hub for full advisory sections, committee pack JSON, and management letter drafts.
        </p>
        <div className="flex flex-wrap gap-2">
          <Link to={execLink} className="text-xs font-mono uppercase text-[#0A84FF] hover:underline">Open executive review →</Link>
          <Link to="/app/copilot" className="text-xs font-mono uppercase text-[#0A84FF] hover:underline">AI Copilot →</Link>
        </div>
      </SectionCard>
    </PageShell>
  );
}
