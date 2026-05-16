import React, { useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import { StatCard } from "../components/StatCard";
import { StatusBadge } from "../components/Badges";
import { Button } from "../components/ui/button";
import { fmtUSD } from "../lib/format";
import { errorMessageFromAxios } from "../lib/apiErrorMessage";

function safeStr(v) {
  if (v == null) return "";
  return String(v);
}

function varianceTone(varianceAmt, budgetAmt) {
  const v = Number(varianceAmt) || 0;
  const b = Math.abs(Number(budgetAmt) || 0);
  if (b > 0 && Math.abs(v) / b < 0.01) return "neutral";
  if (v > 0) return "unfavorable";
  if (v < 0) return "favorable";
  return "neutral";
}

function variancePct(varianceAmt, budgetAmt) {
  const b = Number(budgetAmt) || 0;
  if (!b) return null;
  return (Number(varianceAmt) / b) * 100;
}

function VarianceStatusPill({ row }) {
  if (row.explanation_status === "approved") {
    return (
      <span
        data-testid={`bva-status-approved-${row.id}`}
        className="status-approved inline-flex items-center rounded-sm font-mono text-[10px] uppercase tracking-wider px-2 py-0.5"
      >
        Explanation approved
      </span>
    );
  }
  const status = row.status || "open";
  return <StatusBadge status={status} />;
}

function MetricPill({ label, value, tone }) {
  const toneCls =
    tone === "budget"
      ? "border-sky-200/80 bg-sky-50/90 text-sky-950 dark:border-sky-900/60 dark:bg-sky-950/40 dark:text-sky-100"
      : tone === "actual"
        ? "border-violet-200/80 bg-violet-50/90 text-violet-950 dark:border-violet-900/60 dark:bg-violet-950/40 dark:text-violet-100"
        : tone === "favorable"
          ? "border-emerald-300/80 bg-emerald-50/95 text-emerald-900 dark:border-emerald-800/60 dark:bg-emerald-950/50 dark:text-emerald-100"
          : tone === "unfavorable"
            ? "border-rose-300/80 bg-rose-50/95 text-rose-900 dark:border-rose-900/60 dark:bg-rose-950/50 dark:text-rose-100"
            : "border-zinc-200 bg-zinc-50 text-foreground dark:border-zinc-700 dark:bg-zinc-900/50";

  return (
    <div className={clsx("rounded-md border px-3 py-2", toneCls)}>
      <div className="crt-num text-[10px] uppercase tracking-wider opacity-80">{label}</div>
      <div className="crt-num mt-1 tabular-nums text-base font-semibold tracking-tight">{value}</div>
    </div>
  );
}

function ActualVsBudgetBar({ budget, actual, tone }) {
  const b = Math.max(Number(budget) || 0, 1);
  const a = Math.max(Number(actual) || 0, 0);
  const pct = Math.min(120, (a / b) * 100);
  const barTone =
    tone === "unfavorable"
      ? "bg-gradient-to-r from-rose-400 to-rose-600"
      : tone === "favorable"
        ? "bg-gradient-to-r from-emerald-400 to-emerald-600"
        : "bg-gradient-to-r from-sky-400 to-sky-600";

  return (
    <div className="mt-3">
      <div className="mb-1 flex justify-between crt-num text-[10px] uppercase tracking-wider text-muted-foreground">
        <span>Actual vs budget</span>
        <span className="tabular-nums">{pct.toFixed(0)}% of budget</span>
      </div>
      <div className="h-2.5 overflow-hidden rounded-full bg-zinc-200/90 dark:bg-zinc-800">
        <div
          className={clsx("h-full rounded-full transition-all duration-500", barTone)}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
    </div>
  );
}

function VarianceWorkflowCard({
  row,
  commentText,
  explainText,
  onCommentChange,
  onExplainChange,
  onPostComment,
  onApprove,
}) {
  const tone = varianceTone(row.variance, row.budget_amount);
  const pct = variancePct(row.variance, row.budget_amount);
  const isApproved = row.explanation_status === "approved";
  const accentBorder =
    tone === "unfavorable"
      ? "border-l-rose-500"
      : tone === "favorable"
        ? "border-l-emerald-500"
        : "border-l-sky-500";

  const varianceLabel =
    tone === "unfavorable" ? "Unfavorable" : tone === "favorable" ? "Favorable" : "On track";

  return (
    <article
      data-testid={`bva-variance-card-${row.id}`}
      className={clsx(
        "crt-card overflow-hidden border border-zinc-200/90 bg-white/90 shadow-sm dark:border-zinc-800 dark:bg-zinc-950/80",
        "border-l-4",
        accentBorder,
      )}
    >
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-zinc-100 px-4 py-3 dark:border-zinc-800/80">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="crt-num rounded-md bg-zinc-900 px-2 py-1 text-sm font-semibold tracking-tight text-white dark:bg-zinc-100 dark:text-zinc-900">
              GL {row.gl_account || "—"}
            </span>
            {row.period_ym ? (
              <span className="crt-num rounded-sm border border-amber-300/70 bg-amber-50 px-2 py-0.5 text-[10px] uppercase tracking-wider text-amber-900 dark:border-amber-800/50 dark:bg-amber-950/40 dark:text-amber-100">
                {row.period_ym}
              </span>
            ) : (
              <span className="crt-num text-[10px] uppercase tracking-wider text-muted-foreground">No period</span>
            )}
          </div>
          <p className="mt-1.5 text-xs text-muted-foreground">
            <span
              className={clsx(
                "font-medium",
                tone === "unfavorable" && "text-rose-600 dark:text-rose-400",
                tone === "favorable" && "text-emerald-600 dark:text-emerald-400",
              )}
            >
              {varianceLabel}
            </span>
            {pct != null ? (
              <span className="crt-num ml-2 tabular-nums">
                · {pct >= 0 ? "+" : ""}
                {pct.toFixed(1)}% vs budget
              </span>
            ) : null}
          </p>
        </div>
        <VarianceStatusPill row={row} />
      </header>

      <div className="px-4 py-4">
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          <MetricPill label="Budget" value={fmtUSD(row.budget_amount)} tone="budget" />
          <MetricPill label="Actual" value={fmtUSD(row.actual_amount)} tone="actual" />
          <MetricPill
            label="Variance"
            value={fmtUSD(row.variance)}
            tone={tone === "neutral" ? "neutral" : tone}
          />
        </div>
        <ActualVsBudgetBar budget={row.budget_amount} actual={row.actual_amount} tone={tone} />
      </div>

      <div className="grid grid-cols-1 gap-3 border-t border-zinc-100 bg-zinc-50/60 p-4 dark:border-zinc-800/80 dark:bg-zinc-900/30 lg:grid-cols-2">
        <div className="rounded-lg border border-amber-200/80 bg-amber-50/50 p-3 dark:border-amber-900/40 dark:bg-amber-950/20">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-amber-200/80 text-sm dark:bg-amber-900/60" aria-hidden>
              💬
            </span>
            <div>
              <div className="crt-num text-[10px] uppercase tracking-wider text-amber-900/90 dark:text-amber-200">Comment</div>
              <p className="text-xs text-muted-foreground">Document drivers for this variance</p>
            </div>
          </div>
          {(row.comments || []).length > 0 ? (
            <ul className="mt-3 max-h-28 space-y-2 overflow-y-auto">
              {(row.comments || []).map((c) => (
                <li
                  key={c.id || `${c.at}-${c.by}`}
                  className="rounded-sm border-l-2 border-amber-400 bg-white/80 px-2 py-1.5 text-xs dark:bg-zinc-950/60"
                >
                  <span className="font-medium text-foreground">{c.by || "User"}</span>
                  <span className="text-muted-foreground"> · {c.text}</span>
                </li>
              ))}
            </ul>
          ) : null}
          <div className="mt-3 flex gap-2">
            <input
              value={commentText}
              onChange={(e) => onCommentChange(safeStr(e.target.value))}
              placeholder="Add variance comment…"
              className="w-full rounded-md border border-amber-200/90 bg-white px-3 py-2 text-sm text-foreground outline-none ring-amber-400/30 focus:ring-2 dark:border-amber-900/50 dark:bg-zinc-950"
              data-testid={`bva-comment-${row.id}`}
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="crt-num shrink-0 border-amber-300/80 bg-amber-100/80 uppercase tracking-wider hover:bg-amber-200/80 dark:border-amber-800 dark:bg-amber-950/40"
              onClick={onPostComment}
              data-testid={`bva-comment-submit-${row.id}`}
            >
              Post
            </Button>
          </div>
        </div>

        <div
          className={clsx(
            "rounded-lg border p-3",
            isApproved
              ? "border-emerald-300/80 bg-emerald-50/60 dark:border-emerald-800/50 dark:bg-emerald-950/25"
              : "border-violet-200/80 bg-violet-50/50 dark:border-violet-900/40 dark:bg-violet-950/20",
          )}
        >
          <div className="flex items-center gap-2">
            <span
              className={clsx(
                "flex h-7 w-7 items-center justify-center rounded-full text-sm",
                isApproved ? "bg-emerald-200/90 dark:bg-emerald-900/60" : "bg-violet-200/80 dark:bg-violet-900/60",
              )}
              aria-hidden
            >
              {isApproved ? "✓" : "✎"}
            </span>
            <div>
              <div className="crt-num text-[10px] uppercase tracking-wider text-violet-900/90 dark:text-violet-200">
                Explanation approval
              </div>
              <p className="text-xs text-muted-foreground">CFO gate before close sign-off</p>
            </div>
          </div>
          {isApproved && row.explanation ? (
            <p className="mt-3 rounded-md border border-emerald-200/70 bg-white/90 px-3 py-2 text-sm text-foreground dark:border-emerald-800/40 dark:bg-zinc-950/50">
              {row.explanation}
            </p>
          ) : null}
          {!isApproved ? (
            <div className="mt-3 flex gap-2">
              <input
                value={explainText}
                onChange={(e) => onExplainChange(safeStr(e.target.value))}
                placeholder="Explanation text…"
                className="w-full rounded-md border border-violet-200/90 bg-white px-3 py-2 text-sm text-foreground outline-none ring-violet-400/30 focus:ring-2 dark:border-violet-900/50 dark:bg-zinc-950"
                data-testid={`bva-explain-${row.id}`}
              />
              <Button
                type="button"
                size="sm"
                className="crt-num shrink-0 uppercase tracking-wider"
                onClick={onApprove}
                data-testid={`bva-approve-${row.id}`}
              >
                Approve
              </Button>
            </div>
          ) : (
            <p className="mt-3 text-xs font-medium text-emerald-700 dark:text-emerald-400">
              Explanation recorded — no further action required.
            </p>
          )}
        </div>
      </div>
    </article>
  );
}

export default function BudgetVsActualPage() {
  const [bva, setBva] = useState(null);
  const [vars, setVars] = useState({ items: [], total: 0 });
  const [varsLoading, setVarsLoading] = useState(true);
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
    setVarsLoading(true);
    return http
      .get("/budget/variance", { params: varianceParams })
      .then((r) => setVars({ items: r.data?.items || [], total: r.data?.total || 0 }))
      .catch((e) => toast.error(errorMessageFromAxios(e, "Failed to load variances")))
      .finally(() => setVarsLoading(false));
  };

  useEffect(() => {
    refreshVariances();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [varianceParams]);

  const workflowSummary = useMemo(() => {
    const items = vars.items || [];
    let open = 0;
    let approved = 0;
    let unfavorable = 0;
    let favorable = 0;
    for (const v of items) {
      if (v.explanation_status === "approved") approved += 1;
      else if ((v.status || "open") === "open") open += 1;
      const tone = varianceTone(v.variance, v.budget_amount);
      if (tone === "unfavorable") unfavorable += 1;
      if (tone === "favorable") favorable += 1;
    }
    return { open, approved, unfavorable, favorable, total: items.length };
  }, [vars.items]);

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
      setExplainById((p) => ({ ...p, [varianceId]: "" }));
      refreshVariances();
    } catch (e) {
      toast.error(errorMessageFromAxios(e, "Failed to approve explanation"));
    }
  };

  const k = bva?.data?.kpis || bva?.data?.kpi || bva?.kpis || {};

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="budget-vs-actual-page" data-budget-vs-actual-surface="true">
        <PageHeader
          kicker="BUDGET VS ACTUAL · PHASE 13"
          title="Variance lines & explanation gates"
          subtitle="Review favorable vs unfavorable lines, add comments, and approve explanations before close."
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

        <SectionCard kicker="VARIANCES" title="Budget variances (workflow-ready)">
          <div className="mb-5 flex flex-wrap gap-2" data-testid="bva-variance-summary">
            <span className="crt-num inline-flex items-center gap-1.5 rounded-full border border-zinc-200 bg-zinc-100 px-3 py-1 text-[10px] uppercase tracking-wider text-zinc-800 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200">
              <span className="h-2 w-2 rounded-full bg-zinc-500" aria-hidden />
              {workflowSummary.total} lines
            </span>
            <span className="crt-num inline-flex items-center gap-1.5 rounded-full border border-amber-300/70 bg-amber-50 px-3 py-1 text-[10px] uppercase tracking-wider text-amber-900 dark:border-amber-800/50 dark:bg-amber-950/40 dark:text-amber-100">
              <span className="h-2 w-2 rounded-full bg-amber-500" aria-hidden />
              {workflowSummary.open} open
            </span>
            <span className="crt-num inline-flex items-center gap-1.5 rounded-full border border-emerald-300/70 bg-emerald-50 px-3 py-1 text-[10px] uppercase tracking-wider text-emerald-900 dark:border-emerald-800/50 dark:bg-emerald-950/40 dark:text-emerald-100">
              <span className="h-2 w-2 rounded-full bg-emerald-500" aria-hidden />
              {workflowSummary.approved} approved
            </span>
            <span className="crt-num inline-flex items-center gap-1.5 rounded-full border border-rose-300/70 bg-rose-50 px-3 py-1 text-[10px] uppercase tracking-wider text-rose-900 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-100">
              <span className="h-2 w-2 rounded-full bg-rose-500" aria-hidden />
              {workflowSummary.unfavorable} unfavorable
            </span>
            <span className="crt-num inline-flex items-center gap-1.5 rounded-full border border-sky-300/70 bg-sky-50 px-3 py-1 text-[10px] uppercase tracking-wider text-sky-900 dark:border-sky-900/50 dark:bg-sky-950/40 dark:text-sky-100">
              <span className="h-2 w-2 rounded-full bg-sky-500" aria-hidden />
              {workflowSummary.favorable} favorable
            </span>
          </div>

          {varsLoading ? (
            <p className="crt-num py-12 text-center text-[10px] uppercase tracking-wider text-muted-foreground" data-testid="bva-variance-loading">
              Loading variances…
            </p>
          ) : null}

          {!varsLoading && vars.items.length === 0 ? (
            <p
              className="crt-num rounded-lg border border-dashed border-zinc-300 py-12 text-center text-xs text-muted-foreground dark:border-zinc-700"
              data-testid="bva-variance-empty"
            >
              No variances in scope. Adjust entity or period filters, or seed budget lines from Budget Master.
            </p>
          ) : null}

          <div className="space-y-4" data-testid="bva-variance-table">
            {!varsLoading
              ? vars.items.map((v) => (
                  <VarianceWorkflowCard
                    key={v.id}
                    row={v}
                    commentText={commentById[v.id] || ""}
                    explainText={explainById[v.id] || ""}
                    onCommentChange={(text) => setCommentById((p) => ({ ...p, [v.id]: text }))}
                    onExplainChange={(text) => setExplainById((p) => ({ ...p, [v.id]: text }))}
                    onPostComment={() => postComment(v.id)}
                    onApprove={() => approveExplanation(v.id)}
                  />
                ))
              : null}
          </div>
        </SectionCard>
      </div>
    </PageShell>
  );
}
