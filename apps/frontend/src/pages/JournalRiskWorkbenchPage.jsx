import React, { useEffect, useState } from "react";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useWorkbenchRowDrill } from "../lib/workbenchDrillNav";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import { StatCard } from "../components/StatCard";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { fmtUSD, fmtDate } from "../lib/format";

export default function JournalRiskWorkbenchPage() {
  const { drillToTarget } = useWorkbenchRowDrill();
  const [d, setD] = useState(null);

  const params = useDashboardFilterParams();
  useEffect(() => {
    const jParams = { ...params, limit: 25, offset: 0 };
    Promise.all([http.get("/journals/risk-rules"), http.get("/journals", { params: jParams })])
      .then(([rules, jres]) =>
        setD({
          rules: rules.data?.items || [],
          journals: jres.data?.items || [],
        }),
      )
      .catch(() => toast.error("Failed to load journal risk workbench"));
  }, [params]);

  if (!d) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="journal-risk-loading">
        Loading journal risk workbench…
      </div>
    );
  }

  const rules = d.rules;
  const journals = d.journals;

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="journal-risk-page" data-journal-risk-surface="true">
        <PageHeader
          kicker="JOURNAL RISK · PHASE 16"
          title="Journal entry risk scoring"
          subtitle="Rules + scored listing — APIs: /journals/risk-rules · /journals · /journals/high-risk · /journals/{id} · review · sample."
        />

        <MastersFilterStrip className="mb-6" />
        {params.entity_code ? (
          <p className="crt-num mb-4 text-[10px] uppercase tracking-wider text-muted-foreground">
            Journal list is filtered by entity when pinned in masters.
          </p>
        ) : null}

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          <StatCard label="Active risk rules" value={rules.length} testId="jr-kpi-rules-count" />
          <StatCard label="JEs in sample" value={journals.length} testId="jr-kpi-je-count" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <SectionCard kicker="RULES" title="Journal risk rules">
            <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[40vh]" testId="jr-rules-table">
              <DataTableHead>
                <tr>
                  <DataTableTh>Rule</DataTableTh>
                  <DataTableTh>Name</DataTableTh>
                  <DataTableTh align="right">Weight</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {rules.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                      No rules configured.
                    </td>
                  </tr>
                ) : null}
                {rules.map((r) => (
                  <DataTableRow key={r.id} testId={`jr-rule-${r.id}`}>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">{r.id}</DataTableTd>
                    <DataTableTd className="text-sm text-foreground">{r.name || "—"}</DataTableTd>
                    <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                      {r.weight ?? "—"}
                    </DataTableTd>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </DataTable>
          </SectionCard>

          <SectionCard kicker="ENTRIES" title="Journals (scored sample)">
            <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[48vh]" testId="jr-journals-table">
              <DataTableHead>
                <tr>
                  <DataTableTh>JE</DataTableTh>
                  <DataTableTh>Posted</DataTableTh>
                  <DataTableTh align="right">Amount</DataTableTh>
                  <DataTableTh align="right">Risk</DataTableTh>
                  <DataTableTh>Band</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {journals.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                      No journals in scope.
                    </td>
                  </tr>
                ) : null}
                {journals.map((j) => (
                  <DataTableRow key={j.id} testId={`jr-je-${j.id}`} onClick={() => drillToTarget(j?.id ? { type: "journal", id: String(j.id) } : null)}>
                    <DataTableTd className="text-sm text-foreground">{j.journal_number || j.id}</DataTableTd>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">{fmtDate(j.posting_date)}</DataTableTd>
                    <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                      {fmtUSD(j.total_amount)}
                    </DataTableTd>
                    <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                      {j.risk_score ?? "—"}
                    </DataTableTd>
                    <DataTableTd className="crt-num text-xs uppercase text-muted-foreground">{j.risk_band || "—"}</DataTableTd>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </DataTable>
          </SectionCard>
        </div>
      </div>
    </PageShell>
  );
}
