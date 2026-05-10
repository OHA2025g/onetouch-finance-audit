import React, { useEffect, useState } from "react";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { drillTargetRiskScoreRow, useWorkbenchRowDrill } from "../lib/workbenchDrillNav";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import { StatCard } from "../components/StatCard";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { fmtPct } from "../lib/format";

export default function RiskScoringWorkbenchPage() {
  const { drillToTarget } = useWorkbenchRowDrill();
  const [d, setD] = useState(null);

  const params = useDashboardFilterParams();
  useEffect(() => {
    Promise.all([
      http.get("/risk-intelligence/summary", { params }),
      http.get("/risk-intelligence/scores", { params: { ...params, limit: 35, offset: 0 } }),
      http.get("/risk-intelligence/heatmap", { params }),
    ])
      .then(([summary, scores, heatmap]) => {
        const bands = summary.data?.counts_by_band || {};
        setD({
          high: bands.high ?? 0,
          medium: bands.medium ?? 0,
          low: bands.low ?? 0,
          heatmapRows: heatmap.data?.items || [],
          scoreRows: scores.data?.items || [],
          scoresTotal: scores.data?.total ?? 0,
        });
      })
      .catch(() => toast.error("Failed to load risk scoring workbench"));
  }, [params]);

  if (!d) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="risk-scoring-workbench-loading">
        Loading finance risk scoring workbench…
      </div>
    );
  }

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="risk-scoring-workbench-page" data-risk-scoring-phase36-surface="true">
        <PageHeader
          kicker="RISK INTELLIGENCE · PHASE 36"
          title="Summary · scores · heatmap"
          subtitle="Entity-scored rows from `finance_risk_scores` — /risk-intelligence/summary · /scores · /heatmap · recalculate."
        />

        <MastersFilterStrip className="mb-6" />

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          <StatCard label="High band" value={d.high} testId="ri36-kpi-band-high" />
          <StatCard label="Medium band" value={d.medium} testId="ri36-kpi-band-medium" />
          <StatCard label="Low band" value={d.low} testId="ri36-kpi-band-low" />
          <StatCard label="Score rows (API total)" value={d.scoresTotal} testId="ri36-kpi-scores-total" />
        </div>

        <SectionCard kicker="HEATMAP" title="Object type × severity band">
          <DataTable className="rounded-none border-0 bg-transparent mb-8" maxHeightClassName="max-h-[32vh]" testId="ri36-heatmap-table">
            <DataTableHead>
              <tr>
                <DataTableTh>Object type</DataTableTh>
                <DataTableTh align="right">High</DataTableTh>
                <DataTableTh align="right">Medium</DataTableTh>
                <DataTableTh align="right">Low</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {d.heatmapRows.length === 0 ? (
                <tr>
                  <td colSpan={4} className="crt-num px-4 py-6 text-center text-xs text-muted-foreground">
                    No heatmap rows.
                  </td>
                </tr>
              ) : null}
              {d.heatmapRows.map((row) => (
                <DataTableRow key={row.object_type} testId={`ri36-hm-${row.object_type}`}>
                  <DataTableTd className="text-xs text-foreground">{row.object_type || "—"}</DataTableTd>
                  <DataTableTd align="right" className="crt-num tabular-nums text-xs">
                    {row.high ?? 0}
                  </DataTableTd>
                  <DataTableTd align="right" className="crt-num tabular-nums text-xs">
                    {row.medium ?? 0}
                  </DataTableTd>
                  <DataTableTd align="right" className="crt-num tabular-nums text-xs">
                    {row.low ?? 0}
                  </DataTableTd>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </SectionCard>

        <SectionCard kicker="TOP SCORES" title="Highest finance risk scores (top 35)">
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[48vh]" testId="ri36-scores-table">
            <DataTableHead>
              <tr>
                <DataTableTh>Type</DataTableTh>
                <DataTableTh>Label</DataTableTh>
                <DataTableTh>Band</DataTableTh>
                <DataTableTh align="right">Score</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {d.scoreRows.length === 0 ? (
                <tr>
                  <td colSpan={4} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                    No scores in scope.
                  </td>
                </tr>
              ) : null}
              {d.scoreRows.map((row) => (
                <DataTableRow
                  key={`${row.object_type}-${row.object_id}`}
                  testId={`ri36-sc-${row.object_type}-${row.object_id}`}
                  onClick={() => drillToTarget(drillTargetRiskScoreRow(row))}
                >
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{row.object_type || "—"}</DataTableTd>
                  <DataTableTd className="text-xs text-foreground max-w-[240px] truncate" title={row.object_label}>
                    {row.object_label || row.object_id || "—"}
                  </DataTableTd>
                  <DataTableTd className="text-xs text-foreground">{row.band || "—"}</DataTableTd>
                  <DataTableTd align="right" className="crt-num tabular-nums text-xs text-foreground">
                    {fmtPct((Number(row.score) || 0) * 100)}
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
