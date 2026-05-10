import React, { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useMastersFilters } from "../lib/MastersFilterContext";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import { StatCard } from "../components/StatCard";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { SeverityBadge } from "../components/Badges";
import { fmtUSD, fmtDateTime } from "../lib/format";

export default function TreasuryPage() {
  const { pathname } = useLocation();
  const isPhase11CashForecastRoute = pathname.includes("/treasury/cash-forecast");
  const [d, setD] = useState(null);
  const { entityCode, periodExplicit, departmentId, costCenterId } = useMastersFilters();

  const params = useDashboardFilterParams();
  useEffect(() => {
    http
      .get("/dashboard/treasury", { params })
      .then((r) => setD(r.data))
      .catch(() => toast.error("Failed to load treasury dashboard"));
  }, [params]);

  if (!d) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="treasury-loading">
        Loading treasury view…
      </div>
    );
  }

  const k = d.kpis || {};

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div
        data-testid="treasury-page"
        {...(isPhase11CashForecastRoute ? { "data-cash-forecast-surface": "true" } : {})}
      >
        <PageHeader
          kicker={isPhase11CashForecastRoute ? "CASH FORECAST · PHASE 11" : "TREASURY"}
          title={isPhase11CashForecastRoute ? "13-week runway & liquidity context" : "Cash + bank governance"}
          subtitle={
            isPhase11CashForecastRoute
              ? "Cash forecast deep-link — treasury dashboard + APIs: /treasury/cash-position · /treasury/forecast-13-week."
              : "Bank activity, off-hours wires, FX deviations, and treasury risk signals (Slice 6)."
          }
        />

        <MastersFilterStrip className="mb-6" />
        {(entityCode || periodExplicit || departmentId || costCenterId) && (
          <p className="crt-num mb-4 text-[10px] uppercase tracking-wider text-muted-foreground">
            Bank activity is scoped by entity + period when provided; department/cost center currently scope exception-derived metrics only.
          </p>
        )}

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
          <StatCard label="Bank txns" value={k.bank_txn_count} testId="kpi-bt-count" />
          <StatCard label="Cash inflow" value={fmtUSD(k.cash_inflow)} testId="kpi-inflow" />
          <StatCard label="Cash outflow" value={fmtUSD(k.cash_outflow)} severity="warning" testId="kpi-outflow" />
          <StatCard label="Net movement" value={fmtUSD(k.net_cash_movement)} testId="kpi-net" />
          <StatCard label="Off-hours wires" value={k.off_hours_wires_open} severity="critical" testId="kpi-offhours" />
          <StatCard label="FX deviations" value={k.fx_deviation_open} severity="warning" testId="kpi-fxdev" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <SectionCard kicker="BANKS" title="Bank accounts">
            <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[40vh]" testId="treasury-accounts">
              <DataTableHead>
                <tr>
                  <DataTableTh>Account</DataTableTh>
                  <DataTableTh>Currency</DataTableTh>
                  <DataTableTh>Entity</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {(d.bank_accounts || []).length === 0 ? (
                  <tr>
                    <td colSpan={3} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                      No bank accounts in scope.
                    </td>
                  </tr>
                ) : null}
                {(d.bank_accounts || []).map((a) => (
                  <DataTableRow key={a.id} testId={`acct-${a.id}`}>
                    <DataTableTd className="text-sm text-foreground">{a.bank_name || "Bank"} · {a.account_number_masked || a.account_number || a.id}</DataTableTd>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">{a.currency || "—"}</DataTableTd>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">{a.entity || "—"}</DataTableTd>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </DataTable>
          </SectionCard>

          <SectionCard kicker="ACTIVITY" title="Recent bank transactions">
            <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[40vh]" testId="treasury-txns">
              <DataTableHead>
                <tr>
                  <DataTableTh>Counterparty</DataTableTh>
                  <DataTableTh>Direction</DataTableTh>
                  <DataTableTh>When</DataTableTh>
                  <DataTableTh align="right">Amount</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {(d.recent_bank_transactions || []).length === 0 ? (
                  <tr>
                    <td colSpan={4} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                      No bank transactions in scope.
                    </td>
                  </tr>
                ) : null}
                {(d.recent_bank_transactions || []).map((t) => (
                  <DataTableRow key={t.id} testId={`txn-${t.id}`}>
                    <DataTableTd className="text-sm text-foreground">{t.counterparty || "—"}</DataTableTd>
                    <DataTableTd className="crt-num text-xs uppercase text-muted-foreground">{t.direction || "—"}</DataTableTd>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">{fmtDateTime(t.txn_ts)}</DataTableTd>
                    <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                      {fmtUSD(t.amount)}
                    </DataTableTd>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </DataTable>
          </SectionCard>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4">
          <SectionCard kicker="EXCEPTIONS" title="Off-hours wires (open)">
            <div className="space-y-2">
              {(d.off_hours_wires || []).length === 0 ? (
                <p className="crt-num px-2 py-6 text-center text-xs text-muted-foreground">No open off-hours wire exceptions in scope.</p>
              ) : null}
              {(d.off_hours_wires || []).map((e) => (
                <div
                  key={e.id}
                  className="w-full rounded-sm border border-zinc-200 bg-zinc-50/80 p-4 dark:border-zinc-800 dark:bg-zinc-900/40"
                  data-testid={`offhours-${e.id}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm text-foreground">{e.title}</div>
                      <div className="crt-num mt-0.5 text-[10px] text-muted-foreground">
                        {e.control_code} · {e.entity} · {fmtDateTime(e.detected_at)}
                      </div>
                    </div>
                    <SeverityBadge severity={e.severity} />
                  </div>
                  <div className="crt-num mt-2 text-sm tabular-nums text-[hsl(var(--destructive))]">{fmtUSD(e.financial_exposure)}</div>
                </div>
              ))}
            </div>
          </SectionCard>

          <SectionCard kicker="EXCEPTIONS" title="FX deviations (open)">
            <div className="space-y-2">
              {(d.fx_deviations || []).length === 0 ? (
                <p className="crt-num px-2 py-6 text-center text-xs text-muted-foreground">No open FX deviation exceptions in scope.</p>
              ) : null}
              {(d.fx_deviations || []).map((e) => (
                <div
                  key={e.id}
                  className="w-full rounded-sm border border-zinc-200 bg-zinc-50/80 p-4 dark:border-zinc-800 dark:bg-zinc-900/40"
                  data-testid={`fxdev-${e.id}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm text-foreground">{e.title}</div>
                      <div className="crt-num mt-0.5 text-[10px] text-muted-foreground">
                        {e.control_code} · {e.entity} · {fmtDateTime(e.detected_at)}
                      </div>
                    </div>
                    <SeverityBadge severity={e.severity} />
                  </div>
                  <div className="crt-num mt-2 text-sm tabular-nums text-[hsl(var(--destructive))]">{fmtUSD(e.financial_exposure)}</div>
                </div>
              ))}
            </div>
          </SectionCard>
        </div>
      </div>
    </PageShell>
  );
}

