import { useCallback, useEffect, useState } from "react";
import { Link, useParams, useSearchParams, useNavigate } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { ArrowLeft, ArrowSquareOut } from "@phosphor-icons/react";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import { useAuth } from "../lib/auth";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import MaterialitySetupPanel from "../components/ca/MaterialitySetupPanel";
import RacmBuilderPanel from "../components/ca/RacmBuilderPanel";
import FinancialStatementAuditPanel from "../components/ca/FinancialStatementAuditPanel";
import ScheduleAuditDashboard from "../components/ca/ScheduleAuditDashboard";
import IfcEvaluationPanel from "../components/ca/IfcEvaluationPanel";
import { AuditStatusBadge, RiskBadge } from "../components/ca/AuditCaBadges";
import MilestoneTimeline from "../components/ca/MilestoneTimeline";
import EngagementSummaryCards from "../components/ca/EngagementSummaryCards";
import AuditPlanningPanel from "../components/ca/AuditPlanningPanel";
import AuditTeamCard from "../components/ca/AuditTeamCard";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { PenaltyRiskBadge } from "../components/Badges";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "materiality", label: "Materiality" },
  { id: "racm", label: "RACM" },
  { id: "financial", label: "FS audit" },
  { id: "schedules", label: "Schedules" },
  { id: "ifc", label: "IFC" },
  { id: "wp", label: "Working papers" },
  { id: "compliance", label: "Compliance" },
  { id: "reporting", label: "Reporting" },
  { id: "command", label: "Command center" },
];

