import React from "react";
import clsx from "clsx";

const STATUS_STYLES = {
  draft:
    "border border-zinc-200 bg-zinc-100 text-zinc-800 dark:border-zinc-600 dark:bg-[#262626] dark:text-[#A3A3A3]",
  planned:
    "border border-blue-200 bg-blue-50 text-blue-900 dark:border-blue-800/50 dark:bg-[#1D4ED8]/30 dark:text-[#93C5FD]",
  "in-progress":
    "border border-amber-200 bg-amber-50 text-amber-950 dark:border-amber-800/40 dark:bg-[#854D0E]/40 dark:text-[#FDE047]",
  in_progress:
    "border border-amber-200 bg-amber-50 text-amber-950 dark:border-amber-800/40 dark:bg-[#854D0E]/40 dark:text-[#FDE047]",
  completed:
    "border border-emerald-200 bg-emerald-50 text-emerald-950 dark:border-emerald-800/40 dark:bg-[#14532D]/40 dark:text-[#86EFAC]",
  archived:
    "border border-zinc-200 bg-zinc-100 text-zinc-600 dark:border-zinc-600 dark:bg-[#404040] dark:text-[#737373]",
};

export function AuditStatusBadge({ status }) {
  const raw = status || "draft";
  const s = raw === "in_progress" ? "in-progress" : raw;
  const label = s === "in-progress" || s === "in_progress" ? "In progress" : s.replace(/-/g, " ");
  return (
    <span
      data-testid={`audit-status-${s}`}
      className={clsx("rounded-sm px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider", STATUS_STYLES[s] || STATUS_STYLES.draft)}
    >
      {label}
    </span>
  );
}

const RISK_STYLES = {
  low: "border border-zinc-200 bg-zinc-100 text-zinc-800 dark:border-zinc-600 dark:bg-[#262626] dark:text-[#A3A3A3]",
  medium:
    "border border-amber-200 bg-amber-50 text-amber-950 dark:border-amber-800/35 dark:bg-[#854D0E]/35 dark:text-[#FDE047]",
  high: "border border-orange-200 bg-orange-50 text-orange-950 dark:border-orange-900/40 dark:bg-[#9A3412]/35 dark:text-[#FDBA74]",
  critical:
    "border border-red-200 bg-red-50 text-red-950 dark:border-red-900/50 dark:bg-[#7F1D1D]/50 dark:text-[#FCA5A5]",
};

export function RiskBadge({ level }) {
  const r = level || "medium";
  return (
    <span
      data-testid={`risk-badge-${r}`}
      className={clsx(
        "rounded-sm px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider",
        RISK_STYLES[r] || RISK_STYLES.medium
      )}
    >
      {r} risk
    </span>
  );
}

export function MaterialImpactBadge() {
  return (
    <span
      data-testid="material-impact-badge"
      className="rounded-sm border border-red-200 bg-red-50 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-red-900 dark:border-[#991B1B]/60 dark:bg-[#7F1D1D]/45 dark:text-[#FECACA]"
    >
      Material impact
    </span>
  );
}
