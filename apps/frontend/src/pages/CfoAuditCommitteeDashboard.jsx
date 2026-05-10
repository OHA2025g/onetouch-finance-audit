import React, { useEffect, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";

const DEMO = "ENG-DEMO-IN-2025";

export default function CfoAuditCommitteeDashboard() {
  const dashboardParams = useDashboardFilterParams();
  const [params, setParams] = useSearchParams();
  const eid = params.get("engagement_id") || DEMO;
  const [engagements, setEngagements] = useState([]);
  const [exec, setExec] = useState(null);
  const [pack, setPack] = useState(null);
  const [loading, setLoading] = useState(true);
  const [listErr, setListErr] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await http.get("/audit-engagements", { params: dashboardParams });
        setEngagements(Array.isArray(data) ? data : []);
      } catch {
        setListErr(true);
      }
    })();
  }, [dashboardParams]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const [a, b] = await Promise.all([
          http.get(`/audit-engagements/${encodeURIComponent(eid)}/executive-summary`, { params: dashboardParams }),
          http.get(`/audit-engagements/${encodeURIComponent(eid)}/audit-committee-pack`, { params: dashboardParams }),
        ]);
        if (!cancelled) {
          setExec(a.data);
          setPack(b.data);
        }
      } catch {
        if (!cancelled) {
          toast.error("Could not load executive pack");
          setExec(null);
          setPack(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [eid, dashboardParams]);

  return (
    <PageShell maxWidth="max-w-[1200px]">
      <PageHeader
        kicker="CFO · AUDIT COMMITTEE"
        title="Executive audit view"
        subtitle="Continuous assurance, compliance snapshot, and committee pack — engagement-scoped."
        right={
          <div className="flex flex-wrap justify-end gap-2">
            <Link to="/app/cfo" className="crt-num text-xs uppercase tracking-wider text-primary hover:underline">
              CFO cockpit
            </Link>
            <Link
              to={`/app/executive-review?engagement_id=${encodeURIComponent(eid)}`}
              className="crt-num rounded-sm border border-zinc-300 bg-white px-2 py-1 text-xs uppercase tracking-wider text-zinc-600 transition-colors hover:bg-zinc-50 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
            >
              Full executive hub
            </Link>
          </div>
        }
      />

      <div className="mb-6 flex flex-wrap items-center gap-3">
        <label className="crt-overline text-muted-foreground">Engagement</label>
        <select
          value={eid}
          onChange={(ev) => {
            const n = new URLSearchParams(params);
            n.set("engagement_id", ev.target.value);
            setParams(n, { replace: true });
          }}
          className="crt-num min-w-[240px] rounded-sm border border-zinc-300 bg-white px-3 py-2 text-sm text-foreground outline-none focus:border-primary focus:ring-1 focus:ring-primary dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100"
        >
          {!listErr && engagements.every((x) => x.engagement_id !== eid) ? <option value={eid}>{eid}</option> : null}
          {engagements.map((en) => (
            <option key={en.engagement_id} value={en.engagement_id}>{en.engagement_id} — {en.entity_name}</option>
          ))}
          {listErr ? <option value={DEMO}>{DEMO} (fallback)</option> : null}
        </select>
      </div>

      {loading ? <div className="crt-num py-6 text-xs text-muted-foreground">Loading…</div> : null}

      {!loading && exec ? (
        <SectionCard kicker="SUMMARY" title={exec.headline} bodyClassName="p-6">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {exec.scores && Object.entries(exec.scores).filter(([k]) => k.endsWith("_score") || k === "continuous_assurance_score").map(([k, v]) => (
              <div key={k} className="crt-num rounded-sm border border-zinc-200 bg-zinc-50/50 p-3 text-xs dark:border-zinc-800 dark:bg-zinc-900/30">
                <div className="text-muted-foreground">{k.replace(/_/g, " ")}</div>
                <div className="mt-1 font-display text-xl text-foreground">{String(v)}</div>
              </div>
            ))}
          </div>
        </SectionCard>
      ) : null}

      {!loading && !exec ? (
        <SectionCard kicker="EMPTY" title="No executive summary" bodyClassName="p-6 text-sm text-muted-foreground">
          Select a seeded engagement (e.g. {DEMO}) or create one in Audit Planning.
        </SectionCard>
      ) : null}

      {!loading && pack ? (
        <SectionCard kicker="PACK" title="Audit committee pack (preview)" bodyClassName="p-6 mt-4 space-y-4">
          <div className="text-sm text-muted-foreground">
            Top risks: {(pack.top_risks || []).map((r) => r.risk_title || r.title).join(" · ") || "—"}
          </div>
          <div className="text-sm text-muted-foreground">Open cases (sample): {(pack.open_cases || []).length}</div>
          {pack.compliance_snapshot ? (
            <div className="crt-num rounded-sm border border-zinc-200 bg-zinc-50/80 p-3 text-xs text-foreground dark:border-zinc-800 dark:bg-zinc-900/40">
              Compliance: {JSON.stringify(pack.compliance_snapshot)}
            </div>
          ) : null}
          <p className="crt-num text-xs text-muted-foreground">
            CFO cockpit PDF/DOCX exports remain available; this view adds JSON pack from the CA engine.
          </p>
          <details className="text-sm">
            <summary className="crt-num cursor-pointer text-xs uppercase text-primary">Raw pack JSON</summary>
            <pre className="crt-num mt-2 max-h-[40vh] overflow-x-auto whitespace-pre-wrap rounded-sm border border-zinc-200 bg-zinc-950 p-3 text-xs text-zinc-100 dark:border-zinc-800">
              {JSON.stringify(pack, null, 2)}
            </pre>
          </details>
        </SectionCard>
      ) : null}

      {!loading && !pack ? (
        <SectionCard kicker="EMPTY" title="No committee pack" bodyClassName="mt-4 p-6 text-sm text-muted-foreground">
          Pack loads with the engagement — try {DEMO} after seeding.
        </SectionCard>
      ) : null}
    </PageShell>
  );
}
