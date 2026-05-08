/** Recharts + theme tokens (axis/grid/tooltip). */

export const RC_STROKE = "hsl(var(--border))";

export const RC_TICK = {
  fill: "hsl(var(--muted-foreground))",
  fontSize: 11,
  fontFamily: "'JetBrains Mono', ui-monospace, monospace",
};

export function rcTooltipStyle() {
  return {
    background: "hsl(var(--card))",
    border: "1px solid hsl(var(--border))",
    borderRadius: "var(--radius)",
    color: "hsl(var(--card-foreground))",
    fontFamily: "'JetBrains Mono', ui-monospace, monospace",
    fontSize: 11,
  };
}
