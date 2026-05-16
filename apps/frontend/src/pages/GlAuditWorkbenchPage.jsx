import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useMastersFilters } from "../lib/MastersFilterContext";
import { drillTargetExceptionListRow, useWorkbenchRowDrill } from "../lib/workbenchDrillNav";
import { RC_TICK, rcTooltipStyle } from "../lib/rechartsTheme";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import { StatCard } from "../components/StatCard";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { fmtUSD, fmtDate } from "../lib/format";

/** Resolve a journal id for `/app/drill/journal/:id` from `/gl/transactions` rows (journals vs generic transactions). */
function journalDrillIdFromGlTxn(row, source) {
  if (!row) return null;
  if (source === "journals") return row.id || null;
  const linked =
    row.journal_id ||
    row.journalId ||
    row.linked_journal_id ||
    row.ref_journal_id ||
    row.reference_journal_id ||
    null;
  if (linked) return linked;
  const id = row.id;
  if (typeof id === "string" && id.startsWith("JE-")) return id;
  return null;
}

export default function GlAuditWorkbenchPage() {
  const { drillNavigate, drillToTarget } = useWorkbenchRowDrill();
  const { entityCode, periodExplicit } = useMastersFilters();
  const [d, setD] = useState(null);

  const params = useDashboardFilterParams();
  useEffect(() => {
    const acctParams = { ...params, limit: 20, offset: 0 };
    const txnParams = { ...params, limit: 25, offset: 0 };
    const anomalyParams = { ...params, limit: 50 };
    Promise.all([
      http.get("/gl/summary", { params }),
      http.get("/gl/accounts", { params: acctParams }),
      http.get("/gl/transactions", { params: txnParams }),
      http.get("/gl/anomalies", { params: anomalyParams }),
      http.get("/gl/movement-analysis", { params }),
    ])
      .then(([s, a, tx, anom, mov]) =>
        setD({
          summary: s.data,
          accounts: a.data?.items || [],
          transactions: tx.data?.items || [],
          txnSource: tx.data?.source || "journals",
          anomalies: anom.data?.items || [],
          anomalyCount: anom.data?.count ?? 0,
          anomalySource: anom.data?.source || "",
          movement: mov.data?.items || [],
          movementSource: mov.data?.source || "",
        }),
      )
      .catch(() => toast.error("Failed to load GL audit workbench"));
  }, [params]);

  const onTxnRowClick = useCallback(
    (row) => {
      const jid = journalDrillIdFromGlTxn(row, d?.txnSource);
      if (!jid) {
        toast.message("No journal drill target for this row.");
        return;
      }
      drillNavigate("journal", jid);
    },
    [d?.txnSource, drillNavigate],
  );

  const onAnomalyRowClick = useCallback(
    (row) => {
      const target = drillTargetExceptionListRow(row);
      if (target) drillToTarget(target);
      else toast.message("No drill path for this exception.");
    },
    [drillToTarget],
  );

  const movementChartData = useMemo(() => {
    const rows = d?.movement;
    if (!Array.isArray(rows)) return [];
    return rows.map((r) => ({
      ...r,
      label: r.date && r.date !== "unknown" ? String(r.date).slice(0, 10) : "—",
    }));
  }, [d?.movement]);

  if (!d) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="gl-audit-loading">
        Loading GL audit workbench…
      </div>
    );
  }

  const k = d.summary?.kpis || {};

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="gl-audit-page" data-gl-audit-surface="true">
        <PageHeader
          kicker="GENERAL LEDGER · PHASE 15"
          title="GL audit workbench"
          subtitle="Summary + account sample — APIs: /gl/summary · /gl/accounts · /gl/transactions · /gl/anomalies · /gl/movement-analysis."
        />

        <MastersFilterStrip className="mb-6" />
        {(entityCode || periodExplicit) && (
          <p className="crt-num mb-4 text-[10px] uppercase tracking-wider text-muted-foreground">
            GL scope follows entity and period when pinned in masters.
          </p>
        )}

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          <StatCard label="GL txns (sample)" value={k.txn_count} testId="gl-kpi-txn-count" />
          <StatCard label="GL amount (sample)" value={fmtUSD(k.total_amount)} testId="gl-kpi-total-amount" />
          <StatCard
            label="GL-linked exceptions"
            value={d.anomalyCount ?? 0}
            subtle={d.anomalySource || undefined}
            testId="gl-kpi-anomaly-count"
          />
          <StatCard
            label="Movement days (bucketed)"
            value={d.movement?.length ?? 0}
            subtle={d.movementSource ? `From ${d.movementSource}` : undefined}
            testId="gl-kpi-movement-days"
          />
        </div>

        <SectionCard
          kicker="MOVEMENT"
          title="GL movement by day"
          subtitle="Net posting amounts summed by calendar day from the movement-analysis sample (up to 500 txns; respects masters)."
          className="mb-8"
          data-testid="gl-movement-section"
        >
          {movementChartData.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No daily buckets in scope — widen entity/period or confirm journals/transactions exist for the window.
            </p>
          ) : (
            <>
              <div className="h-[220px] w-full mb-4" data-testid="gl-movement-chart">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={movementChartData} margin={{ top: 8, right: 8, left: 8, bottom: 40 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                    <XAxis dataKey="label" tick={RC_TICK} interval={0} angle={-35} textAnchor="end" height={48} />
                    <YAxis tick={RC_TICK} width={52} />
                    <Tooltip
                      contentStyle={rcTooltipStyle()}
                      formatter={(value) => [fmtUSD(value), "Net amount"]}
                      labelFormatter={(_l, payload) =>
                        payload?.[0]?.payload?.date && payload[0].payload.date !== "unknown"
                          ? payload[0].payload.date
                          : "Date"
                      }
                    />
                    <Bar dataKey="amount" fill="hsl(var(--chart-1))" radius={[3, 3, 0, 0]} name="Amount" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="crt-overline mb-2 text-muted-foreground">Daily totals (table)</div>
              <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[32vh]" testId="gl-movement-table">
                <DataTableHead>
                  <tr>
                    <DataTableTh>Posting date</DataTableTh>
                    <DataTableTh align="right">Net amount</DataTableTh>
                  </tr>
                </DataTableHead>
                <DataTableBody>
                  {d.movement.map((r) => (
                    <DataTableRow key={r.date}>
                      <DataTableTd className="crt-num text-xs text-muted-foreground">{r.date}</DataTableTd>
                      <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                        {fmtUSD(r.amount)}
                      </DataTableTd>
                    </DataTableRow>
                  ))}
                </DataTableBody>
              </DataTable>
            </>
          )}
        </SectionCard>

        <SectionCard
          kicker="ANOMALIES"
          title="GL control exceptions"
          subtitle="Open-style exceptions whose control code starts with C-GL- (manual journals, backdating, privileged activity, etc.). Row click drills to exception or linked source record."
          className="mb-8"
          data-testid="gl-anomalies-section"
        >
          {(d.anomalies || []).length === 0 ? (
            <p className="text-sm text-muted-foreground">No GL-linked exceptions in the current scope.</p>
          ) : (
            <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[48vh]" testId="gl-anomalies-table">
              <DataTableHead>
                <tr>
                  <DataTableTh>Control</DataTableTh>
                  <DataTableTh>Title</DataTableTh>
                  <DataTableTh>Entity</DataTableTh>
                  <DataTableTh>Severity</DataTableTh>
                  <DataTableTh>Status</DataTableTh>
                  <DataTableTh align="right">Exposure</DataTableTh>
                  <DataTableTh>Detected</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {d.anomalies.map((ex) => {
                  const drillable = Boolean(drillTargetExceptionListRow(ex));
                  return (
                    <DataTableRow
                      key={ex.id}
                      testId={`gl-anomaly-${encodeURIComponent(String(ex.id))}`}
                      onClick={drillable ? () => onAnomalyRowClick(ex) : undefined}
                    >
                      <DataTableTd className="crt-num text-xs text-muted-foreground">{ex.control_code || "—"}</DataTableTd>
                      <DataTableTd className="text-sm text-foreground max-w-[280px] truncate">
                        <span title={typeof ex.title === "string" ? ex.title : ""}>{ex.title || "—"}</span>
                      </DataTableTd>
                      <DataTableTd className="crt-num text-xs text-muted-foreground">
                        {ex.entity_code || ex.entity || "—"}
                      </DataTableTd>
                      <DataTableTd className="crt-num text-xs uppercase text-muted-foreground">{ex.severity || "—"}</DataTableTd>
                      <DataTableTd className="crt-num text-xs text-muted-foreground">{ex.status || "—"}</DataTableTd>
                      <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                        {fmtUSD(ex.financial_exposure)}
                      </DataTableTd>
                      <DataTableTd className="crt-num text-xs text-muted-foreground">{fmtDate(ex.detected_at)}</DataTableTd>
                    </DataTableRow>
                  );
                })}
              </DataTableBody>
            </DataTable>
          )}
        </SectionCard>

        <SectionCard kicker="MASTER DATA" title="GL accounts (seeded sample)">
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[40vh]" testId="gl-accounts-table">
            <DataTableHead>
              <tr>
                <DataTableTh align="center">Code</DataTableTh>
                <DataTableTh align="center">Name</DataTableTh>
                <DataTableTh align="center">Entity</DataTableTh>
                <DataTableTh align="center">Type</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {d.accounts.length === 0 ? (
                <tr>
                  <td colSpan={4} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                    No GL accounts in scope.
                  </td>
                </tr>
              ) : null}
              {d.accounts.map((r) => (
                <DataTableRow key={r.id || r.account_code} testId={`gl-acct-${r.account_code || r.id}`}>
                  <DataTableTd align="center" className="crt-num text-xs text-muted-foreground">
                    {r.account_code || "—"}
                  </DataTableTd>
                  <DataTableTd align="center" className="text-sm text-foreground">
                    {r.account_name || "—"}
                  </DataTableTd>
                  <DataTableTd align="center" className="crt-num text-xs text-muted-foreground">
                    {r.entity_code || "—"}
                  </DataTableTd>
                  <DataTableTd align="center" className="crt-num text-xs uppercase text-muted-foreground">
                    {r.account_type || "—"}
                  </DataTableTd>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </SectionCard>

        <div id="gl-journal-lines" className="mt-6">
          <SectionCard kicker="POSTINGS" title="GL postings / journal lines (sample)">
            <p className="crt-num mb-3 text-[10px] uppercase tracking-wider text-muted-foreground">
              Row click opens journal drill when a journal id is available (source: {d.txnSource || "—"}).
            </p>
            <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[48vh]" testId="gl-txns-table">
              <DataTableHead>
                <tr>
                  <DataTableTh>Ref / id</DataTableTh>
                  <DataTableTh>Entity</DataTableTh>
                  <DataTableTh>Date</DataTableTh>
                  <DataTableTh align="right">Amount</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {(d.transactions || []).length === 0 ? (
                  <tr>
                    <td colSpan={4} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                      No postings in scope.
                    </td>
                  </tr>
                ) : null}
                {(d.transactions || []).map((t) => {
                  const ref = t.journal_number || t.reference || t.id || "—";
                  const amt = t.total_amount ?? t.amount;
                  const dt = t.posting_date || t.txn_date;
                  const drillable = Boolean(journalDrillIdFromGlTxn(t, d.txnSource));
                  return (
                    <DataTableRow
                      key={t.id || ref}
                      testId={`gl-txn-${encodeURIComponent(String(t.id || ref))}`}
                      onClick={drillable ? () => onTxnRowClick(t) : undefined}
                    >
                      <DataTableTd className="text-sm text-foreground">{ref}</DataTableTd>
                      <DataTableTd className="crt-num text-xs text-muted-foreground">{t.entity || t.entity_code || "—"}</DataTableTd>
                      <DataTableTd className="crt-num text-xs text-muted-foreground">{fmtDate(dt)}</DataTableTd>
                      <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                        {fmtUSD(amt)}
                      </DataTableTd>
                    </DataTableRow>
                  );
                })}
              </DataTableBody>
            </DataTable>
          </SectionCard>
        </div>
      </div>
    </PageShell>
  );
}