export default function AuditEngagementDetail() {
  const { user } = useAuth();
  const nav = useNavigate();
  const { engagementId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const dashboardParams = useDashboardFilterParams();
  const eid = decodeURIComponent(engagementId || "");
  const [tab, setTab] = useState("overview");
  const [eng, setEng] = useState(null);
  const [summary, setSummary] = useState(null);
  const [materiality, setMateriality] = useState(null);
  const [wpStats, setWpStats] = useState(null);
  const [compliance, setCompliance] = useState(null);
  const [observations, setObservations] = useState([]);
  const [scores, setScores] = useState(null);
  const [loading, setLoading] = useState(true);

  /** Sync tab from URL only when `tab` or engagement changes — ignore unrelated query params. */
  const tabFromUrl = searchParams.get("tab");
  useEffect(() => {
    if (tabFromUrl && TABS.some(x => x.id === tabFromUrl)) setTab(tabFromUrl);
  }, [eid, tabFromUrl]);

  const loadCore = useCallback(async () => {
    if (!eid) return;
    const qp = { params: dashboardParams };
    const [{ data: e }, { data: s }] = await Promise.all([
      http.get(`/audit-engagements/${encodeURIComponent(eid)}`, qp),
      http.get(`/audit-engagements/${encodeURIComponent(eid)}/summary`, qp),
    ]);
    setEng(e);
    setSummary(s);
  }, [eid, dashboardParams]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!eid) return;
      setLoading(true);
      try {
        await loadCore();
      } catch {
        if (!cancelled) toast.error("Failed to load engagement");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [eid, loadCore]);

  useEffect(() => {
    if (!eid) return;
    const run = async () => {
      try {
        if (tab === "materiality") {
          const { data } = await http.get(`/audit-engagements/${encodeURIComponent(eid)}/materiality`, { params: dashboardParams });
          setMateriality(data);
        }
        if (tab === "wp") {
          const { data } = await http.get(`/audit-engagements/${encodeURIComponent(eid)}/wp-workbench`, { params: dashboardParams });
          setWpStats({
            folders: (data.folders || []).length,
            papers: (data.working_papers || []).length,
            plans: (data.sampling_plans || []).length,
            vouches: (data.vouching_items || []).length,
          });
        }
        if (tab === "compliance") {
          const { data } = await http.get(`/audit-engagements/${encodeURIComponent(eid)}/compliance/status`, { params: dashboardParams });
          setCompliance(data);
        }
        if (tab === "reporting") {
          const { data } = await http.get(`/audit-engagements/${encodeURIComponent(eid)}/observations`, { params: dashboardParams });
          setObservations(data || []);
        }
        if (tab === "command") {
          const { data } = await http.get(`/audit-engagements/${encodeURIComponent(eid)}/continuous-assurance-score`, { params: dashboardParams });
          setScores(data);
        }
      } catch {
        if (tab === "materiality") setMateriality(null);
      }
    };
    run();
  }, [eid, tab, dashboardParams]);

  const ensureCompliance = async () => {
    try {
      await http.post(`/audit-engagements/${encodeURIComponent(eid)}/compliance/checklist`, { law_codes: [] }, { params: dashboardParams });
      const { data } = await http.get(`/audit-engagements/${encodeURIComponent(eid)}/compliance/status`, { params: dashboardParams });
      setCompliance(data);
      toast.success("Compliance checklist ready");
    } catch {
      toast.error("Compliance setup failed");
    }
  };

  if (loading && !eng) {
    return <div className="p-8 font-mono text-xs text-[#737373] uppercase tracking-wider">Loading engagement…</div>;
  }
  if (!eng) {
    return <div className="p-8 text-sm text-[#A3A3A3]">Engagement not found.</div>;
  }

  return (
    <PageShell maxWidth="max-w-[1800px]">
      <Link to="/app/audit-planning" className="inline-flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-[#737373] hover:text-white mb-3">
        <ArrowLeft size={14} /> Audit planning
      </Link>
      <PageHeader
        kicker="ENGAGEMENT HUB"
        title={eng.entity_name}
        subtitle={`${eng.engagement_id} · FY ${eng.financial_year} · ${eng.audit_type}`}
        right={
          <div className="flex flex-wrap gap-2 items-center">
            <AuditStatusBadge status={eng.status} />
            <RiskBadge level={eng.risk_level} />
            <Link className="text-xs font-mono uppercase text-[#0A84FF] hover:underline flex items-center gap-1" to={`/app/cases?engagement_id=${encodeURIComponent(eid)}`}>
              Cases <ArrowSquareOut size={12} />
            </Link>
            <Link className="text-xs font-mono uppercase text-[#0A84FF] hover:underline flex items-center gap-1" to="/app/evidence">
              Evidence <ArrowSquareOut size={12} />
            </Link>
            <Link className="text-xs font-mono uppercase text-[#0A84FF] hover:underline flex items-center gap-1" to="/app/copilot">
              AI Copilot <ArrowSquareOut size={12} />
            </Link>
            <Link className="text-xs font-mono uppercase text-[#0A84FF] hover:underline flex items-center gap-1" to="/app/audit">
              Controls <ArrowSquareOut size={12} />
            </Link>
          </div>
        }
      />

      <div className="flex flex-wrap gap-2 mb-6">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => {
              setTab(t.id);
              setSearchParams(p => {
                const n = new URLSearchParams(p);
                n.set("tab", t.id);
                return n;
              }, { replace: true });
            }}
            className={`px-3 h-9 font-mono text-[10px] uppercase tracking-wider border ${tab === t.id ? "bg-white text-black border-white" : "border-[#262626] text-[#A3A3A3] hover:text-white"}`}
          >
            {t.label}
          </button>
        ))}
        <Link to={`/app/audit-planning/engagements/${encodeURIComponent(eid)}/team`} className="px-3 h-9 font-mono text-[10px] uppercase tracking-wider border border-[#262626] text-[#A3A3A3] hover:text-white inline-flex items-center">
          Team assignment
        </Link>
        <Link to="/app/audit-planning/calendar" className="px-3 h-9 font-mono text-[10px] uppercase tracking-wider border border-[#262626] text-[#A3A3A3] hover:text-white inline-flex items-center">
          Calendar
        </Link>
        <Link to={`/app/audit-planning/engagements/${encodeURIComponent(eid)}/racm`} className="px-3 h-9 font-mono text-[10px] uppercase tracking-wider border border-[#262626] text-[#0A84FF] hover:border-white inline-flex items-center">
          RACM builder
        </Link>
        <Link to={`/app/audit-planning/engagements/${encodeURIComponent(eid)}/fs-audit`} className="px-3 h-9 font-mono text-[10px] uppercase tracking-wider border border-[#262626] text-[#0A84FF] hover:border-white inline-flex items-center">
          FS audit module
        </Link>
        <Link to={`/app/audit-planning/engagements/${encodeURIComponent(eid)}/schedules-audit`} className="px-3 h-9 font-mono text-[10px] uppercase tracking-wider border border-[#262626] text-[#0A84FF] hover:border-white inline-flex items-center">
          Schedule audit
        </Link>
        <Link to={`/app/audit-planning/engagements/${encodeURIComponent(eid)}/ifc-engine`} className="px-3 h-9 font-mono text-[10px] uppercase tracking-wider border border-[#262626] text-[#0A84FF] hover:border-white inline-flex items-center">
          IFC engine
        </Link>
        <Link to={`/app/audit-planning/engagements/${encodeURIComponent(eid)}/working-papers`} className="px-3 h-9 font-mono text-[10px] uppercase tracking-wider border border-[#262626] text-[#0A84FF] hover:border-white inline-flex items-center">
          Working papers
        </Link>
        <Link to={`/app/audit-planning/engagements/${encodeURIComponent(eid)}/india-compliance`} className="px-3 h-9 font-mono text-[10px] uppercase tracking-wider border border-[#262626] text-[#0A84FF] hover:border-white inline-flex items-center">
          India compliance
        </Link>
        <Link to={`/app/audit-planning/engagements/${encodeURIComponent(eid)}/report-studio`} className="px-3 h-9 font-mono text-[10px] uppercase tracking-wider border border-[#262626] text-[#0A84FF] hover:border-white inline-flex items-center">
          Report studio
        </Link>
      </div>

      {tab === "overview" && summary ? (
        <div className="space-y-6">
          <EngagementSummaryCards summary={summary} engagementId={eid} />
          <AuditPlanningPanel engagementId={eid} engagement={eng} onSaved={loadCore} />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <SectionCard kicker="MILESTONES" title="Timeline" bodyClassName="p-4">
              <MilestoneTimeline milestones={eng.milestones} />
            </SectionCard>
            <SectionCard kicker="TEAM" title="Assigned team" bodyClassName="p-4">
              <AuditTeamCard members={eng.team_members} />
            </SectionCard>
          </div>
          {(eng.detailed_scopes || []).length > 0 ? (
            <SectionCard kicker="SCOPE AREAS" title="Structured scope lines" bodyClassName="p-4 text-sm">
              <ul className="space-y-2 text-[#A3A3A3]">
                {(eng.detailed_scopes || []).map((s) => (
                  <li key={s.id || s.description}><span className="text-white">{s.process_area || "Area"}</span> — {s.description}{s.financial_statement_area ? <span className="font-mono text-[10px] text-[#737373]"> · {s.financial_statement_area}</span> : null}</li>
                ))}
              </ul>
            </SectionCard>
          ) : null}
          {(eng.planning_notes || []).length > 0 ? (
            <SectionCard kicker="NOTES" title="Planning notes" bodyClassName="p-4 text-sm space-y-2">
              {(eng.planning_notes || []).map((n) => (
                <div key={n.id} className="border-b border-[#262626] pb-2 text-[#A3A3A3]">
                  <div className="text-white">{n.note}</div>
                  <div className="font-mono text-[10px] text-[#737373] mt-1">
                    {n.author_email ? (
                      <Link to={`/app/drill/user/${encodeURIComponent(n.author_email)}`} className="text-[#0A84FF] hover:underline">
                        {n.author_email}
                      </Link>
                    ) : "—"}
                    {" · "}{n.created_at?.slice(0, 10)}
                  </div>
                </div>
              ))}
            </SectionCard>
          ) : null}
        </div>
      ) : null}

      {tab === "materiality" ? (
        <MaterialitySetupPanel
          engagementId={eid}
          materiality={materiality}
          onMaterialityUpdated={setMateriality}
          currentUserEmail={user?.email}
        />
      ) : null}

      {tab === "racm" ? (
        <RacmBuilderPanel engagementId={eid} compact />
      ) : null}

      {tab === "financial" ? <FinancialStatementAuditPanel engagementId={eid} compact /> : null}

      {tab === "schedules" ? <ScheduleAuditDashboard engagementId={eid} compact /> : null}

      {tab === "ifc" ? <IfcEvaluationPanel engagementId={eid} compact /> : null}

      {tab === "wp" ? (
        <SectionCard
          kicker="WORKING PAPERS"
          title="Digital WP, sampling & vouching"
          right={
            <Link
              to={`/app/audit-planning/engagements/${encodeURIComponent(eid)}/working-papers`}
              className="px-4 h-9 inline-flex items-center bg-white text-black font-mono text-[10px] uppercase"
            >
              Open module
            </Link>
          }
          bodyClassName="p-6 space-y-4"
        >
          <p className="text-sm text-[#A3A3A3] max-w-2xl">
            Document procedures, cross-reference codes (e.g. WP-REV-001), attach evidence, run the sampling engine, complete vouching with tick marks, and record preparer / reviewer / partner sign-off in the full working papers workspace.
          </p>
          <button
            type="button"
            className="px-3 h-9 border border-[#262626] text-xs font-mono uppercase text-[#A3A3A3] hover:text-white"
            onClick={async () => {
              try {
                await http.post(`/audit-engagements/${encodeURIComponent(eid)}/working-papers/folders`, {}, { params: dashboardParams });
                const { data } = await http.get(`/audit-engagements/${encodeURIComponent(eid)}/wp-workbench`, { params: dashboardParams });
                setWpStats({
                  folders: (data.folders || []).length,
                  papers: (data.working_papers || []).length,
                  plans: (data.sampling_plans || []).length,
                  vouches: (data.vouching_items || []).length,
                });
                toast.success("Folders ready");
              } catch {
                toast.error("Folder seed failed");
              }
            }}
          >
            Ensure default folders
          </button>
          {wpStats ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 font-mono text-[10px] uppercase text-[#737373]">
              <div className="border border-[#262626] p-3"><div className="text-2xl text-white">{wpStats.folders}</div>Folders</div>
              <div className="border border-[#262626] p-3"><div className="text-2xl text-white">{wpStats.papers}</div>Working papers</div>
              <div className="border border-[#262626] p-3"><div className="text-2xl text-white">{wpStats.plans}</div>Sampling plans</div>
              <div className="border border-[#262626] p-3"><div className="text-2xl text-white">{wpStats.vouches}</div>Vouching lines</div>
            </div>
          ) : (
            <div className="text-xs font-mono text-[#737373]">Open the tab to load counts…</div>
          )}
        </SectionCard>
      ) : null}

      {tab === "compliance" ? (
        <SectionCard
          kicker="INDIA"
          title="Regulatory compliance"
          right={
            <Link
              to={`/app/audit-planning/engagements/${encodeURIComponent(eid)}/india-compliance`}
              className="px-4 h-9 inline-flex items-center bg-white text-black font-mono text-[10px] uppercase"
            >
              Compliance audit dashboard
            </Link>
          }
          bodyClassName="p-6"
        >
          <button type="button" onClick={ensureCompliance} className="px-4 h-10 bg-white text-black font-mono text-xs uppercase mb-4">Build checklist</button>
          <div className="text-xs font-mono text-[#737373] mb-2">
            Requirements: {compliance?.summary?.total ?? 0}
            {compliance?.summary?.pending_evidence != null ? (
              <span className="ml-3">Pending evidence: {compliance.summary.pending_evidence}</span>
            ) : null}
          </div>
          <DataTable className="rounded-none border-0 max-h-[50vh]">
            <DataTableHead>
              <tr>
                <DataTableTh>Title</DataTableTh>
                <DataTableTh>Penalty</DataTableTh>
                <DataTableTh>Status</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {(compliance?.requirements || []).slice(0, 80).map((r) => (
                <DataTableRow
                  key={r.id}
                  className="cursor-pointer"
                  onClick={() => nav(`/app/audit-planning/engagements/${encodeURIComponent(eid)}/india-compliance`)}
                >
                  <DataTableTd className="text-sm">{r.title}</DataTableTd>
                  <DataTableTd><PenaltyRiskBadge risk={r.penalty_risk || "medium"} /></DataTableTd>
                  <DataTableTd className="font-mono text-[10px]">{r.status}</DataTableTd>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </SectionCard>
      ) : null}

      {tab === "reporting" ? (
        <SectionCard
          kicker="REPORTING"
          title="Observations &amp; report"
          right={
            <Link
              to={`/app/audit-planning/engagements/${encodeURIComponent(eid)}/report-studio`}
              className="px-4 h-9 inline-flex items-center bg-white text-black font-mono text-[10px] uppercase"
            >
              Report &amp; opinion studio
            </Link>
          }
          bodyClassName="p-6 space-y-3"
        >
          <div className="flex flex-wrap gap-2">
            <button type="button" className="px-3 h-9 border border-[#262626] text-xs font-mono uppercase" onClick={async () => { await http.post(`/audit-engagements/${encodeURIComponent(eid)}/opinion/generate`, {}, { params: dashboardParams }); toast.success("Opinion generated"); }}>Generate opinion</button>
            <button type="button" className="px-3 h-9 border border-[#262626] text-xs font-mono uppercase" onClick={async () => { await http.post(`/audit-engagements/${encodeURIComponent(eid)}/caro/generate`, {}, { params: dashboardParams }); toast.success("CARO draft"); }}>CARO annexure</button>
            <button type="button" className="px-3 h-9 border border-[#262626] text-xs font-mono uppercase" onClick={async () => { await http.post(`/audit-engagements/${encodeURIComponent(eid)}/report/generate`, {}, { params: dashboardParams }); toast.success("Report draft"); }}>Final report</button>
            <button type="button" className="px-3 h-9 border border-[#262626] text-xs font-mono uppercase" onClick={async () => { await http.post(`/audit-engagements/${encodeURIComponent(eid)}/management-letter/generate`, {}, { params: dashboardParams }); toast.success("Mgmt letter"); }}>Management letter</button>
          </div>
          <ul className="text-sm text-[#E5E5E5] space-y-2">
            {observations.map((o) => (
              <li key={o.id}>
                <Link
                  to={`/app/audit-planning/engagements/${encodeURIComponent(eid)}/report-studio/observations`}
                  className="text-[#0A84FF] hover:underline"
                >
                  {o.title}
                </Link>
                <span className="text-[#737373] font-mono text-xs"> · {o.severity}</span>
              </li>
            ))}
          </ul>
        </SectionCard>
      ) : null}

      {tab === "command" && scores ? (
        <SectionCard kicker="ASSURANCE" title="Continuous assurance scores" bodyClassName="p-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 font-mono text-xs">
            {Object.entries(scores).filter(([k]) => k.endsWith("_score")).map(([k, v]) => (
              <div key={k} className="border border-[#262626] p-3"><div className="text-[#737373]">{k.replace(/_/g, " ")}</div><div className="text-xl text-white mt-1">{v}</div></div>
            ))}
          </div>
          <Link to={`/app/ca-command-center?engagement_id=${encodeURIComponent(eid)}`} className="inline-block mt-4 text-xs font-mono uppercase text-[#0A84FF]">Open full CA command center →</Link>
        </SectionCard>
      ) : null}
    </PageShell>
  );
}
