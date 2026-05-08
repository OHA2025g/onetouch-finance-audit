import React from "react";
import clsx from "clsx";

export const SeverityBadge = ({ severity, size = "sm" }) => {
  const cls = severity ? `sev-${severity}` : "sev-low";
  return (
    <span
      data-testid={`severity-badge-${severity}`}
      className={clsx(
        "inline-flex items-center font-mono uppercase tracking-wider",
        size === "sm" ? "text-[10px] px-2 py-0.5" : "text-xs px-2.5 py-1",
        cls
      )}
      style={{ letterSpacing: "0.08em" }}
    >
      {severity || "—"}
    </span>
  );
};

export const StatusBadge = ({ status }) => {
  const cls = `status-${status}`;
  const label = status === "in_progress" ? "In Progress" : status;
  return (
    <span
      data-testid={`status-badge-${status}`}
      className={clsx("inline-flex items-center font-mono uppercase tracking-wider text-[10px] px-2 py-0.5", cls)}
    >
      {label}
    </span>
  );
};

export const PriorityTag = ({ priority }) => (
  <span className="crt-num rounded-sm border border-zinc-300 bg-zinc-50 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-zinc-800 dark:border-zinc-600 dark:bg-zinc-900/60 dark:text-zinc-200">
    {priority}
  </span>
);

/** India statutory checklist penalty exposure (maps to severity palette). */
export function PenaltyRiskBadge({ risk }) {
  const sev = risk === "critical" ? "critical" : risk === "high" ? "high" : risk === "medium" ? "medium" : "low";
  return <SeverityBadge severity={sev} />;
}
