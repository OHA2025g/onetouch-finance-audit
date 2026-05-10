import React, { useEffect, useState } from "react";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import { StatCard } from "../components/StatCard";
import { SeverityBadge } from "../components/Badges";
import { fmtUSD, fmtDateTime } from "../lib/format";

export default function CashConversionPage() {
  const [d, setD] = useState(null);

  const params = useDashboardFilterParams();
  useEffect(() => {
    http
      .get("/dashboard/cash-conversion", { params })
      .then((r) => setD(r.data))
      .catch(() => toast.error("Failed to load cash conversion dashboard"));
  }, [params]);

  if (!d) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="cash-conversion-loading">
        Loading cash conversion…
      </div>
    );
  }

  const k = d.kpis || {};

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="cash-conversion-page">
        <PageHeader
          kicker="WORKING CAPITAL"
          title="Cash conversion cycle"
          subtitle="DSO/DPO/CCC proxies from AR/AP invoices (Slice 8)."
        />

        <MastersFilterStrip className="mb-6" />
        <p className="crt-num mb-4 text-[10px] uppercase tracking-wider text-muted-foreground">{d.note}</p>

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
          <StatCard label="DSO (days)" value={k.dso_days ?? "—"} severity="warning" testId="kpi-dso" />
          <StatCard label="DPO (days)" value={k.dpo_days ?? "—"} testId="kpi-dpo" />
          <StatCard label="DIO (days)" value={k.dio_days ?? "—"} testId="kpi-dio" />
          <StatCard label="CCC (proxy)" value={k.ccc_days_proxy ?? "—"} severity="critical" testId="kpi-ccc" />
          <StatCard label="AR open" value={fmtUSD(k.ar_open_amount)} testId="kpi-ar-open-ccc" />
          <StatCard label="AP open" value={fmtUSD(k.ap_open_amount)} testId="kpi-ap-open-ccc" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <SectionCard kicker="WINDOW" title={`Last ${d.window_days} days billing/purchases`}>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="crt-card border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950/40">
                <div className="crt-num text-[10px] uppercase tracking-wider text-muted-foreground">AR billed (30d)</div>
                <div className="mt-1 font-display text-xl text-foreground">{fmtUSD(k.ar_billed_30d)}</div>
              </div>
              <div className="crt-card border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950/40">
                <div className="crt-num text-[10px] uppercase tracking-wider text-muted-foreground">AP invoiced (30d)</div>
                <div className="mt-1 font-display text-xl text-foreground">{fmtUSD(k.ap_invoiced_30d)}</div>
              </div>
            </div>
          </SectionCard>

          <SectionCard kicker="RISK" title="Cash conversion exceptions">
            <div className="space-y-2">
              {(d.exceptions || []).length === 0 ? (
                <p className="crt-num px-2 py-6 text-center text-xs text-muted-foreground">No cash conversion exceptions in scope.</p>
              ) : null}
              {(d.exceptions || []).map((e) => (
                <div
                  key={e.id}
                  className="w-full rounded-sm border border-zinc-200 bg-zinc-50/80 p-4 dark:border-zinc-800 dark:bg-zinc-900/40"
                  data-testid={`ccc-ex-${e.id}`}
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

        <SectionCard kicker="MODEL" title="Next improvements" className="mt-4" bodyClassName="text-sm text-muted-foreground leading-relaxed">
          Add inventory + COGS to compute real DIO, and replace AR/AP invoice proxies with ledger-based revenue/COGS once chart-of-accounts budgeting lands.
        </SectionCard>
      </div>
    </PageShell>
  );
}

