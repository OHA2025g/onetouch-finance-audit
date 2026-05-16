import React, { useMemo, useState } from "react";
import { http } from "../../lib/api";
import { toast } from "sonner";
import { useDashboardFilterParams } from "../../lib/useDashboardFilterParams";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { RC_STROKE, RC_TICK, rcTooltipStyle } from "../../lib/rechartsTheme";
import { SectionCard } from "../PageShell";
import { StatCard } from "../StatCard";

function workflowLabel(s) {
  if (!s) return "Not started";
  if (s === "draft") return "Draft";
  if (s === "prepared") return "Prepared";
  if (s === "reviewed") return "Reviewed";
  if (s === "approved") return "Approved";
  return s;
}

/** Light-theme form controls (readable on light shells; `dark:` for dark mode). */
const INPUT =
  "mt-1 w-full h-9 rounded-sm border border-zinc-300 bg-white px-2.5 text-sm text-foreground shadow-sm outline-none placeholder:text-zinc-400 focus:border-primary focus:ring-1 focus:ring-primary dark:border-zinc-600 dark:bg-zinc-950 dark:text-zinc-100 dark:placeholder:text-zinc-500";
const TEXTAREA =
  "mt-1 w-full min-h-[5rem] resize-y rounded-sm border border-zinc-300 bg-white px-2.5 py-2 text-sm text-foreground shadow-sm outline-none placeholder:text-zinc-400 focus:border-primary focus:ring-1 focus:ring-primary dark:border-zinc-600 dark:bg-zinc-950 dark:text-zinc-100 dark:placeholder:text-zinc-500";

/**
 * Materiality Engine — linked to engagement; benchmarks, override, approval, exception flags.
 */
