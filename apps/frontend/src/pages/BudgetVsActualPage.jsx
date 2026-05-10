import React, { useEffect, useMemo, useState } from "react";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { StatCard } from "../components/StatCard";
import { fmtUSD } from "../lib/format";
import { errorMessageFromAxios } from "../lib/apiErrorMessage";

function safeStr(v) {
  if (v == null) return "";
  return String(v);
}

export default function BudgetVsActualPage() {
  const [bva, setBva] = useState(null);
  const [vars, setVars] = useState({ items: [], total: 0 });
  const [commentById, setCommentById] = useState({});
  const [explainById, setExplainById] = useState({});

  const params = useDashboardFilterParams();
  const varianceParams = useMemo(() => ({ ...params, limit: 100, offset: 0 }), [params]);

  useEffect(() => {
    http
      .get("/budget/vs-actual", { params })
      .then((r) => setBva(r.data))
      .catch((e) => toast.error(errorMessageFromAxios(e, "Failed to load budget vs actual")));
  }, [params]);

  const refreshVariances = () => {
    http
      .get("/budget/variance", { params: varianceParams })
      .then((r) => setVars({ items: r.data?.items || [], total: r.data?.total || 0 }))
      .catch((e) => toast.error(errorMessageFromAxios(e, "Failed to load variances")));
  };

  useEffect(() => {
    refreshVariances();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [varianceParams]);

  const postComment = async (varianceId) => {
    const text = safeStr(commentById[varianceId]).trim();
    if (!text) {
      toast.error("Comment text is required");
      return;
    }
    try {
      await http.post(`/budget/variance/${encodeURIComponent(varianceId)}/comment`, { text });
      toast.success("Comment added");
      setCommentById((p) => ({ ...p, [varianceId]: "" }));
      refreshVariances();
    } catch (e) {
      toast.error(errorMessageFromAxios(e, "Failed to add comment"));
    }
  };

  const approveExplanation = async (varianceId) => {
    const explanation = safeStr(explainById[varianceId]).trim();
    if (!explanation) {
      toast.error("Explanation is required for approval");
      return;
    }
    try {
      await http.post(`/budget/variance/${encodeURIComponent(varianceId)}/approve-explanation`, { explanation });
      toast.success("Explanation approved");
      refreshVariances();
    } catch (e) {
      toast.error(errorMessageFromAxios(e, "Failed to approve explanation"));
    }
  };

  const k = bva?.data?.kpis || bva?.data?.kpi || bva?.kpis || {};

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="budget-vs-actual-page">
        <PageHeader
          kicker="BUDGET VS ACTUAL · PHASE 13"
          title="Variance lines & explanation gates"
          subtitle="Backed by /budget/vs-actual + /budget/variance (+ comment + approve-explanation) APIs."
        />

        <MastersFilterStrip className="mb-6" />

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
          <StatCard label="CapEx budget" value={fmtUSD(k.capex_total_budget)} testId="bva-capex-budget" />
          <StatCard label="CapEx actual" value={fmtUSD(k.capex_total_actual)} testId="bva-capex-actual" />
          <StatCard label="CapEx variance" value={fmtUSD(k.capex_total_variance)} severity="warning" testId="bva-capex-variance" />
          <StatCard label="Over-budget projects" value={k.capex_over_budget_count} severity="critical" testId="bva-over-budget" />
          <StatCard label="Variances tracked" value={vars.total} testId="bva-vars-total" />
          <StatCard label="Entity scope" value={params.entity_code || "All"} testId="bva-entity" />
        </div>

        <div className="grid grid-cols-1 gap-4">
          <SectionCard kicker="VARIANCES" title="Budget variances (workflow-ready)">
            <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[70vh]" testId="bva-variance-table">
              <DataTableHead>
                <tr>
                  <DataTableTh>Period</DataTableTh>
                  <DataTableTh>GL</DataTableTh>
                  <DataTableTh align="right">Budget</DataTableTh>
                  <DataTableTh align="right">Actual</DataTableTh>
                  <DataTableTh align="right">Variance</DataTableTh>
                  <DataTableTh>Status</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {vars.items.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                      No variances in scope.
                    </td>
                  </tr>
                ) : null}
                {vars.items.map((v) => (
                  <React.Fragment key={v.id}>
                    <DataTableRow>
                      <DataTableTd className="crt-num text-xs text-muted-foreground">{v.period_ym || "—"}</DataTableTd>
                      <DataTableTd className="text-sm text-foreground">{v.gl_account || "—"}</DataTableTd>
                      <DataTableTd align="right" className="crt-num tabular-nums text-muted-foreground">
                        {fmtUSD(v.budget_amount)}
                      </DataTableTd>
                      <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                        {fmtUSD(v.actual_amount)}
                      </DataTableTd>
                      <DataTableTd
                        align="right"
                        className={`crt-num tabular-nums ${Number(v.variance) > 0 ? "text-[hsl(var(--destructive))]" : "text-foreground"}`}
                      >
                        {fmtUSD(v.variance)}
                      </DataTableTd>
                      <DataTableTd className="crt-num text-xs text-muted-foreground">
                        {v.explanation_status === "approved" ? "approved" : v.status || "open"}
                      </DataTableTd>
                    </DataTableRow>
                    <tr>
                      <td colSpan={6} className="px-4 pb-4">
                        <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-2">
                          <div className="rounded-sm border border-zinc-200 bg-zinc-50/80 p-3 dark:border-zinc-800 dark:bg-zinc-900/40">
                            <div className="crt-num text-[10px] uppercase tracking-wider text-muted-foreground">Comment</div>
                            <div className="mt-2 flex gap-2">
                              <input
                                value={commentById[v.id] || ""}
                                onChange={(e) => setCommentById((p) => ({ ...p, [v.id]: safeStr(e.target.value) }))}
                                placeholder="Add variance comment…"
                                className="w-full rounded-sm border border-zinc-200 bg-white px-3 py-2 text-sm text-foreground outline-none dark:border-zinc-800 dark:bg-zinc-950"
                                data-testid={`bva-comment-${v.id}`}
                              />
                              <button
                                type="button"
                                onClick={() => postComment(v.id)}
                                className="crt-num shrink-0 rounded-sm border border-zinc-200 bg-white px-3 py-2 text-[10px] uppercase tracking-wider hover:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-950 dark:hover:bg-zinc-900"
                                data-testid={`bva-comment-submit-${v.id}`}
                              >
                                Post
                              </button>
                            </div>
                          </div>
                          <div className="rounded-sm border border-zinc-200 bg-zinc-50/80 p-3 dark:border-zinc-800 dark:bg-zinc-900/40">
                            <div className="crt-num text-[10px] uppercase tracking-wider text-muted-foreground">Explanation approval</div>
                            <div className="mt-2 flex gap-2">
                              <input
                                value={explainById[v.id] || ""}
                                onChange={(e) => setExplainById((p) => ({ ...p, [v.id]: safeStr(e.target.value) }))}
                                placeholder="Explanation text…"
                                className="w-full rounded-sm border border-zinc-200 bg-white px-3 py-2 text-sm text-foreground outline-none dark:border-zinc-800 dark:bg-zinc-950"
                                data-testid={`bva-explain-${v.id}`}
                              />
                              <button
                                type="button"
                                onClick={() => approveExplanation(v.id)}
                                className="crt-num shrink-0 rounded-sm border border-zinc-200 bg-white px-3 py-2 text-[10px] uppercase tracking-wider hover:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-950 dark:hover:bg-zinc-900"
                                data-testid={`bva-approve-${v.id}`}
                              >
                                Approve
                              </button>
                            </div>
                          </div>
                        </div>
                      </td>
                    </tr>
                  </React.Fragment>
                ))}
              </DataTableBody>
            </DataTable>
          </SectionCard>
        </div>
      </div>
    </PageShell>
  );
}

