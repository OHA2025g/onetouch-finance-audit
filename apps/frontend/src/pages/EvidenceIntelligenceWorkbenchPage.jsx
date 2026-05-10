import React, { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { drillTargetEvidenceQiRow, useWorkbenchRowDrill } from "../lib/workbenchDrillNav";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import { StatCard } from "../components/StatCard";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";

export default function EvidenceIntelligenceWorkbenchPage() {
  const { drillToTarget } = useWorkbenchRowDrill();
  const [searchParams] = useSearchParams();
  const documentHighlight = (searchParams.get("document") || "").trim();
  const [d, setD] = useState(null);

  const params = useDashboardFilterParams();
  useEffect(() => {
    Promise.all([
      http.get("/evidence-intelligence/quality-issues", { params: { ...params, status: "open", limit: 500, offset: 0 } }),
      http.get("/evidence-intelligence/quality-issues", { params: { ...params, status: "resolved", limit: 1, offset: 0 } }),
      http.get("/exceptions/count", { params }),
    ])
      .then(([openQi, resolvedQi, exCount]) => {
        const items = openQi.data?.items || [];
        const critical = items.filter((r) => String(r.severity || "").toLowerCase() === "critical").length;
        setD({
          openTotal: openQi.data?.total ?? 0,
          resolvedTotal: resolvedQi.data?.total ?? 0,
          exceptionsCount: exCount.data?.count ?? 0,
          criticalSample: critical,
          rows: items.slice(0, 35),
        });
      })
      .catch(() => toast.error("Failed to load evidence intelligence workbench"));
  }, [params]);

  if (!d) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="evidence-intelligence-workbench-loading">
        Loading evidence intelligence workbench…
      </div>
    );
  }

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="evidence-intelligence-workbench-page" data-evidence-intelligence-phase34-surface="true">
        <PageHeader
          kicker="EVIDENCE INTELLIGENCE · PHASE 34"
          title="Quality issues · OCR extract · links · review"
          subtitle="Open DQ rows from `/evidence-intelligence/quality-issues`; critical count is from the first page (≤500). Link targets use `/exceptions`."
        />

        <MastersFilterStrip className="mb-6" />

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          <StatCard label="Open quality issues" value={d.openTotal} testId="ei34-kpi-open-qi" />
          <StatCard label="Resolved QI (scope)" value={d.resolvedTotal} testId="ei34-kpi-resolved-qi" />
          <StatCard label="Exceptions (scope)" value={d.exceptionsCount} testId="ei34-kpi-exceptions" />
          <StatCard label="Critical (in page)" value={d.criticalSample} testId="ei34-kpi-critical-sample" />
        </div>

        <SectionCard kicker="QUALITY ISSUES" title="Open document intelligence findings (top 35)">
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[58vh]" testId="evidence-qi-table">
            <DataTableHead>
              <tr>
                <DataTableTh>Document</DataTableTh>
                <DataTableTh>Field</DataTableTh>
                <DataTableTh>Severity</DataTableTh>
                <DataTableTh>Issue</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {d.rows.length === 0 ? (
                <tr>
                  <td colSpan={4} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                    No open quality issues. Run extract (`POST /evidence-intelligence/extract`) from workflows or demos to seed rows.
                  </td>
                </tr>
              ) : null}
              {d.rows.map((row) => (
                <DataTableRow
                  key={row.id}
                  testId={`ei34-qi-${row.id}`}
                  className={
                    documentHighlight && String(row.document_id || "") === documentHighlight
                      ? "bg-primary/5 ring-1 ring-inset ring-primary/25"
                      : undefined
                  }
                  onClick={() => drillToTarget(drillTargetEvidenceQiRow(row))}
                >
                  <DataTableTd className="text-xs text-muted-foreground">{row.document_id || "—"}</DataTableTd>
                  <DataTableTd className="text-xs text-foreground">{row.field || "—"}</DataTableTd>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{row.severity || "—"}</DataTableTd>
                  <DataTableTd className="text-xs text-muted-foreground max-w-[320px] truncate" title={row.issue}>
                    {row.issue || "—"}
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
