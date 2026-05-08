import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";

const TABS = [
  { id: "summary", label: "Executive summary" },
  { id: "assurance", label: "Continuous assurance" },
  { id: "pack", label: "Committee pack" },
  { id: "letter", label: "Management letter" },
  { id: "advisory", label: "Advisory AI" },
];

const DEMO_EID = "ENG-DEMO-IN-2025";

export default function ExecutiveReviewPage() {
  const [params, setParams] = useSearchParams();
  const eid = params.get("engagement_id") || DEMO_EID;
  const tab = params.get("tab") || "summary";
  const [engagements, setEngagements] = useState([]);
  const [loadingList, setLoadingList] = useState(true);
  const [err, setErr] = useState(null);
  const [summary, setSummary] = useState(null);
  const [assurance, setAssurance] = useState(null);
  const [pack, setPack] = useState(null);
  const [advisory, setAdvisory] = useState(null);
  const [letterText, setLetterText] = useState(null);
  const [tabLoading, setTabLoading] = useState(false);

  useEffect(() => {
    let c = false;
    (async () => {
      setLoadingList(true);
      setErr(null);
      try {
        const { data } = await http.get("/audit-engagements");
        if (!c) setEngagements(Array.isArray(data) ? data : []);
      } catch {
        if (!c) setErr("Could not load engagements");
      } finally {
        if (!c) setLoadingList(false);
      }
    })();
    return () => { c = true; };
  }, []);

  const loadTab = useCallback(async () => {
    if (!eid) return;
    setTabLoading(true);
    setErr(null);
    try {
      if (tab === "summary") {
        const { data } = await http.get(`/audit-engagements/${encodeURIComponent(eid)}/executive-summary`);
        setSummary(data);
      } else if (tab === "assurance") {
        const { data } = await http.get(`/audit-engagements/${encodeURIComponent(eid)}/continuous-assurance-score`);
        setAssurance(data);
      } else if (tab === "pack") {
        const { data } = await http.get(`/audit-engagements/${encodeURIComponent(eid)}/audit-committee-pack`);
        setPack(data);
      } else if (tab === "advisory" || tab === "letter") {
        const { data } = await http.get(`/audit-engagements/${encodeURIComponent(eid)}/advisory-insights`);
        setAdvisory(data);
        if (tab === "letter") setLetterText(null);
      }
    } catch {
      setErr("Failed to load this tab — check engagement id or login.");
      toast.error("Load failed");
    } finally {
      setTabLoading(false);
    }
  }, [eid, tab]);

  useEffect(() => {
    loadTab();
  }, [loadTab]);

  const setEngagement = (id) => {
    const n = new URLSearchParams(params);
    n.set("engagement_id", id);
    if (!n.get("tab")) n.set("tab", "summary");
    setParams(n, { replace: true });
  };

  const setTab = (id) => {
    const n = new URLSearchParams(params);
    n.set("tab", id);
    if (!n.get("engagement_id")) n.set("engagement_id", eid);
    setParams(n, { replace: true });
  };

  const genLetter = async () => {
    try {
      const { data } = await http.post(`/audit-engagements/${encodeURIComponent(eid)}/management-letter/generate`);
      setLetterText(data?.text || "");
      toast.success("Management letter generated");
    } catch {
      toast.error("Generate failed");
    }
  };

  const hub = useMemo(() => `/app/audit-planning/engagements/${encodeURIComponent(eid)}`, [eid]);

  return (
    <PageShell maxWidth="max-w-[1200px]">
      <PageHeader
        kicker="EXECUTIVE REVIEW"
        title="CFO &amp; audit committee workspace"
        subtitle="End-of-chain view: assurance scores, committee pack, management letter, and CFO-language advisory — all scoped to one statutory engagement."
        right={
          <Link to={hub} className="crt-num text-xs uppercase tracking-wider text-primary hover:underline">
            Open engagement hub
          </Link>
        }
      />

      <div className="mb-6 flex flex-wrap items-center gap-3">
        <label className="crt-overline text-muted-foreground">Engagement</label>
        <select
          value={eid}
          disabled={loadingList}
          onChange={(ev) => setEngagement(ev.target.value)}
          className="crt-num min-w-[220px] rounded-sm border border-zinc-300 bg-white px-3 py-2 text-sm text-foreground outline-none focus:border-primary focus:ring-1 focus:ring-primary disabled:opacity-50 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100"
        >
          {loadingList ? <option>Loading…</option> : null}
          {!loadingList && engagements.every((en) => en.engagement_id !== eid) ? (
            <option value={eid}>{eid} (current)</option>
          ) : null}
          {engagements.map((en) => (
            <option key={en.engagement_id} value={en.engagement_id}>
              {en.engagement_id} — {en.entity_name}
            </option>
          ))}
        </select>
      </div>

      {err ? (
        <div className="mb-4 rounded-sm border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900/40 dark:bg-red-950/30 dark:text-red-200">
          {err}
        </div>
      ) : null}

      <div className="mb-6 flex flex-wrap gap-2">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`crt-num h-9 rounded-sm border px-3 text-[10px] uppercase tracking-wider transition-colors ${
              tab === t.id
                ? "border-primary bg-primary text-white"
                : "border-zinc-300 bg-white text-zinc-600 hover:bg-zinc-50 hover:text-foreground dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tabLoading ? <div className="crt-num mb-4 text-xs text-muted-foreground">Loading…</div> : null}

      {tab === "summary" && !tabLoading ? (
        <div className="space-y-4">
          {!summary ? (
            <SectionCard kicker="EMPTY" title="No summary" bodyClassName="p-6 text-sm text-muted-foreground">
              Select a valid engagement or seed demo data.
            </SectionCard>
          ) : (
            <>
              <SectionCard kicker="HEADLINE" title={summary.headline} bodyClassName="p-6">
                <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
                  {summary.scores && Object.entries(summary.scores).filter(([k]) => k.endsWith("_score") || k === "continuous_assurance_score").map(([k, v]) => (
                    <div key={k} className="crt-num rounded-sm border border-zinc-200 bg-zinc-50/80 p-3 text-xs dark:border-zinc-800 dark:bg-zinc-900/40">
                      <div className="text-muted-foreground">{k.replace(/_/g, " ")}</div>
                      <div className="mt-1 font-display text-xl text-foreground">{String(v)}</div>
                    </div>
                  ))}
                </div>
              </SectionCard>
              {summary.integration_summary ? (
                <SectionCard kicker="INTEGRATION" title="Cross-module linkage" bodyClassName="p-6 text-sm text-zinc-700 dark:text-zinc-300">
                  <p className="mb-3">{summary.integration_summary.narrative}</p>
                  <pre className="crt-num max-h-[40vh] overflow-x-auto rounded-sm border border-zinc-200 bg-zinc-100 p-3 text-xs text-zinc-900 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-100">
                    {JSON.stringify(summary.integration_summary.counts, null, 2)}
                  </pre>
                </SectionCard>
              ) : null}
              {summary.advisory_preview ? (
                <SectionCard kicker="ADVISORY" title="CFO preview" bodyClassName="space-y-2 p-6 text-sm text-foreground">
                  <div>
                    <span className="crt-overline text-muted-foreground">Lead risk</span>
                    <div className="mt-1">{summary.advisory_preview.lead_risk || "—"}</div>
                  </div>
                  <div>
                    <span className="crt-overline text-muted-foreground">Finding</span>
                    <div className="mt-1">{summary.advisory_preview.cfo_finding || "—"}</div>
                  </div>
                </SectionCard>
              ) : null}
            </>
          )}
        </div>
      ) : null}

      {tab === "assurance" && !tabLoading && assurance ? (
        <SectionCard kicker="SCORES" title="Continuous assurance components" bodyClassName="p-6">
          <div className="grid grid-cols-1 gap-4 text-sm md:grid-cols-2">
            {(assurance.components ? Object.entries(assurance.components) : Object.entries(assurance).filter(([k]) => k.endsWith("_score"))).map(([k, v]) => (
              <div key={k} className="rounded-sm border border-zinc-200 bg-zinc-50/80 p-4 dark:border-zinc-800 dark:bg-zinc-900/40">
                <div className="crt-num text-[10px] uppercase text-muted-foreground">{k.replace(/_/g, " ")}</div>
                <div className="mt-2 font-display text-2xl text-foreground">{v}</div>
              </div>
            ))}
          </div>
          <p className="crt-num mt-4 text-xs text-muted-foreground">Overall index: {assurance.continuous_assurance_score ?? "—"}</p>
        </SectionCard>
      ) : null}

      {tab === "pack" && !tabLoading ? (
        !pack ? (
          <SectionCard kicker="EMPTY" title="No pack data" bodyClassName="p-6 text-sm text-muted-foreground">
            Try another engagement.
          </SectionCard>
        ) : (
          <div className="space-y-4">
            <SectionCard kicker="RISKS" title="Top risks (high / critical)" bodyClassName="p-6">
              <ul className="space-y-2 text-sm text-foreground">
                {(pack.top_risks || []).length === 0 ? <li className="text-muted-foreground">None flagged.</li> : null}
                {(pack.top_risks || []).map((r) => (
                  <li key={r.id}>{r.risk_title || r.title} · {r.risk_rating}</li>
                ))}
              </ul>
            </SectionCard>
            <SectionCard kicker="JSON" title="Pack preview (structured)" bodyClassName="p-6">
              <pre className="crt-num max-h-[50vh] overflow-x-auto whitespace-pre-wrap rounded-sm border border-zinc-200 bg-zinc-100 p-3 text-xs text-zinc-900 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-100">
                {JSON.stringify({ continuous_assurance: pack.continuous_assurance, compliance_snapshot: pack.compliance_snapshot, advisory: pack.advisory, open_cases: (pack.open_cases || []).slice(0, 5) }, null, 2)}
              </pre>
            </SectionCard>
          </div>
        )
      ) : null}

      {tab === "letter" && !tabLoading ? (
        <SectionCard kicker="MANAGEMENT LETTER" title="Generator" bodyClassName="space-y-4 p-6">
          <p className="text-sm text-muted-foreground">
            Persists a letter draft from open observations. Advisory tab includes a richer narrative template.
          </p>
          <button
            type="button"
            onClick={genLetter}
            className="crt-num h-10 rounded-sm border border-primary bg-primary px-4 text-xs font-medium uppercase tracking-wider text-white transition-opacity hover:opacity-90"
          >
            Generate from observations
          </button>
          {advisory?.management_letter_draft ? (
            <div>
              <div className="crt-overline mb-2 text-muted-foreground">Advisory draft (CFO tone)</div>
              <pre className="max-h-[40vh] overflow-y-auto whitespace-pre-wrap rounded-sm border border-zinc-200 bg-zinc-100 p-4 text-sm text-zinc-900 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-100">
                {advisory.management_letter_draft}
              </pre>
            </div>
          ) : null}
          {letterText ? (
            <div>
              <div className="crt-overline mb-2 text-muted-foreground">Stored generator output</div>
              <pre className="max-h-[40vh] overflow-y-auto whitespace-pre-wrap rounded-sm border border-zinc-200 bg-zinc-100 p-4 text-sm text-zinc-900 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-100">
                {letterText}
              </pre>
            </div>
          ) : null}
        </SectionCard>
      ) : null}

      {tab === "advisory" && !tabLoading && advisory ? (
        <div className="space-y-4">
          {["key_risks_summary", "control_improvements", "cost_optimization", "findings_cfo_language"].map((key) => (
            <SectionCard key={key} kicker="ADVISORY" title={key.replace(/_/g, " ")} bodyClassName="p-6">
              <ul className="list-disc space-y-2 pl-5 text-sm text-foreground">
                {(advisory[key] || []).map((line, i) => (
                  <li key={i}>{line}</li>
                ))}
              </ul>
            </SectionCard>
          ))}
        </div>
      ) : null}
    </PageShell>
  );
}
