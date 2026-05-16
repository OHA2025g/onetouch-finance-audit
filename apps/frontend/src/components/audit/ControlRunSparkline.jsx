import React from "react";
import { Line, LineChart, ResponsiveContainer } from "recharts";

/** Tiny exception trend for one control (from dashboard recent_runs). */
export default function ControlRunSparkline({ points = [] }) {
  if (!points.length) {
    return <span className="crt-num inline-block h-4 w-12 text-[9px] text-muted-foreground">—</span>;
  }
  const data = [...points].reverse().map((p, i) => ({ i, exc: p.exc ?? 0 }));
  return (
    <div className="h-6 w-14" aria-hidden data-testid="control-run-sparkline">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <Line
            type="monotone"
            dataKey="exc"
            stroke="hsl(var(--chart-3))"
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
