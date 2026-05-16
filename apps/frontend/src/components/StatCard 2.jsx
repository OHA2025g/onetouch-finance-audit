import React from "react";
import clsx from "clsx";

function topAccent(severity) {
  if (severity === "critical") return "hsl(var(--destructive))";
  if (severity === "warning") return "hsl(var(--chart-3))";
  if (severity === "success") return "hsl(var(--chart-4))";
  return "hsl(var(--chart-1))";
}

/**
 * Control-room metric tile: `.crt-card` + top accent strip, KPI in `.crt-num`.
 */
export const StatCard = ({ label, value, unit, trend, severity, testId, subtle }) => {
  const accent = topAccent(severity);
  return (
    <div
      data-testid={testId}
      className={clsx(
        "crt-card relative overflow-hidden p-0 transition-colors duration-200",
        "hover:bg-zinc-50/80 dark:hover:bg-zinc-800/40"
      )}
    >
      <div className="h-0.5 w-full shrink-0" style={{ backgroundColor: accent }} aria-hidden />
      <div className="p-5">
        <div className="mb-3 flex items-center justify-between">
          <span className="crt-overline">{label}</span>
          {trend != null && (
            <span
              className={clsx(
                "crt-num text-[10px] font-medium uppercase tracking-wider",
                trend >= 0 ? "text-[hsl(var(--chart-4))]" : "text-[hsl(var(--destructive))]"
              )}
            >
              {trend >= 0 ? "▲" : "▼"} {Math.abs(trend).toFixed(1)}%
            </span>
          )}
        </div>
        <div className="flex items-baseline gap-2">
          <span
            className={clsx(
              "crt-num tabular-nums text-3xl font-semibold tracking-tight",
              severity === "critical" && "text-[hsl(var(--destructive))]",
              severity === "warning" && "text-[hsl(var(--chart-3))]",
              severity === "success" && "text-[hsl(var(--chart-4))]",
              !severity && "text-foreground"
            )}
          >
            {value}
          </span>
          {unit && <span className="crt-num text-xs text-muted-foreground">{unit}</span>}
        </div>
        {subtle && <div className="crt-num mt-2 text-[11px] text-muted-foreground">{subtle}</div>}
      </div>
    </div>
  );
};
