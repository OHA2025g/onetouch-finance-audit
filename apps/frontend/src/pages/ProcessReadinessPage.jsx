import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { fmtUSD } from "../lib/format";
import { useMastersFilters } from "../lib/MastersFilterContext";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import InsightPanel from "../components/InsightPanel";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import ReadinessHeatmap from "../components/ReadinessHeatmap";
import clsx from "clsx";

function govScopeLabel(row) {
  if (!row) return "—";
  if (row.scope_label) return row.scope_label;
  if (row.entity_code != null && String(row.entity_code).trim() !== "") return String(row.entity_code);
  return "ALL ENTITIES";
}

function govDepthSnapshot(label, row) {
  if (!row) return "—";
  if (label === "RPT register") {
    const rp = row.related_parties_count ?? 0;
    const tx = row.rpt_transactions_count ?? 0;
    return `${rp} related parties · ${tx} RPT txns`;
  }
  if (label === "DOA rules") {
    const rc = row.rules_count ?? (row.items?.length ?? 0);
    const mx = row.matrix_rows ?? 0;
    return `${rc} rules · ${mx} matrix rows`;
  }
  if (label === "SoD campaigns") {
    const c = row.campaigns_total ?? (row.items?.length ?? 0);
    return `${c} campaign(s)`;
  }
  if (label === "MDQ summary") {
    const n = row.open_findings ?? 0;
    return `${n} open findings`;
  }
  return "—";
}

function cellTone(r) {
  if (r.readiness >= 80) return "text-[hsl(var(--chart-4))]";
  if (r.readiness >= 60) return "text-[hsl(var(--chart-3))]";
  return "text-[hsl(var(--destructive))]";
}

