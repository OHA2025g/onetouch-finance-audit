import React from "react";
import { useNavigate } from "react-router-dom";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "./DataTable";

/** Process × entity readiness grid (shared by CFO cockpit and Risk intelligence hub — Phase 36+). */
export default function ReadinessHeatmap({ rows, buildDrillHref, onCellClick }) {
  const nav = useNavigate();

  if (!rows?.length) {
    return (
      <div
        className="crt-num px-4 py-8 text-center text-sm text-muted-foreground"
        data-testid="heatmap-empty"
      >
        No readiness heatmap rows for this slice. Broaden entity or period in the strip above.
      </div>
    );
  }

  const processes = [...new Set(rows.map((r) => r.process))].sort((a, b) => String(a).localeCompare(String(b)));
  const entities = [...new Set(rows.map((r) => r.entity))].sort((a, b) => String(a).localeCompare(String(b)));
  const map = {};
  rows.forEach((r) => {
    map[`${r.entity}::${r.process}`] = r;
  });
  const cellColor = (v) => {
    if (v == null) return "hsl(var(--muted))";
    if (v >= 85) return "rgba(48,209,88,0.20)";
    if (v >= 70) return "rgba(48,209,88,0.10)";
    if (v >= 55) return "rgba(255,159,10,0.18)";
    if (v >= 40) return "rgba(255,59,48,0.18)";
    return "rgba(255,59,48,0.35)";
  };
  const textColor = (v) => (v >= 70 ? "#30D158" : v >= 55 ? "#FF9F0A" : "#FF3B30");

  return (
    <DataTable
      testId="heatmap"
      tableClassName="border-collapse"
      className="rounded-none border-0 bg-transparent"
      maxHeightClassName="max-h-none"
      stickyHeader={false}
    >
      <DataTableHead>
        <tr>
          <DataTableTh className="py-2 pl-0 pr-3 text-left text-muted-foreground">Process / Entity</DataTableTh>
          {entities.map((e) => (
            <DataTableTh key={e} align="center" className="py-2 px-2 min-w-[90px]">
              {e}
            </DataTableTh>
          ))}
        </tr>
      </DataTableHead>
      <DataTableBody>
        {processes.map((p) => (
          <DataTableRow key={p}>
            <DataTableTd className="border-t border-zinc-200 bg-zinc-100/90 py-2 pr-3 text-sm font-medium text-foreground dark:border-zinc-800 dark:bg-zinc-900/40">
              {p}
            </DataTableTd>
            {entities.map((e) => {
              const cell = map[`${e}::${p}`];
              return (
                <DataTableTd key={e} className="!p-0 align-middle border-l border-t border-zinc-200 dark:border-zinc-800">
                  <div
                    className="flex h-14 cursor-pointer flex-col items-center justify-center transition-all hover:brightness-110"
                    style={{ background: cellColor(cell?.readiness) }}
                    data-testid={`heatmap-${e}-${p}`}
                    onClick={() => {
                      if (typeof onCellClick === "function") {
                        onCellClick(p, e, cell);
                        return;
                      }
                      const href =
                        typeof buildDrillHref === "function"
                          ? buildDrillHref(p, e)
                          : `/app/cases?process=${encodeURIComponent(p)}&entity=${encodeURIComponent(e)}`;
                      if (href) nav(href);
                    }}
                    title={cell ? `${p} · ${e} · open_high=${cell.open_high}` : "—"}
                  >
                    {cell ? (
                      <>
                        <span className="font-mono text-sm tabular-nums" style={{ color: textColor(cell.readiness) }}>
                          {cell.readiness.toFixed(0)}
                        </span>
                        <span className="crt-num text-[9px] text-foreground/70 dark:text-zinc-400">{cell.open_high} hi/crit</span>
                      </>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </div>
                </DataTableTd>
              );
            })}
          </DataTableRow>
        ))}
      </DataTableBody>
    </DataTable>
  );
}
