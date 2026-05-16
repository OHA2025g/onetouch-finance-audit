/** Recharts + theme tokens (axis/grid/tooltip). */

export const RC_STROKE = "hsl(var(--border))";

/** Props for Recharts `<XAxis tick={...} />` / `<YAxis tick={...} />` (flat SVG text styling). Do not assign this object to `fill`; use `{ ...RC_TICK }` or `RC_TICK.fill`. */
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
