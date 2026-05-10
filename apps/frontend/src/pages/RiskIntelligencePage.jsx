import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { WarningCircle, ArrowRight, Download, Copy } from "@phosphor-icons/react";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import { StatCard } from "../components/StatCard";
import { SeverityBadge } from "../components/Badges";
import { fmtUSD, fmtPct } from "../lib/format";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useMastersFilters } from "../lib/MastersFilterContext";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import ReadinessHeatmap from "../components/ReadinessHeatmap";
import InsightPanel from "../components/InsightPanel";

/**
 * Phase 36 — Cross-module risk intelligence: CFO readiness heatmap + top risks,
 * plus universal finance risk scores from masters (entity-level composite).
 * Phase 37 — Scoped committee-pack exports + master-aware deep links (readiness `?process=` lens).
 * Phase 38 — Consolidated `/dashboard/risk-intelligence` payload; `?process=` URL lens (shareable with masters).
 * Phase 39 — `/insights/risk` AI insight panel (scoped); Compliance hub deep link to this page with masters.
 * Phase 40 — Copy shareable URL (origin + path + query); readiness header link; external dashboard test; Super Admin preview nav.
 */
export default function RiskIntelligencePage() {
  const [cockpit, setCockpit] = useState(null);
  const [riskScores, setRiskScores] = useState([]);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();
  const processFilter = (searchParams.get("process") || "").trim() || "all";
  const { hrefWithMasterParams } = useMastersFilters();
  const nav = useNavigate();
  const location = useLocation();
  const firstLoadRef = useRef(true);

  const copyShareableLink = useCallback(async () => {
    try {
      const url = `${window.location.origin}${location.pathname}${location.search}`;
      await navigator.clipboard.writeText(url);
      toast.success("Copied shareable link (masters + process lens if set)");
    } catch {
      toast.error("Could not copy link");
    }
  }, [location.pathname, location.search]);

  const dashboardParams = useDashboardFilterParams();

  const load = useCallback(async () => {
    if (firstLoadRef.current) setLoading(true);
    try {
      const { data } = await http.get("/dashboard/risk-intelligence", {
        params: { ...dashboardParams, risk_scores_limit: 200 },
      });
      const { risk_scores: rs, ...cockpitRest } = data || {};
      setCockpit(cockpitRest);
      setRiskScores(rs?.items || []);
    } catch {
      toast.error("Failed to load risk intelligence");
    } finally {
      if (firstLoadRef.current) {
        setLoading(false);
        firstLoadRef.current = false;
      }
    }
  }, [dashboardParams]);

  useEffect(() => {
    load();
  }, [load]);

  const exportPack = useCallback(
    async (format) => {
      setExporting(true);
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
        const scoped = !!(
          dashboardParams.entity_code ||
          dashboardParams.period_ym ||
          dashboardParams.department_id ||
          dashboardParams.cost_center_id
        );
        toast.success(
          scoped ? `Downloaded scoped ${format.toUpperCase()} pack` : `Downloaded ${format.toUpperCase()} pack`,
        );
      } catch {
        toast.error(`Export ${format} failed`);
      }
      setExporting(false);
    },
    [dashboardParams],
  );

  const readinessHref = useMemo(() => {
    const base = hrefWithMasterParams("/app/readiness");
    if (processFilter === "all") return base;
    const sep = base.includes("?") ? "&" : "?";
    return `${base}${sep}process=${encodeURIComponent(processFilter)}`;
  }, [hrefWithMasterParams, processFilter]);

  const processes = useMemo(() => {
    if (!cockpit?.heatmap) return [];
    return [...new Set(cockpit.heatmap.map((r) => r.process))].sort();
  }, [cockpit]);

  useEffect(() => {
    const raw = (searchParams.get("process") || "").trim();
    if (!raw || !processes.length) return;
    if (!processes.includes(raw)) {
      setSearchParams(
        (prev) => {
          const n = new URLSearchParams(prev);
          n.delete("process");
          return n;
        },
        { replace: true },
      );
    }
  }, [processes, searchParams, setSearchParams]);

  const filteredHeatmap = useMemo(() => {
    if (!cockpit?.heatmap) return [];
    return cockpit.heatmap.filter((r) => processFilter === "all" || r.process === processFilter);
  }, [cockpit, processFilter]);

  const filteredTopRisks = useMemo(() => {
    if (!cockpit?.top_risks) return [];
    return cockpit.top_risks.filter((r) => processFilter === "all" || r.process === processFilter).slice(0, 10);
  }, [cockpit, processFilter]);

  if (loading || !cockpit) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="risk-intelligence-loading">
        Loading risk intelligence…
      </div>
    );
  }

  const k = cockpit.kpis || {};

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="risk-intelligence">
        <PageHeader
          kicker="RISK INTELLIGENCE"
          title="Universal risk scoring"
          icon={<WarningCircle size={18} />}
          subtitle={
            <>
              Phase 36–40 — Heatmap, top risks, master scores; one API round-trip; scoped AI insights; copy link for the
              exact reporting context; exports and deep links keep masters; optional{" "}
              <span className="font-medium">?process=</span> lens for heatmap, top risks, and readiness.
            </>
          }
          right={
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                data-testid="ri-export-xlsx"
                disabled={exporting}
                onClick={() => exportPack("xlsx")}
                className="inline-flex items-center gap-2 rounded-sm border border-primary bg-primary px-3 py-2 text-xs font-medium uppercase tracking-wider text-white shadow-none transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                <Download size={14} /> XLSX
              </button>
              <button
                type="button"
                data-testid="ri-export-pdf"
                disabled={exporting}
                onClick={() => exportPack("pdf")}
                className="inline-flex items-center gap-2 rounded-sm border border-zinc-300 bg-white px-3 py-2 text-xs font-medium uppercase tracking-wider text-zinc-600 shadow-none transition-colors hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
              >
                <Download size={14} /> PDF pack
              </button>
              <Link
                to={hrefWithMasterParams("/app/cfo")}
                className="inline-flex items-center gap-2 rounded-sm border border-zinc-300 bg-white px-3 py-2 text-xs font-medium uppercase tracking-wider text-zinc-600 shadow-none transition-colors hover:bg-zinc-50 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
              >
                CFO cockpit <ArrowRight size={14} />
              </Link>
              <Link
                to={readinessHref}
                className="inline-flex items-center gap-2 rounded-sm border border-zinc-300 bg-white px-3 py-2 text-xs font-medium uppercase tracking-wider text-zinc-600 shadow-none transition-colors hover:bg-zinc-50 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
                data-testid="ri-readiness-deep-link"
              >
                Readiness matrix <ArrowRight size={14} />
              </Link>
              <Link
                to={hrefWithMasterParams("/app/compliance")}
                className="inline-flex items-center gap-2 rounded-sm border border-zinc-300 bg-white px-3 py-2 text-xs font-medium uppercase tracking-wider text-zinc-600 shadow-none transition-colors hover:bg-zinc-50 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
              >
                Compliance
              </Link>
              <button
                type="button"
                onClick={copyShareableLink}
                className="inline-flex items-center gap-2 rounded-sm border border-zinc-300 bg-white px-3 py-2 text-xs font-medium uppercase tracking-wider text-zinc-600 shadow-none transition-colors hover:bg-zinc-50 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
                data-testid="ri-copy-share-link"
                title="Copy URL with current master filters and process lens"
              >
                <Copy size={14} /> Copy link
              </button>
            </div>
          }
        />

        <MastersFilterStrip className="mb-4" />

        {processFilter !== "all" ? (
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-sm border border-primary/30 bg-primary/5 px-3 py-2 text-xs">
            <span className="crt-num uppercase tracking-wider text-foreground">
              Phase 38–40 — Process lens: <span className="font-medium">{processFilter}</span>
            </span>
            <Link
              to={hrefWithMasterParams("/app/risk-intelligence")}
              className="crt-num uppercase tracking-wider text-primary hover:underline"
              data-testid="ri-clear-process-lens"
            >
              Show all processes
            </Link>
          </div>
        ) : null}

        <div className="mb-6 flex flex-wrap items-center gap-2">
          <span className="crt-overline inline-flex h-9 items-center rounded-sm border border-zinc-200 bg-white px-3 text-muted-foreground dark:border-zinc-700 dark:bg-zinc-900/60">
            Process lens
          </span>
          <select
            value={processFilter}
            onChange={(e) => {
              const v = e.target.value;
              setSearchParams(
                (prev) => {
                  const n = new URLSearchParams(prev);
                  if (v === "all") n.delete("process");
                  else n.set("process", v);
                  return n;
                },
                { replace: true },
              );
            }}
            className="crt-num h-9 rounded-sm border border-zinc-300 bg-white px-3 text-xs uppercase tracking-wider text-foreground outline-none focus:border-primary dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100"
            data-testid="ri-process-filter"
          >
            <option value="all">All processes</option>
            {processes.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>

        <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
          <StatCard
            label="Audit readiness"
            value={fmtPct(k.audit_readiness_pct)}
            unit=""
            severity={k.audit_readiness_pct >= 80 ? "success" : k.audit_readiness_pct >= 60 ? "warning" : "critical"}
          />
          <StatCard label="High / crit exposure" value={fmtUSD(k.unresolved_high_risk_exposure)} severity="critical" />
          <StatCard label="Open high / crit cases" value={String(k.high_critical_open_cases ?? "—")} />
          <StatCard label="Remediation SLA" value={fmtPct(k.remediation_sla_pct)} unit="" />
        </div>

        <InsightPanel section="risk" title="Risk intelligence · AI insights" />

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          <SectionCard
            kicker="READINESS"
            title="Process × entity heatmap"
            className="xl:col-span-2 overflow-hidden"
            subtitle="Same engine as CFO cockpit; click a cell to open scoped cases."
            right={
              <Link
                to={readinessHref}
                className="crt-num text-[10px] uppercase tracking-wider text-primary hover:underline"
                data-testid="ri-heatmap-to-readiness"
              >
                Matrix view →
              </Link>
            }
          >
            <ReadinessHeatmap
              rows={filteredHeatmap.length ? filteredHeatmap : cockpit.heatmap}
              buildDrillHref={(p, e) =>
                hrefWithMasterParams(
                  `/app/cases?process=${encodeURIComponent(p)}&entity=${encodeURIComponent(e)}`,
                )
              }
            />
          </SectionCard>

          <SectionCard kicker="MASTERS" title="Universal risk scores" subtitle="Composite scores from finance_risk_scores (Phase 2 masters).">
            {!riskScores.length ? (
              <p className="text-sm text-muted-foreground">No risk score rows yet. Reseed or widen entity filter.</p>
            ) : (
              <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[55vh]" testId="ri-risk-scores-table">
                <DataTableHead>
                  <tr>
                    <DataTableTh>Object</DataTableTh>
                    <DataTableTh>Band</DataTableTh>
                    <DataTableTh align="right">Score</DataTableTh>
                  </tr>
                </DataTableHead>
                <DataTableBody>
                  {riskScores.map((row) => (
                    <DataTableRow key={row.id}>
                      <DataTableTd>
                        <div className="text-sm text-foreground">
                          {row.object_type} · {row.object_id || row.entity_code}
                        </div>
                        <div className="crt-num mt-0.5 text-[10px] text-muted-foreground">
                          {(row.drivers || []).slice(0, 2).join(" · ") || "—"}
                        </div>
                      </DataTableTd>
                      <DataTableTd className="crt-num text-xs uppercase">{row.band || "—"}</DataTableTd>
                      <DataTableTd align="right" className="font-mono tabular-nums text-sm">
                        {typeof row.score === "number" ? row.score.toFixed(1) : "—"}
                      </DataTableTd>
                    </DataTableRow>
                  ))}
                </DataTableBody>
              </DataTable>
            )}
          </SectionCard>
        </div>

        <SectionCard
          kicker="EXCEPTIONS"
          title="Top unresolved risks"
          className="mt-4"
          right={<span className="crt-num text-[10px] uppercase tracking-wider text-muted-foreground">severity × exposure</span>}
        >
          <div className="hidden md:block">
            <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[50vh]" testId="ri-top-risks-table">
              <DataTableHead>
                <tr>
                  <DataTableTh>Issue</DataTableTh>
                  <DataTableTh className="w-28">Severity</DataTableTh>
                  <DataTableTh className="w-28">Entity</DataTableTh>
                  <DataTableTh align="right" className="w-32">Exposure</DataTableTh>
                  <DataTableTh className="w-12" />
                </tr>
              </DataTableHead>
              <DataTableBody>
                {filteredTopRisks.map((r) => (
                  <DataTableRow
                    key={r.id}
                    onClick={() => nav(`/app/evidence/${r.id}`)}
                    className="cursor-pointer"
                    testId={`ri-top-risk-${r.control_code}`}
                  >
                    <DataTableTd>
                      <div className="max-w-md truncate text-sm text-foreground">{r.title}</div>
                      <div className="crt-num mt-0.5 text-[10px] text-muted-foreground">
                        {r.control_code} · {r.process}
                      </div>
                    </DataTableTd>
                    <DataTableTd>
                      <SeverityBadge severity={r.severity} />
                    </DataTableTd>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">{r.entity}</DataTableTd>
                    <DataTableTd align="right" className="crt-num tabular-nums">
                      {fmtUSD(r.financial_exposure)}
                    </DataTableTd>
                    <DataTableTd className="text-muted-foreground">
                      <ArrowRight size={14} />
                    </DataTableTd>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </DataTable>
          </div>
          <div className="divide-y divide-zinc-200 dark:divide-zinc-800 md:hidden">
            {filteredTopRisks.map((r) => (
              <button
                key={r.id}
                type="button"
                onClick={() => nav(`/app/evidence/${r.id}`)}
                className="w-full p-4 text-left transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-900/60"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate text-sm text-foreground">{r.title}</div>
                    <div className="crt-num mt-1 text-[10px] text-muted-foreground">
                      {r.control_code} · {r.process} · {r.entity}
                    </div>
                  </div>
                  <SeverityBadge severity={r.severity} />
                </div>
                <div className="mt-2 flex items-center justify-between">
                  <span className="crt-num text-xs text-muted-foreground">Exposure</span>
                  <span className="crt-num tabular-nums">{fmtUSD(r.financial_exposure)}</span>
                </div>
              </button>
            ))}
          </div>
        </SectionCard>
      </div>
    </PageShell>
  );
}