export default function MaterialitySetupPanel({ engagementId, materiality, onMaterialityUpdated, currentUserEmail }) {
  const dashboardParams = useDashboardFilterParams();
  const [saving, setSaving] = useState(false);
  const [workflowBusy, setWorkflowBusy] = useState(false);
  const email = currentUserEmail || "auditor@onetouch.ai";

  const chartRows = useMemo(() => {
    const bm = materiality?.benchmarks;
    if (bm && bm.length) {
      return bm.map((b) => ({ name: b.label?.slice(0, 28) || b.key, amount: b.amount, selected: b.selected }));
    }
    const opts = materiality?.benchmark_options;
    if (!opts) return [];
    return Object.entries(opts).map(([k, v]) => ({
      name: k.replace(/_/g, " "),
      amount: v,
      selected: k === materiality?.benchmark_selected,
    }));
  }, [materiality]);

  const save = async (ev) => {
    ev.preventDefault();
    const fd = new FormData(ev.target);
    const overrideRaw = fd.get("override_amount");
    const overrideNum = overrideRaw !== "" && overrideRaw != null ? parseFloat(String(overrideRaw), 10) : null;
    const reason = (fd.get("override_reason") || "").toString().trim();
    if (overrideNum != null && !Number.isNaN(overrideNum) && Math.abs(overrideNum) > 1e-9 && !reason) {
      toast.error("Justification required when using manual override amount");
      return;
    }
    const body = {
      revenue: parseFloat(fd.get("revenue") || "0") || null,
      profit_before_tax: parseFloat(fd.get("profit_before_tax") || "0") || null,
      total_assets: parseFloat(fd.get("total_assets") || "0") || null,
      gross_expenses: parseFloat(fd.get("gross_expenses") || "0") || null,
      benchmark_selected: fd.get("benchmark_selected") || null,
      override_amount: overrideNum != null && !Number.isNaN(overrideNum) ? overrideNum : null,
      override_reason: reason || null,
    };
    setSaving(true);
    try {
      const { data } = await http.post(`/audit-engagements/${encodeURIComponent(engagementId)}/materiality`, body, { params: dashboardParams });
      onMaterialityUpdated(data);
      toast.success("Materiality calculated");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Save failed");
    }
    setSaving(false);
  };

  const workflow = async (approval_status, extra = {}) => {
    if (!materiality?.id) {
      toast.error("Save materiality first");
      return;
    }
    setWorkflowBusy(true);
    try {
      const { data } = await http.post(
        `/materiality/${materiality.id}/approve`,
        {
          approval_status,
          ...extra,
        },
        { params: dashboardParams },
      );
      onMaterialityUpdated(data);
      toast.success(`Status: ${workflowLabel(approval_status)}`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Workflow update failed");
    }
    setWorkflowBusy(false);
  };

  const flags = materiality?.exception_materiality_flags || [];
  const perf = materiality?.performance_materiality;
  const trivial = materiality?.clearly_trivial_threshold;
  const benchmarks = materiality?.benchmarks || [];

  return (
    <div className="space-y-6" data-testid="materiality-setup-panel">
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Reviewer workflow</div>
          <div className="mt-1 flex flex-wrap gap-2 items-center">
            <span className="rounded-sm border border-zinc-200 bg-zinc-50 px-2 py-1 font-mono text-[10px] uppercase text-foreground dark:border-zinc-700 dark:bg-zinc-800/80">
              {workflowLabel(materiality?.approval_status)}
            </span>
            {materiality?.prepared_by ? (
              <span className="font-mono text-[10px] text-muted-foreground">Prep: {materiality.prepared_by}</span>
            ) : null}
            {materiality?.reviewed_by ? (
              <span className="font-mono text-[10px] text-muted-foreground">Rev: {materiality.reviewed_by}</span>
            ) : null}
            {materiality?.approved_by ? (
              <span className="font-mono text-[10px] text-muted-foreground">App: {materiality.approved_by}</span>
            ) : null}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={workflowBusy || !materiality?.id}
            className="h-9 rounded-sm border border-zinc-300 bg-white px-3 font-mono text-[10px] uppercase text-foreground transition-colors hover:bg-zinc-50 disabled:opacity-40 dark:border-zinc-600 dark:bg-zinc-900 dark:hover:bg-zinc-800"
            onClick={() => workflow("prepared", { prepared_by: email })}
          >
            Mark prepared
          </button>
          <button
            type="button"
            disabled={workflowBusy || !materiality?.id}
            className="h-9 rounded-sm border border-zinc-300 bg-white px-3 font-mono text-[10px] uppercase text-foreground transition-colors hover:bg-zinc-50 disabled:opacity-40 dark:border-zinc-600 dark:bg-zinc-900 dark:hover:bg-zinc-800"
            onClick={() => workflow("reviewed", { reviewed_by: email })}
          >
            Mark reviewed
          </button>
          <button
            type="button"
            disabled={workflowBusy || !materiality?.id}
            className="h-9 rounded-sm border border-primary bg-primary px-3 font-mono text-[10px] uppercase text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-40"
            onClick={() => workflow("approved", { approved_by: email })}
          >
            Mark approved
          </button>
        </div>
      </div>

      {benchmarks.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
          {benchmarks.map((b) => (
            <StatCard
              key={b.key}
              label={b.label}
              value={typeof b.amount === "number" ? b.amount.toLocaleString() : String(b.amount ?? "")}
              subtle={b.selected ? "Selected for overall materiality" : undefined}
              severity={b.selected ? "success" : undefined}
              testId={`benchmark-${b.key}`}
            />
          ))}
        </div>
      ) : null}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <SectionCard kicker="INPUTS" title="Materiality setup" bodyClassName="p-4 md:p-6">
          <form key={materiality?.id || "new"} className="space-y-3" onSubmit={save}>
            <div className="grid grid-cols-2 gap-2">
              <label className="text-xs font-mono text-muted-foreground">
                Revenue
                <input name="revenue" type="number" step="any" className={INPUT} defaultValue={materiality?.revenue ?? ""} />
              </label>
              <label className="text-xs font-mono text-muted-foreground">
                PBT
                <input name="profit_before_tax" type="number" step="any" className={INPUT} defaultValue={materiality?.profit_before_tax ?? ""} />
              </label>
              <label className="text-xs font-mono text-muted-foreground">
                Total assets
                <input name="total_assets" type="number" step="any" className={INPUT} defaultValue={materiality?.total_assets ?? ""} />
              </label>
              <label className="text-xs font-mono text-muted-foreground">
                Gross expenses
                <input name="gross_expenses" type="number" step="any" className={INPUT} defaultValue={materiality?.gross_expenses ?? ""} />
              </label>
            </div>
            <label className="block text-xs font-mono text-muted-foreground">
              Benchmark
              <select name="benchmark_selected" className={INPUT} defaultValue={materiality?.benchmark_selected || ""}>
                <option value="">Auto (lowest positive benchmark)</option>
                <option value="five_pct_pbt">5% PBT</option>
                <option value="one_pct_revenue">1% revenue</option>
                <option value="one_pct_assets">1% assets</option>
                <option value="half_pct_expenses">0.5% gross expenses</option>
              </select>
            </label>
            <label className="block text-xs font-mono text-muted-foreground">
              Manual override (final materiality amount)
              <input
                name="override_amount"
                type="number"
                step="any"
                className={INPUT}
                defaultValue={materiality?.override_amount ?? ""}
                placeholder="Leave blank to use calculated benchmark"
              />
            </label>
            <label className="block text-xs font-mono text-muted-foreground">
              Override justification (required if override set)
              <textarea
                name="override_reason"
                rows={3}
                className={TEXTAREA}
                defaultValue={materiality?.override_reason ?? ""}
                placeholder="e.g. cyclical loss year — use revenue benchmark"
              />
            </label>
            <button
              type="submit"
              disabled={saving}
              className="h-10 rounded-sm border border-primary bg-primary px-4 font-mono text-xs font-medium uppercase tracking-wider text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {saving ? "Saving…" : "Calculate & save"}
            </button>
          </form>
        </SectionCard>

        <div className="space-y-4">
          <SectionCard kicker="RESULT" title="Determined thresholds" bodyClassName="p-4 md:p-6 space-y-3 text-sm">
            {materiality ? (
              <>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <StatCard label="Calculated (benchmark)" value={Number(materiality.calculated_materiality || 0).toLocaleString()} testId="mat-calc" />
                  <StatCard label="Final materiality" value={Number(materiality.final_materiality || 0).toLocaleString()} severity="warning" testId="mat-final" />
                  <StatCard label="Clearly trivial" value={Number(materiality.trivial_threshold || 0).toLocaleString()} subtle="~5% of final" testId="mat-trivial" />
                </div>
                {perf ? (
                  <div className="rounded-sm border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-700 dark:bg-zinc-900/40">
                    <div className="font-mono text-[10px] uppercase text-muted-foreground">Performance materiality</div>
                    <div className="mt-1 font-heading text-lg text-foreground">
                      {perf.low?.toLocaleString?.()} – {perf.high?.toLocaleString?.()}{" "}
                      <span className="font-sans text-sm text-muted-foreground">(mid {perf.mid?.toLocaleString?.()})</span>
                    </div>
                    <p className="mt-2 text-xs text-muted-foreground">{perf.basis_note}</p>
                  </div>
                ) : null}
                {trivial ? <p className="text-xs text-muted-foreground">{trivial.basis_note}</p> : null}
              </>
            ) : (
              <div className="font-mono text-xs text-muted-foreground">No materiality record yet — enter benchmarks and save.</div>
            )}
          </SectionCard>

          {materiality?.impact_explanation ? (
            <SectionCard
              kicker="IMPACT"
              title="How materiality drives the audit"
              bodyClassName="p-4 text-sm leading-relaxed text-foreground"
            >
              {materiality.impact_explanation}
            </SectionCard>
          ) : null}
        </div>
      </div>

      {chartRows.length > 0 ? (
        <SectionCard kicker="VISUAL" title="Benchmark comparison" bodyClassName="p-4">
          <div className="h-56 w-full min-w-0">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartRows} margin={{ top: 8, right: 8, left: 0, bottom: 32 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={RC_STROKE} />
                <XAxis dataKey="name" tick={RC_TICK} interval={0} angle={-18} textAnchor="end" height={60} stroke={RC_STROKE} />
                <YAxis tick={RC_TICK} stroke={RC_STROKE} />
                <Tooltip contentStyle={rcTooltipStyle()} formatter={(v) => [v?.toLocaleString?.() ?? v, "Amount"]} />
                <Bar dataKey="amount" radius={[0, 0, 0, 0]}>
                  {chartRows.map((entry, i) => (
                    <Cell
                      key={i}
                      fill={entry.selected ? "hsl(var(--foreground))" : "hsl(var(--chart-1))"}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p className="mt-2 font-mono text-[10px] text-muted-foreground">
            Highlighted bar = benchmark selected for overall materiality (unless manual override applies).
          </p>
        </SectionCard>
      ) : null}

      {flags.length > 0 ? (
        <SectionCard kicker="EXCEPTIONS" title="Exposure vs materiality" bodyClassName="p-0 overflow-x-auto">
          <table className="w-full text-sm min-w-[520px]">
            <thead>
              <tr className="border-b border-zinc-200 text-left font-mono text-[10px] uppercase text-muted-foreground dark:border-zinc-700">
                <th className="p-3">Exception</th>
                <th className="p-3">Exposure</th>
                <th className="p-3">≥ trivial</th>
                <th className="p-3">≥ overall</th>
              </tr>
            </thead>
            <tbody>
              {flags.map((f) => (
                <tr key={f.exception_id || f.summary} className="border-b border-zinc-200/90 dark:border-zinc-800/80">
                  <td className="max-w-[240px] truncate p-3 text-foreground" title={f.summary}>
                    {f.summary || f.exception_id}
                  </td>
                  <td className="p-3 font-mono text-xs">{f.financial_exposure?.toLocaleString?.()}</td>
                  <td className="p-3">
                    {f.exceeds_trivial_threshold ? (
                      <span className="font-mono text-[10px] uppercase text-amber-600 dark:text-[#FF9F0A]">Watch</span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="p-3">
                    {f.exceeds_overall_materiality ? (
                      <span className="font-mono text-[10px] uppercase text-red-600 dark:text-[#FF3B30]">Flag</span>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </SectionCard>
      ) : null}
    </div>
  );
}
