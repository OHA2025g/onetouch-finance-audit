import React, { useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useWorkbenchRowDrill } from "../lib/workbenchDrillNav";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import { StatCard } from "../components/StatCard";
import { SeverityBadge } from "../components/Badges";
import { Button } from "../components/ui/button";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { fmtUSD, fmtDate } from "../lib/format";
import { errorMessageFromAxios } from "../lib/apiErrorMessage";

function riskBandSeverity(band) {
  if (band === "high") return "critical";
  if (band === "medium") return "medium";
  return "low";
}

function RiskBandBadge({ band }) {
  const b = (band || "low").toLowerCase();
  return <SeverityBadge severity={riskBandSeverity(b)} />;
}

export default function JournalRiskWorkbenchPage() {
  const { drillToTarget } = useWorkbenchRowDrill();
  const [d, setD] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sampling, setSampling] = useState(false);

  const params = useDashboardFilterParams();

  const refresh = useCallback(() => {
    setLoading(true);
    const jParams = { ...params, limit: 50, offset: 0 };
    return Promise.all([
      http.get("/journals/risk-rules"),
      http.get("/journals/risk-summary", { params }),
      http.get("/journals", { params: jParams }),
    ])
      .then(([rulesRes, summaryRes, jres]) =>
        setD({
          rules: rulesRes.data?.items || [],
          summary: summaryRes.data || {},
          journals: jres.data?.items || [],
          journalsTotal: jres.data?.total || 0,
        }),
      )
      .catch((e) => toast.error(errorMessageFromAxios(e, "Failed to load journal risk workbench")))
      .finally(() => setLoading(false));
  }, [params]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const generateHighRiskSample = async () => {
    try {
      setSampling(true);
      const res = await http.post("/journals/sample", {
        n: 10,
        risk_band: "high",
        entity_code: params.entity_code || undefined,
      });
      const count = res.data?.count ?? 0;
      toast.success(`High-risk audit sample created (${count} JEs)`);
      refresh();
    } catch (e) {
      toast.error(errorMessageFromAxios(e, "Failed to generate sample"));
    } finally {
      setSampling(false);
    }
  };

  if (loading && !d) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="journal-risk-loading">
        Loading journal risk workbench…
      </div>
    );
  }

  const rules = d?.rules || [];
  const journals = d?.journals || [];
  const k = d?.summary?.kpis || {};
  const ruleHits = d?.summary?.rule_hits || [];
  const topPosters = d?.summary?.top_posters || [];

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="journal-risk-page" data-journal-risk-surface="true">
        <PageHeader
          kicker="JOURNAL RISK · PHASE 16"
          title="Journal entry risk scoring"
          subtitle="Portfolio KPIs, rule effectiveness, and scored journal lines — filter by entity and period above."
          right={
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={sampling}
              onClick={generateHighRiskSample}
              data-testid="jr-sample-high-risk"
            >
              {sampling ? "Sampling…" : "Sample high-risk (n=10)"}
            </Button>
          }
        />

        <MastersFilterStrip className="mb-6" />

        {params.entity_code || params.period_ym ? (
          <p className="crt-num mb-4 text-[10px] uppercase tracking-wider text-muted-foreground">
            Scope: {params.entity_code || "All entities"}
            {params.period_ym ? ` · period ${params.period_ym}` : ""}
            {k.scanned != null && k.total_journals != null ? (
              <span>
                {" "}
                · scanned {k.scanned} of {k.total_journals} JEs
              </span>
            ) : null}
          </p>
        ) : null}

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-4" data-testid="jr-kpi-strip">
          <StatCard label="Total JEs in scope" value={k.total_journals ?? "—"} testId="jr-kpi-total" />
          <StatCard label="High risk" value={k.high_count ?? 0} severity="critical" testId="jr-kpi-high-count" />
          <StatCard label="Medium risk" value={k.medium_count ?? 0} severity="warning" testId="jr-kpi-medium-count" />
          <StatCard
            label="% high risk"
            value={k.pct_high != null ? `${k.pct_high}%` : "—"}
            severity={Number(k.pct_high) >= 15 ? "critical" : "warning"}
            testId="jr-kpi-pct-high"
          />
          <StatCard
            label="$ high-risk exposure"
            value={fmtUSD(k.high_risk_amount)}
            severity="critical"
            testId="jr-kpi-high-amount"
          />
          <StatCard label="Unreviewed high" value={k.unreviewed_high_count ?? 0} severity="warning" testId="jr-kpi-unreviewed-high" />
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
          <StatCard label="$ manual journals" value={fmtUSD(k.manual_amount)} testId="jr-kpi-manual-amount" />
          <StatCard label="Manual JEs" value={k.manual_count ?? 0} testId="jr-kpi-manual-count" />
          <StatCard label="Backdated (≥10d)" value={k.backdated_count ?? 0} severity="warning" testId="jr-kpi-backdated" />
          <StatCard label="Missing approver" value={k.missing_approver_count ?? 0} severity="warning" testId="jr-kpi-missing-approver" />
          <StatCard label="Privileged posters" value={k.privileged_poster_count ?? 0} testId="jr-kpi-privileged" />
          <StatCard
            label="Avg / max score"
            value={k.avg_risk_score != null ? `${k.avg_risk_score} / ${k.max_risk_score ?? 0}` : "—"}
            testId="jr-kpi-avg-score"
          />
        </div>

        {k.top_rule_id ? (
          <p className="crt-num mb-6 text-[10px] uppercase tracking-wider text-muted-foreground" data-testid="jr-top-rule">
            Top firing rule: {k.top_rule_id} · {k.top_rule_hits} hits in scan
          </p>
        ) : null}

        <div className="mb-4 flex flex-wrap gap-2" data-testid="jr-band-summary">
          <span className="crt-num inline-flex items-center gap-1.5 rounded-full border border-rose-300/70 bg-rose-50 px-3 py-1 text-[10px] uppercase tracking-wider text-rose-900 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-100">
            High {k.high_count ?? 0}
          </span>
          <span className="crt-num inline-flex items-center gap-1.5 rounded-full border border-amber-300/70 bg-amber-50 px-3 py-1 text-[10px] uppercase tracking-wider text-amber-900 dark:border-amber-800/50 dark:bg-amber-950/40 dark:text-amber-100">
            Medium {k.medium_count ?? 0}
          </span>
          <span className="crt-num inline-flex items-center gap-1.5 rounded-full border border-emerald-300/70 bg-emerald-50 px-3 py-1 text-[10px] uppercase tracking-wider text-emerald-900 dark:border-emerald-800/50 dark:bg-emerald-950/40 dark:text-emerald-100">
            Low {k.low_count ?? 0}
          </span>
          <span className="crt-num inline-flex items-center gap-1.5 rounded-full border border-zinc-200 bg-zinc-100 px-3 py-1 text-[10px] uppercase tracking-wider text-zinc-800 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200">
            Active rules {k.active_rules ?? rules.length}
          </span>
        </div>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          <SectionCard kicker="RULES" title="Journal risk rules" className="xl:col-span-1">
            <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[36vh]" testId="jr-rules-table">
              <DataTableHead>
                <tr>
                  <DataTableTh>Rule</DataTableTh>
                  <DataTableTh>Name</DataTableTh>
                  <DataTableTh align="right">Weight</DataTableTh>
                  <DataTableTh align="right">Hits</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {rules.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                      No rules configured.
                    </td>
                  </tr>
                ) : null}
                {(ruleHits.length ? ruleHits : rules.map((r) => ({ rule_id: r.id, name: r.name, weight: r.weight, hit_count: 0 }))).map(
                  (r) => (
                    <DataTableRow key={r.rule_id || r.id} testId={`jr-rule-${r.rule_id || r.id}`}>
                      <DataTableTd className="crt-num text-xs text-muted-foreground">{r.rule_id || r.id}</DataTableTd>
                      <DataTableTd className="text-sm text-foreground">{r.name || "—"}</DataTableTd>
                      <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                        {r.weight ?? "—"}
                      </DataTableTd>
                      <DataTableTd align="right" className="crt-num tabular-nums">
                        <span
                          className={clsx(
                            "inline-block min-w-[1.5rem] rounded-sm px-1.5 py-0.5 text-center text-[10px]",
                            Number(r.hit_count) > 0
                              ? "bg-amber-100 text-amber-900 dark:bg-amber-950/50 dark:text-amber-100"
                              : "text-muted-foreground",
                          )}
                        >
                          {r.hit_count ?? 0}
                        </span>
                      </DataTableTd>
                    </DataTableRow>
                  ),
                )}
              </DataTableBody>
            </DataTable>
          </SectionCard>

          <SectionCard kicker="ENTRIES" title="Journals (scored sample)" className="xl:col-span-2">
            <p className="crt-num mb-3 text-[10px] uppercase tracking-wider text-muted-foreground">
              Showing {journals.length} of {d?.journalsTotal ?? journals.length} · click row to drill
            </p>
            <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[52vh]" testId="jr-journals-table">
              <DataTableHead>
                <tr>
                  <DataTableTh>JE</DataTableTh>
                  <DataTableTh>Posted</DataTableTh>
                  <DataTableTh align="right">Amount</DataTableTh>
                  <DataTableTh align="right">Risk</DataTableTh>
                  <DataTableTh>Band</DataTableTh>
                  <DataTableTh>Rules hit</DataTableTh>
                  <DataTableTh>Manual</DataTableTh>
                  <DataTableTh>Review</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {journals.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                      No journals in scope.
                    </td>
                  </tr>
                ) : null}
                {journals.map((j) => (
                  <DataTableRow
                    key={j.id}
                    testId={`jr-je-${j.id}`}
                    onClick={() => drillToTarget(j?.id ? { type: "journal", id: String(j.id) } : null)}
                  >
                    <DataTableTd>
                      <div className="text-sm font-medium text-foreground">{j.journal_number || j.id}</div>
                      {j.created_by ? (
                        <div className="crt-num text-[10px] text-muted-foreground">{j.created_by}</div>
                      ) : null}
                    </DataTableTd>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">
                      {fmtDate(j.posting_date)}
                      {j.backdated_days > 0 ? (
                        <span className="ml-1 text-amber-600 dark:text-amber-400">+{j.backdated_days}d</span>
                      ) : null}
                    </DataTableTd>
                    <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                      {fmtUSD(j.total_amount)}
                    </DataTableTd>
                    <DataTableTd
                      align="right"
                      className={clsx(
                        "crt-num tabular-nums font-semibold",
                        j.risk_band === "high" && "text-[hsl(var(--destructive))]",
                        j.risk_band === "medium" && "text-[hsl(var(--chart-3))]",
                      )}
                    >
                      {j.risk_score ?? "—"}
                    </DataTableTd>
                    <DataTableTd>
                      <RiskBandBadge band={j.risk_band} />
                    </DataTableTd>
                    <DataTableTd className="crt-num text-[10px] text-muted-foreground">
                      {(j.rules_hit || []).length ? (j.rules_hit || []).join(", ") : "—"}
                    </DataTableTd>
                    <DataTableTd className="crt-num text-xs uppercase text-muted-foreground">{j.is_manual ? "Yes" : "No"}</DataTableTd>
                    <DataTableTd className="crt-num text-[10px] uppercase">
                      {j.reviewed ? (
                        <span className="text-emerald-600 dark:text-emerald-400">Done</span>
                      ) : (
                        <span className="text-amber-600 dark:text-amber-400">Open</span>
                      )}
                    </DataTableTd>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </DataTable>
          </SectionCard>
        </div>

        {topPosters.length > 0 ? (
          <div className="mt-4">
            <SectionCard kicker="POSTERS" title="Top high-risk posters (by $ exposure)">
              <DataTable className="rounded-none border-0 bg-transparent" testId="jr-top-posters-table">
                <DataTableHead>
                  <tr>
                    <DataTableTh>User</DataTableTh>
                    <DataTableTh align="right">High-risk JEs</DataTableTh>
                    <DataTableTh align="right">$ exposure</DataTableTh>
                  </tr>
                </DataTableHead>
                <DataTableBody>
                  {topPosters.map((p) => (
                    <DataTableRow key={p.created_by}>
                      <DataTableTd className="text-sm text-foreground">{p.created_by}</DataTableTd>
                      <DataTableTd align="right" className="crt-num tabular-nums">
                        {p.high_risk_count}
                      </DataTableTd>
                      <DataTableTd align="right" className="crt-num tabular-nums">
                        {fmtUSD(p.high_risk_amount)}
                      </DataTableTd>
                    </DataTableRow>
                  ))}
                </DataTableBody>
              </DataTable>
            </SectionCard>
          </div>
        ) : null}
      </div>
    </PageShell>
  );
}
