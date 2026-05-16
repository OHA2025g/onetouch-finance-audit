import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Funnel,
  FunnelChart,
  Line,
  LineChart,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";

const TABS = [
  { id: "summary", label: "Executive summary" },
  { id: "assurance", label: "Continuous assurance" },
  { id: "pack", label: "Committee pack" },
  { id: "letter", label: "Letter & advisory" },
];

const ADVISORY_SECTIONS = [
  { key: "key_risks_summary", title: "Key risks" },
  { key: "control_improvements", title: "Control improvements" },
  { key: "cost_optimization", title: "Cost & efficiency" },
  { key: "findings_cfo_language", title: "Findings (CFO language)" },
];

const SCORE_DESCRIPTIONS = {
  audit_readiness_score: "Weighted view of risk, controls, compliance, evidence, and FS risk.",
  control_effectiveness_score: "Derived from RACM control effectiveness ratings.",
  compliance_score: "Share of compliant India checklist lines (or neutral default).",
  evidence_completeness_score: "Heuristic from working paper volume / sign-off coverage.",
  fraud_risk_score: "Inversely related to high-severity exceptions vs materiality.",
  financial_statement_risk_score: "FS validation and compliance pressure.",
  continuous_assurance_score: "Overall index for committee dashboards.",
};

function humanizeKey(k) {
  return k.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function funnelChartData(funnel) {
  if (!funnel) return [];
  const pickTotal = (block) => (block && typeof block.total === "number" ? block.total : 0);
  return [
    { name: "Risks (H/C)", value: pickTotal(funnel.risks_high_critical) },
    { name: "Open cases", value: pickTotal(funnel.open_cases) },
    { name: "Deficiencies", value: pickTotal(funnel.control_deficiencies) },
    { name: "Observations", value: pickTotal(funnel.open_observations) },
  ];
}

const FUNNEL_STAGE_FILLS = ["#4f46e5", "#6366f1", "#818cf8", "#a5b4fc"];

function radarChartData(radar) {
  if (!radar) return [];
  return Object.entries(radar).map(([k, v]) => ({
    metric: humanizeKey(k).replace(/ Score$/, ""),
    value: typeof v === "number" ? Math.min(100, Math.max(0, v)) : 0,
  }));
}

function SkeletonBlock({ className = "" }) {
  return <div className={`animate-pulse rounded-sm bg-zinc-200/80 dark:bg-zinc-800/80 ${className}`} />;
}

export default function ExecutiveReviewPage() {
  const dashboardParams = useDashboardFilterParams();
  const [params, setParams] = useSearchParams();
  const engagementIdInUrl = params.get("engagement_id");
  /** Legacy ``tab=advisory`` merges into Letter & advisory. */
  const tab =
    params.get("tab") === "advisory" ? "letter" : params.get("tab") || "summary";

  useEffect(() => {
    if (params.get("tab") !== "advisory") return;
    const n = new URLSearchParams(params);
    n.set("tab", "letter");
    setParams(n, { replace: true });
  }, [params, setParams]);
  const [engagements, setEngagements] = useState([]);
  const [crossOrg, setCrossOrg] = useState([]);
  const [loadingList, setLoadingList] = useState(true);
  const [err, setErr] = useState(null);
  const [dashboard, setDashboard] = useState(null);
  const [dashboardLoading, setDashboardLoading] = useState(false);
  const [pack, setPack] = useState(null);
  const [letterText, setLetterText] = useState(null);
  const [tabLoading, setTabLoading] = useState(false);

  const eid = engagementIdInUrl || "";

  useEffect(() => {
    let c = false;
    (async () => {
      setLoadingList(true);
      setErr(null);
      try {
        const { data } = await http.get("/audit-engagements", { params: dashboardParams });
        if (!c) setEngagements(Array.isArray(data) ? data : []);
      } catch {
        if (!c) setErr("Could not load engagements");
      } finally {
        if (!c) setLoadingList(false);
      }
    })();
    return () => {
      c = true;
    };
  }, [dashboardParams]);

  useEffect(() => {
    if (!engagements.length) {
      setCrossOrg([]);
      return;
    }
    let c = false;
    (async () => {
      try {
        const { data } = await http.get("/audit-engagements/executive-review-cross-org", {
          params: { ...dashboardParams, limit: 6, pool: 40 },
        });
        if (!c) setCrossOrg(Array.isArray(data) ? data : []);
      } catch {
        if (!c) setCrossOrg([]);
      }
    })();
    return () => {
      c = true;
    };
  }, [engagements, dashboardParams]);

  useEffect(() => {
    if (loadingList) return;
    if (!engagements.length) return;
    const first = engagements[0].engagement_id;
    if (!engagementIdInUrl) {
      const n = new URLSearchParams(params);
      n.set("engagement_id", first);
      if (!n.get("tab")) n.set("tab", "summary");
      setParams(n, { replace: true });
      return;
    }
    if (!engagements.some((en) => en.engagement_id === engagementIdInUrl)) {
      const n = new URLSearchParams(params);
      n.set("engagement_id", first);
      setParams(n, { replace: true });
    }
  }, [loadingList, engagements, engagementIdInUrl, params, setParams]);

  const loadDashboard = useCallback(async () => {
    if (!eid) {
      setDashboard(null);
      return;
    }
    setDashboardLoading(true);
    setErr(null);
    try {
      const { data } = await http.get(`/audit-engagements/${encodeURIComponent(eid)}/ca-dashboard`, {
        params: dashboardParams,
      });
      setDashboard(data);
    } catch {
      setDashboard(null);
      setErr("Failed to load executive dashboard — check engagement access or login.");
      toast.error("Dashboard load failed");
    } finally {
      setDashboardLoading(false);
    }
  }, [eid, dashboardParams]);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  const loadPack = useCallback(async () => {
    if (!eid || tab !== "pack") return;
    setTabLoading(true);
    setErr(null);
    try {
      const { data } = await http.get(`/audit-engagements/${encodeURIComponent(eid)}/audit-committee-pack`, {
        params: dashboardParams,
      });
      setPack(data);
    } catch {
      setErr("Failed to load committee pack.");
      toast.error("Pack load failed");
    } finally {
      setTabLoading(false);
    }
  }, [eid, tab, dashboardParams]);

  useEffect(() => {
    loadPack();
  }, [loadPack]);

  const setEngagement = (id) => {
    const n = new URLSearchParams(params);
    n.set("engagement_id", id);
    if (!n.get("tab")) n.set("tab", "summary");
    setParams(n, { replace: true });
  };

  const setTab = (id) => {
    const n = new URLSearchParams(params);
    n.set("tab", id);
    if (!n.get("engagement_id") && eid) n.set("engagement_id", eid);
    setParams(n, { replace: true });
  };

  const genLetter = async () => {
    try {
      const { data } = await http.post(
        `/audit-engagements/${encodeURIComponent(eid)}/management-letter/generate`,
        {},
        { params: dashboardParams },
      );
      setLetterText(data?.text || "");
      toast.success("Management letter generated");
    } catch {
      toast.error("Generate failed");
    }
  };

  const copyPageLink = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      toast.success("Link copied");
    } catch {
      toast.error("Could not copy link");
    }
  };

  const exportDashboardJson = () => {
    if (!dashboard) {
      toast.error("Nothing to export yet");
      return;
    }
    const blob = new Blob([JSON.stringify(dashboard, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `executive-review-${eid || "export"}.json`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success("Export started");
  };

  const hub = useMemo(() => `/app/audit-planning/engagements/${encodeURIComponent(eid)}`, [eid]);
  const reportStudio = useMemo(() => `/app/audit-planning/engagements/${encodeURIComponent(eid)}/report-studio`, [eid]);

  const noEngagements = !loadingList && !err && engagements.length === 0;
  const listBusy = loadingList || (!!engagements.length && !engagementIdInUrl);
  const kpis = dashboard?.executive_review_kpis;
  const scores = dashboard?.scores;
  const advisory = dashboard?.advisory;
  const engagementRow = dashboard?.engagement;
  const sparkOverall = kpis?.sparkline_series?.continuous_assurance_score || [];

  const committeePackQuery = useMemo(
    () => ({
      ...dashboardParams,
      ...(engagementRow?.entity_code ? { entity_code: engagementRow.entity_code } : {}),
    }),
    [dashboardParams, engagementRow?.entity_code],
  );

  const exportCommitteePack = useCallback(
    async (format) => {
      try {
        const resp = await http.get(`/reports/audit-committee-pack.${format}`, {
          params: committeePackQuery,
          responseType: "blob",
        });
        const blob = new Blob([resp.data]);
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `audit-committee-pack-${eid || "export"}.${format}`;
        a.click();
        URL.revokeObjectURL(url);
        toast.success(`Committee pack (${format.toUpperCase()}) downloaded`);
      } catch {
        toast.error(`Committee pack ${format} failed`);
      }
    },
    [committeePackQuery, eid],
  );

  const recordAssuranceSnapshot = useCallback(
    async (force) => {
      if (!eid) return;
      try {
        await http.post(
          `/audit-engagements/${encodeURIComponent(eid)}/assurance-snapshot`,
          { force },
          { params: dashboardParams },
        );
        toast.success(force ? "Assurance snapshot saved (forced)" : "Assurance snapshot saved");
        await loadDashboard();
      } catch {
        toast.error("Assurance snapshot failed");
      }
    },
    [eid, dashboardParams, loadDashboard],
  );

  const issueFunnelRows = useMemo(
    () => funnelChartData(kpis?.tier_b?.issue_funnel ?? kpis?.issue_funnel),
    [kpis],
  );

  const complianceLawRows = useMemo(() => {
    const by = kpis?.compliance_extended?.by_law;
    if (!by || typeof by !== "object") return [];
    return Object.entries(by).map(([law, counts]) => {
      const c = counts || {};
      const nc = Number(c.non_compliant || 0);
      const tot = Number(c.compliant || 0) + nc + Number(c.pending_evidence || 0) + Number(c.other || 0);
      const intensity = tot ? Math.min(100, Math.round((nc / tot) * 100)) : 0;
      return { law, ...c, total: tot, intensity };
    });
  }, [kpis]);

  return (
    <PageShell maxWidth="max-w-[1200px]">
      <PageHeader
        kicker="EXECUTIVE REVIEW"
        title="CFO & audit committee workspace"
        subtitle="Assurance snapshots, committee thresholds, portfolio comparisons, and CFO-language advisory — fed by the CA dashboard bundle."
        right={
          eid ? (
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
              <button
                type="button"
                onClick={copyPageLink}
                className="crt-num text-xs uppercase tracking-wider text-primary underline-offset-2 hover:underline"
              >
                Copy link
              </button>
              <button
                type="button"
                onClick={exportDashboardJson}
                disabled={!dashboard}
                className="crt-num text-xs uppercase tracking-wider text-primary underline-offset-2 hover:underline disabled:opacity-40"
              >
                Export JSON
              </button>
              <button
                type="button"
                onClick={() => exportCommitteePack("pdf")}
                className="crt-num text-xs uppercase tracking-wider text-primary underline-offset-2 hover:underline"
              >
                PDF pack
              </button>
              <button
                type="button"
                onClick={() => exportCommitteePack("xlsx")}
                className="crt-num text-xs uppercase tracking-wider text-primary underline-offset-2 hover:underline"
              >
                XLSX pack
              </button>
              <button
                type="button"
                onClick={() => recordAssuranceSnapshot(false)}
                disabled={dashboardLoading}
                className="crt-num text-xs uppercase tracking-wider text-primary underline-offset-2 hover:underline disabled:opacity-40"
              >
                Record snapshot
              </button>
              <button
                type="button"
                onClick={() => recordAssuranceSnapshot(true)}
                disabled={dashboardLoading}
                className="crt-num text-xs uppercase tracking-wider text-amber-800 underline-offset-2 hover:underline dark:text-amber-400 disabled:opacity-40"
              >
                Force snapshot
              </button>
              <Link to={hub} className="crt-num text-xs uppercase tracking-wider text-primary hover:underline">
                Engagement hub
              </Link>
            </div>
          ) : null
        }
      />

      {eid && (engagementRow || dashboardLoading) ? (
        <div className="mb-6 rounded-sm border border-zinc-200 bg-zinc-50/90 px-4 py-3 text-sm dark:border-zinc-700 dark:bg-zinc-900/50">
          {dashboardLoading ? (
            <SkeletonBlock className="h-4 w-2/3 max-w-md" />
          ) : (
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <div>
                <span className="crt-overline text-muted-foreground">Selected engagement</span>
                <div className="mt-1 font-medium text-foreground">
                  {engagementRow?.entity_name || "—"} · FY {engagementRow?.financial_year || "—"}
                  <span className="crt-num ml-2 text-muted-foreground">{eid}</span>
                </div>
              </div>
              {kpis?.committee_threshold ? (
                <div className="crt-num text-xs">
                  Committee assurance floor {kpis.committee_threshold.continuous_assurance_floor}
                  {kpis.committee_threshold.below_floor ? (
                    <span className="ml-2 font-medium text-amber-700 dark:text-amber-400">Below threshold</span>
                  ) : (
                    <span className="ml-2 text-emerald-700 dark:text-emerald-400">At or above</span>
                  )}
                </div>
              ) : null}
            </div>
          )}
        </div>
      ) : null}

      {!noEngagements && crossOrg.length > 0 ? (
        <SectionCard
          kicker="PORTFOLIO"
          title="Cross-org spotlight (lowest assurance first)"
          bodyClassName="overflow-x-auto p-4"
        >
          <table className="crt-num w-full min-w-[520px] border-collapse text-left text-xs">
            <thead>
              <tr className="border-b border-zinc-200 text-muted-foreground dark:border-zinc-700">
                <th className="py-2 pr-3 font-medium">Engagement</th>
                <th className="py-2 pr-3 font-medium">Entity</th>
                <th className="py-2 pr-3 font-medium">FY</th>
                <th className="py-2 pr-3 font-medium">Assurance</th>
                <th className="py-2 font-medium">Open critical</th>
              </tr>
            </thead>
            <tbody>
              {crossOrg.map((row) => (
                <tr key={row.engagement_id} className="border-b border-zinc-100 dark:border-zinc-800">
                  <td className="py-2 pr-3">
                    <button
                      type="button"
                      className="text-left text-primary underline-offset-2 hover:underline"
                      onClick={() => setEngagement(row.engagement_id)}
                    >
                      {row.engagement_id}
                    </button>
                  </td>
                  <td className="py-2 pr-3">{row.entity_name || "—"}</td>
                  <td className="py-2 pr-3">{row.financial_year || "—"}</td>
                  <td className="py-2 pr-3">{row.continuous_assurance_score ?? "—"}</td>
                  <td className="py-2">{row.open_critical_cases ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </SectionCard>
      ) : null}

      <div className="mb-6 flex flex-wrap items-center gap-3">
        <label className="crt-overline text-muted-foreground">Engagement</label>
        <select
          value={eid || ""}
          disabled={loadingList || noEngagements || listBusy}
          onChange={(ev) => setEngagement(ev.target.value)}
          className="crt-num min-w-[220px] rounded-sm border border-zinc-300 bg-white px-3 py-2 text-sm text-foreground outline-none focus:border-primary focus:ring-1 focus:ring-primary disabled:opacity-50 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100"
        >
          {loadingList || listBusy ? <option value="">Resolving…</option> : null}
          {!loadingList && !listBusy && engagements.every((en) => en.engagement_id !== eid) && eid ? (
            <option value={eid}>{eid} (unlisted)</option>
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

      {noEngagements ? (
        <SectionCard
          kicker="NO DATA"
          title="No audit engagements available"
          bodyClassName="space-y-3 p-6 text-sm text-muted-foreground"
        >
          <p>Create an engagement in Audit Planning to populate executive summary, assurance scores, and the committee pack.</p>
          <Link to="/app/audit-planning" className="crt-num inline-block text-primary underline">
            Go to audit planning
          </Link>
        </SectionCard>
      ) : null}

      {!noEngagements ? (
        <>
          <nav
            aria-label="Section shortcuts"
            className="sticky top-2 z-10 mb-4 flex flex-wrap gap-2 rounded-sm border border-zinc-200 bg-white/90 px-2 py-2 text-[11px] backdrop-blur-sm dark:border-zinc-700 dark:bg-zinc-950/90"
          >
            <span className="self-center text-muted-foreground">Jump:</span>
            <a href="#exec-tier-a" className="crt-num text-primary underline-offset-2 hover:underline">
              Tier A
            </a>
            <a href="#exec-tier-b" className="crt-num text-primary underline-offset-2 hover:underline">
              Tier B
            </a>
            <a href="#exec-tier-c" className="crt-num text-primary underline-offset-2 hover:underline">
              Tier C
            </a>
            <a href="#exec-reporting" className="crt-num text-primary underline-offset-2 hover:underline">
              Reporting
            </a>
            <a href="#exec-agenda" className="crt-num text-primary underline-offset-2 hover:underline">
              Agenda
            </a>
            <a href="#exec-scores" className="crt-num text-primary underline-offset-2 hover:underline">
              Scores
            </a>
            <a href="#exec-radar" className="crt-num text-primary underline-offset-2 hover:underline">
              Radar
            </a>
            <a href="#exec-workflow" className="crt-num text-primary underline-offset-2 hover:underline">
              Workflow
            </a>
            <a href="#exec-risks" className="crt-num text-primary underline-offset-2 hover:underline">
              Risks
            </a>
            <a href="#exec-compliance" className="crt-num text-primary underline-offset-2 hover:underline">
              Compliance
            </a>
          </nav>

          <div className="mb-6 flex flex-wrap gap-2" role="tablist" aria-label="Executive review tabs">
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                role="tab"
                aria-selected={tab === t.id}
                aria-controls={`exec-panel-${t.id}`}
                id={`exec-tab-${t.id}`}
                disabled={!eid || listBusy}
                onClick={() => setTab(t.id)}
                className={`crt-num h-9 rounded-sm border px-3 text-[10px] uppercase tracking-wider transition-colors disabled:opacity-40 ${
                  tab === t.id
                    ? "border-primary bg-primary text-white"
                    : "border-zinc-300 bg-white text-zinc-600 hover:bg-zinc-50 hover:text-foreground dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>

          {tab === "summary" && dashboardLoading ? (
            <div className="space-y-4">
              <SkeletonBlock className="h-40 w-full" />
              <SkeletonBlock className="h-56 w-full" />
            </div>
          ) : null}

          {tab === "summary" && !dashboardLoading && eid ? (
            <div
              role="tabpanel"
              id="exec-panel-summary"
              aria-labelledby="exec-tab-summary"
              className="space-y-4"
            >
              {!dashboard ? (
                <SectionCard kicker="EMPTY" title="No dashboard" bodyClassName="p-6 text-sm text-muted-foreground">
                  Dashboard could not be loaded for this engagement.
                </SectionCard>
              ) : (
                <>
                  <div id="exec-tier-a" className="scroll-mt-24 space-y-3">
                    <p className="crt-num text-[11px] font-semibold uppercase tracking-wider text-foreground">
                      Tier A · Committee headline
                    </p>
                  <SectionCard kicker="HEADLINE" title={`${engagementRow?.entity_name || "Engagement"} · FY ${engagementRow?.financial_year || "—"}`} bodyClassName="p-6">
                    <div id="exec-scores" className="scroll-mt-24">
                      <div className="crt-overline mb-3 text-muted-foreground">Assurance metrics</div>
                      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3">
                        {scores &&
                          Object.entries(scores)
                            .filter(([k]) => k.endsWith("_score") || k === "continuous_assurance_score")
                            .map(([k, v]) => (
                              <div
                                key={k}
                                className="crt-num rounded-sm border border-zinc-200 bg-zinc-50/80 p-3 text-xs dark:border-zinc-800 dark:bg-zinc-900/40"
                              >
                                <div className="font-medium text-foreground">{humanizeKey(k)}</div>
                                {SCORE_DESCRIPTIONS[k] ? (
                                  <div className="mt-1 text-[11px] leading-snug text-muted-foreground">{SCORE_DESCRIPTIONS[k]}</div>
                                ) : null}
                                <div className="mt-2 font-display text-xl text-foreground">{String(v)}</div>
                              </div>
                            ))}
                      </div>
                      {kpis?.assurance_trend ? (
                        <p className="crt-num mt-3 text-xs text-muted-foreground">
                          Trend: <span className="font-medium text-foreground">{kpis.assurance_trend.direction}</span> · History points:{" "}
                          {kpis.assurance_trend.history_points}
                        </p>
                      ) : null}
                    </div>
                  </SectionCard>
                  </div>

                  <div id="exec-tier-b" className="scroll-mt-24 space-y-4">
                    <p className="crt-num text-[11px] font-semibold uppercase tracking-wider text-foreground">
                      Tier B · Risk & compliance signals
                    </p>
                  <div id="exec-radar" className="grid scroll-mt-24 gap-4 lg:grid-cols-2">
                    <SectionCard kicker="VISUAL" title="Assurance radar" bodyClassName="p-4">
                      <div className="h-[280px] w-full min-h-[240px]">
                        <ResponsiveContainer width="100%" height="100%">
                          <RadarChart data={radarChartData(kpis?.radar_components)} cx="50%" cy="50%" outerRadius="78%">
                            <PolarGrid />
                            <PolarAngleAxis dataKey="metric" tick={{ fontSize: 10 }} />
                            <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 10 }} />
                            <Radar name="Score" dataKey="value" stroke="#2563eb" fill="#2563eb" fillOpacity={0.35} />
                            <Tooltip />
                          </RadarChart>
                        </ResponsiveContainer>
                      </div>
                    </SectionCard>
                    <SectionCard kicker="ISSUES" title="Issue funnel" bodyClassName="space-y-4 p-4">
                      <p className="text-[11px] leading-snug text-muted-foreground">
                        Classic funnel (stage counts) plus horizontal bars for the same totals — tiers resolve via{" "}
                        <span className="crt-num font-medium text-foreground">tier_b.issue_funnel</span> when present.
                      </p>
                      {issueFunnelRows.every((r) => !r.value) ? (
                        <p className="text-sm text-muted-foreground">No open risks, cases, deficiencies, or observations in funnel buckets.</p>
                      ) : (
                        <div className="grid gap-6 lg:grid-cols-2">
                          <div className="h-[280px] w-full min-h-[240px]">
                            <ResponsiveContainer width="100%" height="100%">
                              <FunnelChart margin={{ left: 12, right: 12, top: 8, bottom: 8 }}>
                                <Tooltip />
                                <Funnel data={issueFunnelRows} dataKey="value" nameKey="name" stroke="#fafafa" strokeWidth={1} isAnimationActive={false}>
                                  {issueFunnelRows.map((_, i) => (
                                    <Cell key={`f-${issueFunnelRows[i]?.name ?? i}`} fill={FUNNEL_STAGE_FILLS[i % FUNNEL_STAGE_FILLS.length]} />
                                  ))}
                                </Funnel>
                              </FunnelChart>
                            </ResponsiveContainer>
                          </div>
                          <div className="h-[280px] w-full min-h-[240px]">
                            <ResponsiveContainer width="100%" height="100%">
                              <BarChart data={issueFunnelRows} layout="vertical" margin={{ left: 8, right: 12 }}>
                                <CartesianGrid strokeDasharray="3 3" className="stroke-muted opacity-40" />
                                <XAxis type="number" />
                                <YAxis type="category" dataKey="name" width={100} tick={{ fontSize: 10 }} />
                                <Tooltip />
                                <Bar dataKey="value" fill="#6366f1" radius={[0, 4, 4, 0]} />
                              </BarChart>
                            </ResponsiveContainer>
                          </div>
                        </div>
                      )}
                    </SectionCard>
                  </div>

                  {sparkOverall.length > 1 ? (
                    <SectionCard kicker="TIMELINE" title="Continuous assurance (snapshot history)" bodyClassName="p-4">
                      <div className="h-[200px] w-full">
                        <ResponsiveContainer width="100%" height="100%">
                          <LineChart data={sparkOverall.map((p) => ({ ...p, label: p.at }))} margin={{ left: 0, right: 8 }}>
                            <CartesianGrid strokeDasharray="3 3" className="stroke-muted opacity-40" />
                            <XAxis dataKey="label" hide />
                            <YAxis domain={[0, 100]} width={32} tick={{ fontSize: 10 }} />
                            <Tooltip />
                            <Line type="monotone" dataKey="value" stroke="#2563eb" strokeWidth={2} dot={false} />
                          </LineChart>
                        </ResponsiveContainer>
                      </div>
                    </SectionCard>
                  ) : null}

                  <div id="exec-compliance" className="scroll-mt-24">
                    <SectionCard kicker="COMPLIANCE" title="Law-level heatmap (non-compliant intensity)" bodyClassName="p-4">
                      {complianceLawRows.length === 0 ? (
                        <p className="text-sm text-muted-foreground">No compliance checklist loaded — run India compliance for this engagement.</p>
                      ) : (
                        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4">
                          {complianceLawRows.map((row) => (
                            <div
                              key={row.law}
                              title={`${row.law}: ${row.non_compliant || 0} non-compliant / ${row.total || 0}`}
                              className={`crt-num rounded-sm border border-zinc-200 p-3 text-center text-xs dark:border-zinc-800 ${
                                row.intensity > 66
                                  ? "bg-red-200/90 dark:bg-red-950/50"
                                  : row.intensity > 33
                                    ? "bg-amber-100/90 dark:bg-amber-950/40"
                                    : "bg-emerald-50/90 dark:bg-emerald-950/25"
                              }`}
                            >
                              <div className="font-medium">{row.law}</div>
                              <div className="mt-1 text-muted-foreground">NC {row.non_compliant ?? 0}</div>
                            </div>
                          ))}
                        </div>
                      )}
                    </SectionCard>
                  </div>

                  {kpis?.materiality_bridge ? (
                    <SectionCard kicker="MATERIALITY" title="Exception exposure bridge" bodyClassName="p-6 text-sm">
                      <p>{kpis.materiality_bridge.narrative}</p>
                      <dl className="mt-3 grid gap-2 sm:grid-cols-2">
                        <div>
                          <dt className="crt-overline text-muted-foreground">Planning materiality</dt>
                          <dd className="font-display text-lg">{kpis.materiality_bridge.planning_materiality}</dd>
                        </div>
                        <div>
                          <dt className="crt-overline text-muted-foreground">Open exception exposure</dt>
                          <dd className="font-display text-lg">{kpis.materiality_bridge.aggregated_open_exception_exposure}</dd>
                        </div>
                      </dl>
                    </SectionCard>
                  ) : null}
                  </div>

                  <div id="exec-tier-c" className="scroll-mt-24 space-y-4">
                    <p className="crt-num text-[11px] font-semibold uppercase tracking-wider text-foreground">
                      Tier C · Reporting readiness & narrative
                    </p>

                  <div id="exec-reporting" className="scroll-mt-24">
                    <SectionCard kicker="REPORTING" title="Report studio status" bodyClassName="space-y-3 p-6 text-sm">
                      <dl className="grid gap-3 sm:grid-cols-2">
                        <div>
                          <dt className="crt-overline text-muted-foreground">Latest report status</dt>
                          <dd className="mt-1 font-medium text-foreground">
                            {kpis?.reporting_status?.latest_report_status ?? "—"}
                          </dd>
                        </div>
                        <div>
                          <dt className="crt-overline text-muted-foreground">Opinion phase</dt>
                          <dd className="mt-1 font-medium text-foreground">
                            {kpis?.reporting_status?.opinion_phase ?? "—"}
                          </dd>
                        </div>
                      </dl>
                      {kpis?.reporting_status?.created_at ? (
                        <p className="crt-num text-xs text-muted-foreground">Updated {kpis.reporting_status.created_at}</p>
                      ) : null}
                      <p className="text-xs leading-relaxed text-muted-foreground">{kpis?.reporting_status?.kam_placeholder}</p>
                      <p className="text-xs leading-relaxed text-muted-foreground">{kpis?.reporting_status?.caro_placeholder}</p>
                      <Link to={reportStudio} className="crt-num inline-block text-xs font-medium text-primary underline">
                        Open report studio
                      </Link>
                    </SectionCard>
                  </div>

                  <div id="exec-agenda" className="scroll-mt-24">
                    <SectionCard kicker="AGENDA" title="Committee readiness checklist" bodyClassName="space-y-3 p-6 text-sm">
                      <ul className="space-y-2">
                        {(kpis?.agenda_readiness?.checklist || []).map((item) => (
                          <li key={item.id} className="flex items-start gap-2">
                            <span
                              className={`mt-0.5 font-mono text-base ${item.done ? "text-emerald-600 dark:text-emerald-400" : "text-muted-foreground"}`}
                              aria-hidden
                            >
                              {item.done ? "✓" : "○"}
                            </span>
                            <span className={item.done ? "text-foreground" : "text-muted-foreground"}>{item.label}</span>
                          </li>
                        ))}
                      </ul>
                      <p className="crt-num border-t border-zinc-200 pt-3 text-xs text-muted-foreground dark:border-zinc-700">
                        Open critical cases:{" "}
                        <span className="font-medium text-foreground">{kpis?.agenda_readiness?.critical_open_cases ?? "—"}</span>
                        {kpis?.agenda_readiness?.management_letter_generated ? " · Management letter on file" : ""}
                        {kpis?.agenda_readiness?.committee_pack_touched ? " · Committee pack touched" : ""}
                      </p>
                      <div className="border-t border-zinc-200 pt-3 dark:border-zinc-700">
                        <div className="crt-overline text-muted-foreground">Minutes follow-ups</div>
                        {Array.isArray(kpis?.agenda_readiness?.minutes_followups_stub) &&
                        kpis.agenda_readiness.minutes_followups_stub.length ? (
                          <ul className="mt-2 space-y-1 text-xs text-foreground">
                            {kpis.agenda_readiness.minutes_followups_stub.map((item, idx) => (
                              <li key={idx} className="crt-num">
                                {typeof item === "string" ? item : JSON.stringify(item)}
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                            No prior-meeting follow-ups on file yet — backend stub{" "}
                            <span className="crt-num font-medium text-foreground">minutes_followups_stub</span> is reserved for minutes linkage.
                          </p>
                        )}
                      </div>
                    </SectionCard>
                  </div>

                  <div id="exec-workflow" className="scroll-mt-24">
                    {dashboard.workflow_steps?.length ? (
                      <SectionCard kicker="WORKFLOW" title="Audit workflow timeline" bodyClassName="p-6">
                        <ol className="relative border-l border-zinc-200 pl-6 dark:border-zinc-700">
                          {dashboard.workflow_steps.map((step, i) => (
                            <li key={step.phase || i} className="mb-6 ml-1">
                              <span className="absolute -left-[9px] mt-1 h-4 w-4 rounded-full border-2 border-primary bg-white dark:bg-zinc-950" />
                              <div className="crt-overline text-muted-foreground">{step.phase}</div>
                              <p className="mt-1 text-sm text-foreground">{step.note}</p>
                              {step.path ? (
                                <Link to={step.path} className="crt-num mt-1 inline-block text-xs text-primary underline">
                                  Open
                                </Link>
                              ) : null}
                            </li>
                          ))}
                        </ol>
                      </SectionCard>
                    ) : null}
                  </div>

                  <div id="exec-risks" className="scroll-mt-24">
                    <SectionCard kicker="RISKS" title="Risk register preview" bodyClassName="p-0 overflow-x-auto">
                      <table className="crt-num w-full min-w-[480px] border-collapse text-left text-sm">
                        <thead>
                          <tr className="border-b border-zinc-200 bg-zinc-50 text-xs text-muted-foreground dark:border-zinc-700 dark:bg-zinc-900/60">
                            <th className="px-4 py-2 font-medium">Title</th>
                            <th className="px-4 py-2 font-medium">Rating</th>
                            <th className="px-4 py-2 font-medium">Process</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(kpis?.risk_register_preview || []).length === 0 ? (
                            <tr>
                              <td colSpan={3} className="px-4 py-6 text-muted-foreground">
                                No risks recorded for this engagement yet.
                              </td>
                            </tr>
                          ) : (
                            (kpis?.risk_register_preview || []).map((r) => (
                              <tr key={r.id || r.title} className="border-b border-zinc-100 dark:border-zinc-800">
                                <td className="px-4 py-2">{r.title}</td>
                                <td className="px-4 py-2">{r.risk_rating || "—"}</td>
                                <td className="px-4 py-2 text-muted-foreground">{r.process_area || "—"}</td>
                              </tr>
                            ))
                          )}
                        </tbody>
                      </table>
                    </SectionCard>
                  </div>

                  {dashboard.integration ? (
                    <SectionCard kicker="INTEGRATION" title="Cross-module linkage" bodyClassName="p-6 text-sm text-zinc-700 dark:text-zinc-300">
                      <p className="mb-3">{dashboard.integration.narrative}</p>
                      <dl className="crt-num grid grid-cols-1 gap-2 rounded-sm border border-zinc-200 bg-zinc-100 p-3 text-xs text-zinc-900 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-100 sm:grid-cols-2">
                        {dashboard.integration.counts &&
                          Object.entries(dashboard.integration.counts).map(([k, v]) => (
                            <div key={k} className="flex justify-between gap-2 border-b border-zinc-200/80 pb-1 dark:border-zinc-800/80">
                              <dt className="text-muted-foreground">{humanizeKey(k)}</dt>
                              <dd className="font-medium">{String(v)}</dd>
                            </div>
                          ))}
                      </dl>
                    </SectionCard>
                  ) : null}

                  {advisory ? (
                    <SectionCard kicker="ADVISORY" title="CFO preview" bodyClassName="space-y-2 p-6 text-sm text-foreground">
                      <div>
                        <span className="crt-overline text-muted-foreground">Lead risk</span>
                        <div className="mt-1">{(advisory.key_risks_summary || [])[0] || "—"}</div>
                      </div>
                      <div>
                        <span className="crt-overline text-muted-foreground">Finding</span>
                        <div className="mt-1">{(advisory.findings_cfo_language || [])[0] || "—"}</div>
                      </div>
                    </SectionCard>
                  ) : null}
                  </div>
                </>
              )}
            </div>
          ) : null}

          {tab === "assurance" && dashboardLoading ? (
            <div className="space-y-4">
              <SkeletonBlock className="h-48 w-full" />
              <SkeletonBlock className="h-40 w-full" />
            </div>
          ) : null}

          {tab === "assurance" && !dashboardLoading && eid ? (
            <div role="tabpanel" id="exec-panel-assurance" aria-labelledby="exec-tab-assurance" className="space-y-4">
              {!kpis ? (
                <SectionCard kicker="EMPTY" title="No KPI bundle" bodyClassName="p-6 text-sm text-muted-foreground">
                  Load the dashboard to see remediation SLA, evidence readiness, and sparklines.
                </SectionCard>
              ) : (
                <>
                  <SectionCard kicker="SLA" title="Remediation SLA (closed cases)" bodyClassName="p-6 text-sm">
                    <dl className="grid gap-3 sm:grid-cols-2">
                      <div>
                        <dt className="text-muted-foreground">Closed within SLA</dt>
                        <dd className="font-display text-2xl">{kpis.remediation_sla?.pct_closed_within_sla ?? "—"}%</dd>
                      </div>
                      <div>
                        <dt className="text-muted-foreground">Open overdue</dt>
                        <dd className="font-display text-2xl">{kpis.remediation_sla?.open_overdue_count ?? "—"}</dd>
                      </div>
                      <div>
                        <dt className="text-muted-foreground">Largest open exposure (USD)</dt>
                        <dd className="font-display text-xl">{kpis.remediation_sla?.largest_open_exposure_usd ?? "—"}</dd>
                      </div>
                    </dl>
                  </SectionCard>
                  <SectionCard kicker="EVIDENCE" title="Working paper readiness" bodyClassName="p-6 text-sm">
                    <p className="text-muted-foreground">{kpis.evidence_readiness?.definition}</p>
                    <div className="mt-3 grid gap-2 sm:grid-cols-3">
                      <div>
                        <span className="crt-overline text-muted-foreground">Readiness</span>
                        <div className="font-display text-2xl">{kpis.evidence_readiness?.readiness_pct ?? "—"}%</div>
                      </div>
                      <div>
                        <span className="crt-overline text-muted-foreground">Signed</span>
                        <div className="font-display text-xl">{kpis.evidence_readiness?.working_papers_with_signoff ?? "—"}</div>
                      </div>
                      <div>
                        <span className="crt-overline text-muted-foreground">Unsigned</span>
                        <div className="font-display text-xl">{kpis.evidence_readiness?.unsigned_count ?? "—"}</div>
                      </div>
                    </div>
                  </SectionCard>
                  <SectionCard kicker="SPARKS" title="Component histories (snapshots)" bodyClassName="p-4">
                    <div className="grid gap-6 md:grid-cols-2">
                      {Object.entries(kpis.sparkline_series || {})
                        .filter(([, pts]) => (pts || []).length > 1)
                        .slice(0, 6)
                        .map(([key, pts]) => (
                          <div key={key}>
                            <div className="crt-overline mb-2 text-[10px] text-muted-foreground">{humanizeKey(key)}</div>
                            <div className="h-[120px]">
                              <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={pts.map((p) => ({ ...p, label: p.at }))}>
                                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted opacity-40" />
                                  <XAxis dataKey="label" hide />
                                  <YAxis domain={[0, 100]} width={28} tick={{ fontSize: 9 }} />
                                  <Tooltip />
                                  <Line type="monotone" dataKey="value" stroke="#2563eb" strokeWidth={1.5} dot={false} />
                                </LineChart>
                              </ResponsiveContainer>
                            </div>
                          </div>
                        ))}
                    </div>
                  </SectionCard>
                  {scores ? (
                    <SectionCard kicker="COMPONENTS" title="Latest assurance components" bodyClassName="p-6">
                      <div className="grid grid-cols-1 gap-4 text-sm md:grid-cols-2">
                        {Object.entries(scores)
                          .filter(([k]) => k.endsWith("_score"))
                          .map(([k, v]) => (
                            <div key={k} className="rounded-sm border border-zinc-200 bg-zinc-50/80 p-4 dark:border-zinc-800 dark:bg-zinc-900/40">
                              <div className="crt-num text-[10px] uppercase text-muted-foreground">{humanizeKey(k)}</div>
                              <div className="mt-2 font-display text-2xl text-foreground">{v}</div>
                            </div>
                          ))}
                      </div>
                      <p className="crt-num mt-4 text-xs text-muted-foreground">
                        Overall index: {scores.continuous_assurance_score ?? "—"}
                      </p>
                    </SectionCard>
                  ) : null}
                </>
              )}
            </div>
          ) : null}

          {tab === "pack" ? (
            <>
              {tabLoading ? <div className="crt-num mb-4 text-xs text-muted-foreground">Loading pack…</div> : null}
              {!pack && !tabLoading ? (
                <SectionCard kicker="EMPTY" title="No pack data" bodyClassName="p-6 text-sm text-muted-foreground">
                  Committee pack could not be loaded for this engagement.
                </SectionCard>
              ) : null}
              {pack ? (
                <div role="tabpanel" id="exec-panel-pack" aria-labelledby="exec-tab-pack" className="space-y-4">
                  <SectionCard kicker="RISKS" title="Top risks (high / critical)" bodyClassName="p-6">
                    <ul className="space-y-2 text-sm text-foreground">
                      {(pack.top_risks || []).length === 0 ? <li className="text-muted-foreground">None flagged.</li> : null}
                      {(pack.top_risks || []).map((r) => (
                        <li key={r.id || r.risk_title || r.title}>
                          {r.risk_title || r.title} · {r.risk_rating}
                          {r.process_area ? <span className="text-muted-foreground"> · {r.process_area}</span> : null}
                        </li>
                      ))}
                    </ul>
                  </SectionCard>

                  <SectionCard kicker="CASES" title="Open cases (sample)" bodyClassName="p-6">
                    <p className="crt-num mb-2 text-xs text-muted-foreground">
                      {(pack.open_cases || []).filter((c) => c.status !== "closed").length} non-closed in sample
                    </p>
                    <ul className="space-y-2 text-sm text-foreground">
                      {(pack.open_cases || [])
                        .filter((c) => c.status !== "closed")
                        .slice(0, 8)
                        .map((c) => (
                          <li key={c.id || c.title}>
                            <span className="font-medium">{c.title || c.id || "Case"}</span>
                            <span className="text-muted-foreground"> · {c.status || "open"}</span>
                          </li>
                        ))}
                      {(pack.open_cases || []).filter((c) => c.status !== "closed").length === 0 ? (
                        <li className="text-muted-foreground">No open cases in sample.</li>
                      ) : null}
                    </ul>
                  </SectionCard>

                  {pack.materiality_snapshot ? (
                    <SectionCard kicker="MATERIALITY" title="Planning materiality" bodyClassName="p-6 text-sm">
                      <dl className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                        <div>
                          <dt className="crt-overline text-muted-foreground">Final materiality</dt>
                          <dd className="mt-1 font-display text-lg">
                            {pack.materiality_snapshot.final_materiality != null
                              ? String(pack.materiality_snapshot.final_materiality)
                              : "—"}
                          </dd>
                        </div>
                        <div>
                          <dt className="crt-overline text-muted-foreground">Performance materiality</dt>
                          <dd className="mt-1 font-display text-lg">
                            {pack.materiality_snapshot.performance != null ? String(pack.materiality_snapshot.performance) : "—"}
                          </dd>
                        </div>
                      </dl>
                      <Link to={`${hub}?tab=materiality`} className="crt-num mt-3 inline-block text-xs text-primary underline">
                        Open materiality working paper
                      </Link>
                    </SectionCard>
                  ) : null}

                  {pack.compliance_snapshot ? (
                    <SectionCard kicker="COMPLIANCE" title="India checklist snapshot" bodyClassName="p-6 text-sm">
                      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                        {[
                          ["Total", pack.compliance_snapshot.total],
                          ["Compliant", pack.compliance_snapshot.compliant],
                          ["Non-compliant", pack.compliance_snapshot.non_compliant],
                          ["Pending evidence", pack.compliance_snapshot.pending_evidence],
                        ].map(([label, val]) => (
                          <div
                            key={label}
                            className="crt-num rounded-sm border border-zinc-200 bg-zinc-50/80 p-3 text-center dark:border-zinc-800 dark:bg-zinc-900/40"
                          >
                            <div className="text-[10px] uppercase text-muted-foreground">{label}</div>
                            <div className="mt-1 font-display text-xl text-foreground">{val ?? "—"}</div>
                          </div>
                        ))}
                      </div>
                    </SectionCard>
                  ) : null}

                  <SectionCard kicker="REPORT" title="Latest auditor report draft" bodyClassName="space-y-3 p-6 text-sm">
                    {pack.latest_report ? (
                      <>
                        <p className="text-muted-foreground">
                          Status: <span className="font-medium text-foreground">{pack.latest_report.status || "draft"}</span>
                          {pack.latest_report.created_at ? (
                            <span className="crt-num text-muted-foreground"> · {pack.latest_report.created_at}</span>
                          ) : null}
                        </p>
                        <Link to={reportStudio} className="crt-num inline-block text-primary underline">
                          Open report studio
                        </Link>
                      </>
                    ) : (
                      <p className="text-muted-foreground">No final report draft stored yet — generate one from report studio.</p>
                    )}
                  </SectionCard>

                  {pack.advisory ? (
                    <SectionCard kicker="ADVISORY" title="Committee talking points" bodyClassName="space-y-4 p-6 text-sm">
                      {(pack.advisory.key_risks_summary || []).length ? (
                        <div>
                          <div className="crt-overline mb-2 text-muted-foreground">Key risks</div>
                          <ul className="list-disc space-y-1 pl-5">
                            {(pack.advisory.key_risks_summary || []).map((line, i) => (
                              <li key={i}>{line}</li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                      {(pack.advisory.control_improvements || []).length ? (
                        <div>
                          <div className="crt-overline mb-2 text-muted-foreground">Control improvements</div>
                          <ul className="list-disc space-y-1 pl-5">
                            {(pack.advisory.control_improvements || []).map((line, i) => (
                              <li key={i}>{line}</li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                    </SectionCard>
                  ) : null}
                </div>
              ) : null}
            </>
          ) : null}

          {tab === "letter" && eid ? (
            <div role="tabpanel" id="exec-panel-letter" aria-labelledby="exec-tab-letter" className="grid gap-6 lg:grid-cols-2">
              <SectionCard kicker="MANAGEMENT LETTER" title="Generator" bodyClassName="space-y-4 p-6">
                <p className="text-sm text-muted-foreground">
                  Builds a draft from open observations on this engagement. CFO-tone advisory sits beside this panel from the live dashboard
                  bundle.
                </p>
                <button
                  type="button"
                  onClick={genLetter}
                  className="crt-num h-10 rounded-sm border border-primary bg-primary px-4 text-xs font-medium uppercase tracking-wider text-white transition-opacity hover:opacity-90"
                >
                  Generate from observations
                </button>
                {letterText ? (
                  <div>
                    <div className="crt-overline mb-2 text-muted-foreground">Stored generator output</div>
                    <pre className="max-h-[40vh] overflow-y-auto whitespace-pre-wrap rounded-sm border border-zinc-200 bg-zinc-100 p-4 text-sm text-zinc-900 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-100">
                      {letterText}
                    </pre>
                  </div>
                ) : null}
              </SectionCard>
              <div className="space-y-4">
                {dashboardLoading ? (
                  <div className="space-y-3">
                    <SkeletonBlock className="h-24 w-full" />
                    <SkeletonBlock className="h-32 w-full" />
                  </div>
                ) : null}
                {!dashboardLoading && advisory?.management_letter_draft ? (
                  <SectionCard kicker="ADVISORY" title="Management letter (AI draft)" bodyClassName="p-6">
                    <pre className="max-h-[36vh] overflow-y-auto whitespace-pre-wrap text-sm text-foreground">{advisory.management_letter_draft}</pre>
                  </SectionCard>
                ) : null}
                {!dashboardLoading &&
                  ADVISORY_SECTIONS.map(({ key, title }) => (
                  <SectionCard key={key} kicker="ADVISORY" title={title} bodyClassName="p-6">
                    {(advisory?.[key] || []).length === 0 ? (
                      <p className="text-sm text-muted-foreground">No items in this snapshot.</p>
                    ) : (
                      <ul className="list-disc space-y-2 pl-5 text-sm text-foreground">
                        {(advisory[key] || []).map((line, i) => (
                          <li key={i}>{line}</li>
                        ))}
                      </ul>
                    )}
                  </SectionCard>
                  ))}
              </div>
            </div>
          ) : null}
        </>
      ) : null}
    </PageShell>
  );
}
