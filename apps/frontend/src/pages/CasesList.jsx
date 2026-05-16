import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { http } from "../lib/api";
import { SeverityBadge, StatusBadge, PriorityTag } from "../components/Badges";
import { MaterialImpactBadge } from "../components/ca/AuditCaBadges";
import { fmtUSD, fmtDate } from "../lib/format";
import { MagnifyingGlass } from "@phosphor-icons/react";
import InsightPanel from "../components/InsightPanel";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";

export default function CasesList() {
  const [all, setAll] = useState([]);
  const [searchParams] = useSearchParams();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState(searchParams.get("status") || "");
  const [severity, setSeverity] = useState(searchParams.get("severity") || "");
  const [processFilter, setProcessFilter] = useState(searchParams.get("process") || "");
  const [entity, setEntity] = useState(searchParams.get("entity") || "");
  const nav = useNavigate();
  const baseMasterParams = useDashboardFilterParams();

  // Keep triage filters aligned with URL (heatmap / CFO drill-down updates query without remount).
  useEffect(() => {
    setStatus(searchParams.get("status") || "");
    setSeverity(searchParams.get("severity") || "");
    setProcessFilter(searchParams.get("process") || "");
    setEntity(searchParams.get("entity") || "");
  }, [searchParams]);

  useEffect(() => {
    const engagementId = searchParams.get("engagement_id") || undefined;
    const drillProcess = searchParams.get("process") || "";
    const drillEntity = searchParams.get("entity") || "";
    const masterParams = { ...baseMasterParams };
    // Heatmap / CFO drill uses `entity` + `process` query keys; scope API fetches to that cell so
    // client filters are satisfiable even when the masters strip pins a different `m_entity`.
    const apiScope = { ...masterParams };
    if (drillEntity) {
      apiScope.entity_code = drillEntity;
    }
    const exceptionParams = { limit: 800, ...apiScope };
    if (drillProcess) {
      exceptionParams.process = drillProcess;
    }
    const matchesDrill = (e) => {
      if (!drillProcess && !drillEntity) return false;
      if (drillProcess && e.process !== drillProcess) return false;
      if (drillEntity && e.entity !== drillEntity) return false;
      return true;
    };
    const sevRank = { critical: 4, high: 3, medium: 2, low: 1 };
    // Pull both open cases and uncased exceptions as shadow rows (CFO heatmap drill-down must
    // include low-exposure open items; they sort last by $ alone and were dropped by slice(0, 100)).
    Promise.all([
      http.get("/cases", { params: { engagement_id: engagementId, ...apiScope } }),
      http.get("/exceptions", { params: exceptionParams }),
    ]).then(([cases, exs]) => {
      const realIds = new Set(cases.data.map(c => c.exception_id));
      const uncased = exs.data.filter(e => !realIds.has(e.id) && (!engagementId || e.engagement_id === engagementId));
      uncased.sort((a, b) => {
        const ma = matchesDrill(a);
        const mb = matchesDrill(b);
        if (ma !== mb) return ma ? -1 : 1;
        const exp = (b.financial_exposure || 0) - (a.financial_exposure || 0);
        if (exp !== 0) return exp;
        return (sevRank[b.severity] || 0) - (sevRank[a.severity] || 0);
      });
      const shadow = uncased.slice(0, 300).map(e => ({
        id: `shadow-${e.id}`,
        exception_id: e.id,
        title: e.title,
        summary: e.summary,
        control_code: e.control_code,
        control_name: e.control_name,
        severity: e.severity,
        priority: e.severity === "critical" ? "P1" : e.severity === "high" ? "P2" : "P3",
        status: "open",
        owner_email: "",
        owner_name: "",
        financial_exposure: e.financial_exposure,
        entity: e.entity,
        process: e.process,
        detected_at: e.detected_at,
        opened_at: e.detected_at,
        due_date: e.detected_at,
        department_id: e.department_id || e.dept_id,
        cost_center_id: e.cost_center_id || e.cc_id,
        is_shadow: true,
      }));
      setAll([...cases.data, ...shadow]);
    });
  }, [searchParams, baseMasterParams]);

  const filtered = useMemo(() => {
    const term = q.trim().toLowerCase();
    return all.filter(c => {
      if (status && c.status !== status) return false;
      if (severity && c.severity !== severity) return false;
      if (processFilter && c.process !== processFilter) return false;
      if (entity && c.entity !== entity) return false;
      if (term && !(
        c.title?.toLowerCase().includes(term) ||
        c.control_code?.toLowerCase().includes(term) ||
        c.entity?.toLowerCase().includes(term) ||
        c.process?.toLowerCase().includes(term)
      )) return false;
      return true;
    });
  }, [all, q, status, severity, processFilter, entity]);

  const openCase = async (c) => {
    if (!c.is_shadow) {
      nav(`/app/cases/${c.id}`);
      return;
    }
    // promote exception to case
    const { data: created } = await http.post(`/cases/from-exception?exception_id=${c.exception_id}`);
    nav(`/app/cases/${created.id}`);
  };

  return (
    <PageShell maxWidth="max-w-[1700px]">
      <div data-testid="cases-list">
        <PageHeader
          kicker="ALL CASES & OPEN EXCEPTIONS"
          title="Cases · remediation"
          subtitle="Triage exceptions, manage remediation, and keep evidence and governance in one place."
        />

        <InsightPanel section="cases" title="Cases · AI Insights" />

        <MastersFilterStrip className="mb-4" />

        <SectionCard
          kicker="FILTERS"
          title="Search & triage"
          right={
            <span className="crt-num text-[10px] uppercase tracking-wider text-muted-foreground">
              {filtered.length} of {all.length}
            </span>
          }
          className="mb-4"
          bodyClassName="p-4"
        >
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative min-w-[260px] max-w-xl flex-1">
              <MagnifyingGlass size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                data-testid="case-search"
                value={q}
                onChange={e => setQ(e.target.value)}
                placeholder="Search cases, control codes, entities…"
                className="h-10 w-full rounded-sm border border-zinc-300 bg-white pl-9 pr-3 text-sm text-foreground placeholder:text-zinc-400 outline-none focus:border-primary focus:ring-1 focus:ring-primary dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100 dark:placeholder:text-zinc-500"
              />
            </div>
            <select
              data-testid="filter-status"
              value={status}
              onChange={e => setStatus(e.target.value)}
              className="crt-num h-10 rounded-sm border border-zinc-300 bg-white px-3 text-xs uppercase tracking-wider text-foreground outline-none focus:border-primary focus:ring-1 focus:ring-primary dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100"
            >
              <option value="">All status</option><option value="open">Open</option><option value="in_progress">In progress</option><option value="closed">Closed</option>
            </select>
            <select
              data-testid="filter-severity"
              value={severity}
              onChange={e => setSeverity(e.target.value)}
              className="crt-num h-10 rounded-sm border border-zinc-300 bg-white px-3 text-xs uppercase tracking-wider text-foreground outline-none focus:border-primary focus:ring-1 focus:ring-primary dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100"
            >
              <option value="">All severity</option><option value="critical">Critical</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option>
            </select>
            {(processFilter || entity) && (
              <span className="crt-num inline-flex h-10 items-center gap-2 rounded-sm border border-zinc-200 bg-zinc-50 px-3 text-xs uppercase tracking-wider text-primary dark:border-zinc-700 dark:bg-zinc-900/60">
                {processFilter && `process: ${processFilter}`}{processFilter && entity && " · "}{entity && `entity: ${entity}`}
                <button
                  type="button"
                  onClick={() => {
                    const next = new URLSearchParams(searchParams);
                    next.delete("process");
                    next.delete("entity");
                    const s = next.toString();
                    nav({ pathname: "/app/cases", search: s ? `?${s}` : "" }, { replace: true });
                  }}
                  className="text-primary hover:text-foreground"
                  data-testid="clear-filters"
                >
                  ×
                </button>
              </span>
            )}
          </div>
        </SectionCard>

        <SectionCard kicker="CASES" title="All cases" bodyClassName="p-0">
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[70vh]" testId="cases-list-table">
            <DataTableHead>
              <tr>
                <DataTableTh>Issue</DataTableTh>
                <DataTableTh className="w-24">Priority</DataTableTh>
                <DataTableTh className="w-28">Severity</DataTableTh>
                <DataTableTh className="w-32">Status</DataTableTh>
                <DataTableTh className="w-48">Owner</DataTableTh>
                <DataTableTh className="w-36">Org slice</DataTableTh>
                <DataTableTh align="right" className="w-32">Exposure</DataTableTh>
                <DataTableTh className="w-32">Detected</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {filtered.map(c => (
                <DataTableRow
                  key={c.id}
                  onClick={() => openCase(c)}
                  testId={`case-row-${c.id}`}
                >
                  <DataTableTd>
                    <div className="flex max-w-xl flex-wrap items-center gap-2 truncate text-sm font-medium text-zinc-900 dark:text-zinc-50">
                      <span className="min-w-0 truncate">{c.title}</span>
                      {c.material_impact ? <MaterialImpactBadge /> : null}
                    </div>
                    <div className="crt-num text-[10px] text-zinc-600 dark:text-zinc-400">{c.control_code} · {c.entity} · {c.process}</div>
                  </DataTableTd>
                  <DataTableTd><PriorityTag priority={c.priority} /></DataTableTd>
                  <DataTableTd><SeverityBadge severity={c.severity} /></DataTableTd>
                  <DataTableTd>
                    {c.is_shadow ? (
                      <span className="crt-num text-[10px] uppercase text-muted-foreground">unassigned</span>
                    ) : (
                      <StatusBadge status={c.status} />
                    )}
                  </DataTableTd>
                  <DataTableTd className="truncate text-xs text-zinc-800 dark:text-zinc-200">
                    {c.is_shadow ? "Unassigned" : (c.owner_name || c.owner_email || "—")}
                  </DataTableTd>
                  <DataTableTd className="crt-num max-w-[9rem] text-[10px] leading-tight text-zinc-600 dark:text-zinc-400">
                    {c.department_id || c.cost_center_id ? (
                      <>
                        {c.department_id ? <div className="truncate" title={c.department_id}>dept · {String(c.department_id).slice(0, 10)}…</div> : null}
                        {c.cost_center_id ? <div className="truncate" title={c.cost_center_id}>cc · {String(c.cost_center_id).slice(0, 10)}…</div> : null}
                      </>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </DataTableTd>
                  <DataTableTd align="right" className="crt-num tabular-nums text-foreground">{fmtUSD(c.financial_exposure)}</DataTableTd>
                  <DataTableTd className="crt-num text-xs text-zinc-800 dark:text-zinc-200">{fmtDate(c.detected_at)}</DataTableTd>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </SectionCard>
      </div>
    </PageShell>
  );
}
