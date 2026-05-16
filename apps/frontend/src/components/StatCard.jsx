import React from "react";
import clsx from "clsx";
import { toProperHeadingLabel } from "../lib/headingCase";

function topAccent(severity) {
  if (severity === "critical") return "hsl(var(--destructive))";
  if (severity === "warning") return "hsl(var(--chart-3))";
  if (severity === "success") return "hsl(var(--chart-4))";
  return "hsl(var(--chart-1))";
}

/**
 * Control-room metric tile: `.crt-card` + top accent strip, KPI in `.crt-num`.
 */
export const StatCard = ({ label, value, unit, trend, severity, testId, subtle, compact }) => {
  const accent = topAccent(severity);
  return (
    <div
      data-testid={testId}
      className={clsx(
        "crt-card relative min-w-0 transition-colors duration-200",
        "hover:bg-zinc-50/80 dark:hover:bg-zinc-800/40",
        compact ? "rounded-sm p-0" : "overflow-hidden p-0",
      )}
    >
      <div className="h-0.5 w-full shrink-0" style={{ backgroundColor: accent }} aria-hidden />
      <div className={clsx(compact ? "p-3 md:p-4" : "p-5")}>
        <div className={clsx("flex items-start justify-between gap-2", compact ? "mb-2" : "mb-3")}>
          <span className="crt-overline min-w-0 flex-1 leading-snug">{toProperHeadingLabel(label)}</span>
          {trend != null && (
            <span
              className={clsx(
                "crt-num shrink-0 text-[10px] font-medium tracking-wide",
                trend >= 0 ? "text-[hsl(var(--chart-4))]" : "text-[hsl(var(--destructive))]",
              )}
            >
              {trend >= 0 ? "▲" : "▼"} {Math.abs(trend).toFixed(1)}%
            </span>
          )}
        </div>
        <div className="flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-0">
          <span
            className={clsx(
              "crt-num tabular-nums font-semibold tracking-tight",
              compact ? "text-lg md:text-xl lg:text-2xl leading-snug break-words" : "text-3xl",
              severity === "critical" && "text-[hsl(var(--destructive))]",
              severity === "warning" && "text-[hsl(var(--chart-3))]",
              severity === "success" && "text-[hsl(var(--chart-4))]",
              !severity && "text-foreground",
            )}
          >
            {value}
          </span>
          {unit && <span className="crt-num text-xs text-muted-foreground">{unit}</span>}
        </div>
        {subtle && (
          <div className={clsx("crt-num text-muted-foreground", compact ? "mt-1.5 text-[10px]" : "mt-2 text-[11px]")}>
            {subtle}
          </div>
        )}
      </div>
    </div>
  );
};
