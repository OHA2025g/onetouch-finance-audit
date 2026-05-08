import React, { useEffect, useState, useMemo, useCallback } from "react";
import { http } from "../lib/api";
import { StatCard } from "../components/StatCard";
import { SeverityBadge } from "../components/Badges";
import { fmtUSD, fmtPct, fmtDateTime, fmtDate } from "../lib/format";
import { toast } from "sonner";
import { FileXls, FilePdf, Eye } from "@phosphor-icons/react";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { useMastersFilters } from "../lib/MastersFilterContext";
import { buildDashboardFilterParams } from "../lib/mastersDashboardParams";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";

export default function AuditorPortal() {
  const [d, setD] = useState(null);
  const { entityCode, periodYm, periodExplicit, departmentId, costCenterId } = useMastersFilters();

  const dashboardParams = useMemo(
    () =>
      buildDashboardFilterParams({
        entityCode,
        periodYm,
        periodExplicit,
        departmentId,
        costCenterId,
      }),
    [entityCode, periodYm, periodExplicit, departmentId, costCenterId],
  );

  useEffect(() => {
    http
      .get("/auditor/pack", { params: dashboardParams })
      .then((r) => setD(r.data))
      .catch(() => toast.error("Load failed"));
  }, [dashboardParams]);

  const download = useCallback(
    async (format) => {
      try {
        const resp = await http.get(`/reports/audit-committee-pack.${format}`, {
          params: dashboardParams,
          responseType: "blob",
        });
        const blob = new Blob([resp.data]);
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `audit-committee-pack.${format}`;
        a.click();
        URL.revokeObjectURL(url);
        const scoped =
          !!(dashboardParams.entity_code ||
          dashboardParams.period_ym ||
          dashboardParams.department_id ||
          dashboardParams.cost_center_id);
        toast.success(scoped ? `Downloaded scoped ${format.toUpperCase()} pack (Phase 14)` : `Downloaded ${format.toUpperCase()} pack`);
      } catch {
        toast.error("Download failed");
      }
    },
    [dashboardParams],
  );

  if (!d)
    return <div className="p-8 font-mono text-xs uppercase tracking-wider text-[#737373]">Loading auditor workspace…</div>;
  const k = d.kpis;
  const filtersApplied = d.filters_applied || {};

  return (
    <PageShell maxWidth="max-w-[1700px]">
      <div data-testid="auditor-portal">
        <PageHeader
          kicker="EXTERNAL AUDITOR · READ-ONLY"
          title="Auditor workspace"
          icon={<Eye size={18} />}
          subtitle={`Generated ${fmtDateTime(d.generated_at)} · CFO-aligned reporting extract (Phase 14)`}
          right={
            <div className="flex gap-2">
              <button
                data-testid="download-pdf-btn"
                onClick={() => download("pdf")}
                className="flex h-11 items-center gap-2 rounded-full border border-[#404040] bg-[#141414]/70 px-5 text-xs font-mono uppercase tracking-wider text-white backdrop-blur transition-colors hover:bg-[#1F1F1F]/70"
              >
                <FilePdf size={14} /> Download PDF
              </button>
              <button
                data-testid="download-xlsx-btn"
                onClick={() => download("xlsx")}
                className="flex h-11 items-center gap-2 rounded-full bg-white px-5 text-xs font-mono uppercase tracking-wider text-black shadow-[0_18px_55px_rgba(255,255,255,0.10)] transition-colors hover:bg-[#E5E5E5]"
              >
                <FileXls size={14} /> Download XLSX
              </button>
            </div>
          }
        />

        <MastersFilterStrip className="mb-4" />

        {Object.keys(filtersApplied).length > 0 ? (
          <p className="crt-num mb-4 font-mono text-[10px] uppercase tracking-wider text-[#737373]">
            Reporting context:&nbsp;
            {Object.entries(filtersApplied)
              .map(([gk, gv]) => `${gk}=${gv}`)
              .join(" · ")}
          </p>
        ) : null}

        <div className="mb-8 grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
          <StatCard
            label="Audit readiness"
            value={fmtPct(k.audit_readiness_pct)}
            testId="auditor-kpi-readiness"
            severity={k.audit_readiness_pct >= 80 ? "success" : k.audit_readiness_pct >= 60 ? "warning" : "critical"}
          />
          <StatCard label="Unresolved exposure" value={fmtUSD(k.unresolved_high_risk_exposure)} severity="critical" testId="auditor-kpi-exposure" />
          <StatCard label="High/critical cases" value={k.high_critical_open_cases} severity="warning" testId="auditor-kpi-highcrit" />
          <StatCard label="Open cases" value={k.open_cases} testId="auditor-kpi-open" />
          <StatCard label="Evidence completeness" value={fmtPct(k.evidence_completeness_pct)} testId="auditor-kpi-evidence" />
          <StatCard label="Remediation SLA" value={fmtPct(k.remediation_sla_pct)} testId="auditor-kpi-sla" />
        </div>

        <div className="mb-8 grid grid-cols-1 gap-4 lg:grid-cols-3">
          <SectionCard className="lg:col-span-2" kicker="RISK" title="Top unresolved risks" data-testid="auditor-risks" bodyClassName="p-0">
            <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[55vh]" testId="auditor-risks-table">
              <DataTableHead>
                <tr>
                  <DataTableTh>Issue</DataTableTh>
                  <DataTableTh className="w-28">Severity</DataTableTh>
                  <DataTableTh className="w-24">Entity</DataTableTh>
                  <DataTableTh align="right" className="w-28">
                    Exposure
                  </DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {d.top_risks.map((r) => (
                  <DataTableRow key={r.id}>
                    <DataTableTd>
                      <div className="max-w-lg truncate text-sm text-white">{r.title}</div>
                      <div className="mt-0.5 font-mono text-[10px] text-[#737373]">
                        {r.control_code} · {r.process}
                      </div>
                    </DataTableTd>
                    <DataTableTd>
                      <SeverityBadge severity={r.severity} />
                    </DataTableTd>
                    <DataTableTd className="font-mono text-xs text-[#A3A3A3]">{r.entity}</DataTableTd>
                    <DataTableTd align="right" className="font-mono tabular-nums text-white">
                      {fmtUSD(r.financial_exposure)}
                    </DataTableTd>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </DataTable>
          </SectionCard>

          <SectionCard kicker="POLICY" title="Policies in scope" data-testid="auditor-policies">
            <div className="space-y-3">
              {d.policies.map((p) => (
                <div key={p.id} className="rounded-xl border border-[#262626] bg-[#0A0A0A]/55 p-4 backdrop-blur">
                  <div className="font-mono text-[10px] uppercase tracking-wider text-[#737373]">
                    {p.id} · effective {p.effective_date}
                  </div>
                  <div className="mt-1 text-sm text-white">{p.title}</div>
                  <div className="mt-2 space-y-1">
                    {p.clauses.map((c, i) => (
                      <div key={i} className="truncate font-mono text-[10px] text-[#A3A3A3]">
                        · {c}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </SectionCard>
        </div>

        <SectionCard kicker="CONTROLS" title={`Control library (${d.controls.length})`} data-testid="auditor-controls" bodyClassName="p-0">
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[65vh]" testId="auditor-controls-table">
            <DataTableHead>
              <tr>
                <DataTableTh>Code</DataTableTh>
                <DataTableTh>Name</DataTableTh>
                <DataTableTh>Process</DataTableTh>
                <DataTableTh>Framework</DataTableTh>
                <DataTableTh>Last run</DataTableTh>
                <DataTableTh align="right">Exceptions</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {d.controls.map((c) => (
                <DataTableRow key={c.id}>
                  <DataTableTd className="font-mono text-xs text-white">{c.code}</DataTableTd>
                  <DataTableTd className="text-sm text-white">{c.name}</DataTableTd>
                  <DataTableTd className="font-mono text-xs text-[#A3A3A3]">{c.process}</DataTableTd>
                  <DataTableTd className="font-mono text-xs text-[#A3A3A3]">{c.framework}</DataTableTd>
                  <DataTableTd className="font-mono text-xs text-[#737373]">{c.last_run_at ? fmtDate(c.last_run_at) : "—"}</DataTableTd>
                  <DataTableTd align="right" className="font-mono tabular-nums" style={{ color: c.last_run_exceptions > 0 ? "#FF9F0A" : "#30D158" }}>
                    {c.last_run_exceptions ?? "—"}
                  </DataTableTd>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </SectionCard>
      </div>
    </PageShell>
  );
}