export default function ProcessReadinessPage() {
  const [payload, setPayload] = useState(null);
  const nav = useNavigate();
  const [sp] = useSearchParams();
  const processLens = (sp.get("process") || "").trim();
  const { hrefWithMasterParams } = useMastersFilters();
  const dashboardParams = useDashboardFilterParams();
  const complianceDepthParams = useMemo(() => {
    const ec = dashboardParams.entity_code;
    return ec ? { entity_code: ec } : {};
  }, [dashboardParams.entity_code]);
  const [govDepth, setGovDepth] = useState(null);

  useEffect(() => {
    http
      .get("/readiness", { params: dashboardParams })
      .then((r) => setPayload(r.data))
      .catch(() => toast.error("Failed to load readiness matrix"));
  }, [dashboardParams]);

  useEffect(() => {
    let cancelled = false;
    const paths = ["/compliance-depth/rpt/register", "/compliance-depth/doa/rules", "/compliance-depth/sod/campaigns", "/compliance-depth/mdq/summary"];
    Promise.all(paths.map((p) => http.get(p, { params: complianceDepthParams })))
      .then(([rpt, doa, sod, mdq]) => {
        if (cancelled) return;
        setGovDepth({
          rpt: rpt.data,
          doa: doa.data,
          sod: sod.data,
          mdq: mdq.data,
        });
      })
      .catch(() => {
        if (!cancelled) setGovDepth(null);
      });
    return () => {
      cancelled = true;
    };
  }, [complianceDepthParams]);

  const rows = useMemo(() => payload?.rows ?? [], [payload]);
  const applied = payload?.filters_applied ?? {};

  const displayRows = useMemo(() => {
    if (!processLens) return rows;
    return rows.filter((r) => r.process === processLens);
  }, [rows, processLens]);

  const heatmapRows = useMemo(() => (processLens ? displayRows : rows), [processLens, displayRows, rows]);

  return (
    <PageShell maxWidth="max-w-[1700px]">
      <div data-testid="process-readiness-page">
        <PageHeader
          kicker="REPORTING"
          title="Process × entity readiness"
          subtitle="Weighted control, reconciliation, evidence, and issue signals — scoped by the global reporting context (Phase 12)."
          right={
            <Link
              to={hrefWithMasterParams("/app/risk-intelligence")}
              className="hidden items-center gap-2 rounded-sm border border-zinc-300 bg-white px-3 py-2 text-xs font-medium uppercase tracking-wider text-zinc-600 shadow-none transition-colors hover:bg-zinc-50 sm:inline-flex dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
              data-testid="readiness-risk-intelligence-header-link"
            >
              Risk intelligence
            </Link>
          }
        />

        <MastersFilterStrip className="mb-4" />

        {processLens ? (
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-sm border border-primary/30 bg-primary/5 px-3 py-2 text-xs">
            <span className="crt-num uppercase tracking-wider text-foreground">
              Phase 37–40 — Matrix filtered to process: <span className="font-medium">{processLens}</span>
            </span>
            <div className="flex flex-wrap items-center gap-3">
              <Link
                to={hrefWithMasterParams("/app/readiness")}
                className="crt-num uppercase tracking-wider text-primary hover:underline"
                data-testid="readiness-clear-process-lens"
              >
                Show all processes
              </Link>
              <Link
                to={(() => {
                  const b = hrefWithMasterParams("/app/risk-intelligence");
                  const sep = b.includes("?") ? "&" : "?";
                  return `${b}${sep}process=${encodeURIComponent(processLens)}`;
                })()}
                className="crt-num uppercase tracking-wider text-primary hover:underline"
                data-testid="readiness-to-risk-hub"
              >
                Risk hub (same lens) →
              </Link>
            </div>
          </div>
        ) : null}

        {Object.keys(applied).length > 0 ? (
          <p className="crt-num mb-4 text-[10px] uppercase tracking-wider text-muted-foreground">
            Filters applied:{" "}
            {Object.entries(applied)
              .map(([k, v]) => `${k}=${v}`)
              .join(" · ")}
          </p>
        ) : null}

        <InsightPanel section="cfo" title="Readiness context · AI Insights" />

        {govDepth ? (
          <SectionCard
            kicker="GOVERNANCE DEPTH · WAVE 3"
            title="Compliance depth — GET /compliance-depth/* (live counts, Phase 40)"
            bodyClassName="p-0"
            className="mb-6"
          >
            <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[260px]" testId="readiness-gov-depth-table">
              <DataTableHead>
                <tr>
                  <DataTableTh>Surface</DataTableTh>
                  <DataTableTh>Scope</DataTableTh>
                  <DataTableTh>Live snapshot</DataTableTh>
                  <DataTableTh>Summary</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {[
                  { key: "rpt", label: "RPT register", row: govDepth.rpt },
                  { key: "doa", label: "DOA rules", row: govDepth.doa },
                  { key: "sod", label: "SoD campaigns", row: govDepth.sod },
                  { key: "mdq", label: "MDQ summary", row: govDepth.mdq },
                ].map(({ key, label, row }) => (
                  <DataTableRow key={key} testId={`readiness-gov-depth-${key}`}>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">{label}</DataTableTd>
                    <DataTableTd className="crt-num text-xs text-foreground">{govScopeLabel(row)}</DataTableTd>
                    <DataTableTd className="crt-num text-xs text-foreground">{govDepthSnapshot(label, row)}</DataTableTd>
                    <DataTableTd className="text-xs text-muted-foreground max-w-[360px] truncate" title={row?.note}>
                      {row?.note || "—"}
                    </DataTableTd>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </DataTable>
          </SectionCard>
        ) : null}

        {heatmapRows.length > 0 ? (
          <SectionCard
            kicker="HEATMAP"
            title="Process × entity matrix"
            subtitle="Same readiness scores as the table below — click a cell to open scoped cases."
            className="mb-6"
            bodyClassName="p-0 overflow-x-auto"
          >
            <ReadinessHeatmap
              rows={heatmapRows}
              buildDrillHref={(p, e) =>
                hrefWithMasterParams(`/app/cases?entity=${encodeURIComponent(e)}&process=${encodeURIComponent(p)}`)
              }
            />
          </SectionCard>
        ) : null}

        <SectionCard
          kicker="MATRIX"
          title="Readiness cells"
          right={
            <span className="crt-num text-xs text-muted-foreground">
              {displayRows.length} of {rows.length} combinations
            </span>
          }
          bodyClassName="p-0"
        >
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[72vh]" testId="readiness-matrix-table">
            <DataTableHead>
              <tr>
                <DataTableTh>Entity</DataTableTh>
                <DataTableTh>Process</DataTableTh>
                <DataTableTh align="right">Readiness %</DataTableTh>
                <DataTableTh align="right">Open crit/high</DataTableTh>
                <DataTableTh align="right">Exposure</DataTableTh>
                <DataTableTh className="w-36">Drill</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {displayRows.length === 0 ? (
                <tr>
                  <td colSpan={6} className="crt-num px-4 py-10 text-center text-xs text-muted-foreground">
                    {processLens && rows.length
                      ? `No rows for process “${processLens}” in this reporting context.`
                      : "No readiness rows match the current context."}
                  </td>
                </tr>
              ) : (
                displayRows.map((r, i) => (
                  <DataTableRow key={`${r.entity}-${r.process}-${i}`} testId={`readiness-row-${r.entity}-${i}`}>
                    <DataTableTd className="crt-num text-xs">{r.entity}</DataTableTd>
                    <DataTableTd className="text-sm text-foreground">{r.process}</DataTableTd>
                    <DataTableTd align="right" className={clsx("crt-num text-sm font-medium tabular-nums", cellTone(r))}>
                      {r.readiness?.toFixed?.(1) ?? r.readiness}
                    </DataTableTd>
                    <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                      {r.open_high ?? "—"}
                    </DataTableTd>
                    <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                      {r.exposure != null ? fmtUSD(r.exposure) : "—"}
                    </DataTableTd>
                    <DataTableTd>
                      <button
                        type="button"
                        className="crt-num text-[10px] uppercase tracking-wider text-primary hover:underline"
                        onClick={() =>
                          nav(
                            hrefWithMasterParams(
                              `/app/cases?entity=${encodeURIComponent(r.entity)}&process=${encodeURIComponent(r.process)}`,
                            ),
                          )
                        }
                      >
                        Cases →
                      </button>
                    </DataTableTd>
                  </DataTableRow>
                ))
              )}
            </DataTableBody>
          </DataTable>
        </SectionCard>
      </div>
    </PageShell>
  );
}
