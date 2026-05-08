// Shared primitives reused across all drill renderers.
import React from "react";
import { Link } from "react-router-dom";
import { fmtUSD } from "../../lib/format";
import { SeverityBadge, StatusBadge, PriorityTag } from "../../components/Badges";
import { ArrowRight } from "@phosphor-icons/react";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../../components/DataTable";

/** Light-first drill “chrome”: zinc gutters, white panels, dark variants for `.dark`. */
export const DRILL_GRID = "gap-px border border-zinc-200 bg-zinc-200 dark:border-zinc-800 dark:bg-zinc-800";
export const DRILL_CELL = "bg-white p-5 dark:bg-zinc-900/95";
export const DRILL_TITLE = "font-display mb-3 text-base font-semibold tracking-tight text-foreground";
export const DRILL_INSET =
  "rounded-sm border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-700 dark:bg-zinc-950/60";
export const DRILL_INSET_LINK =
  "block rounded-sm border border-zinc-200 bg-zinc-50 p-4 transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-950/60 dark:hover:bg-zinc-900";

/** 2×2 (or N) stat tiles inside a drill panel */
export const DRILL_SUBGRID =
  "mt-4 grid grid-cols-2 gap-px border border-zinc-200 bg-zinc-200 dark:border-zinc-800 dark:bg-zinc-800";
export const DRILL_SUBCELL = "bg-zinc-50 p-3 dark:bg-zinc-950/60";
export const DRILL_SUBLABEL = "font-mono text-[10px] uppercase text-muted-foreground";
export const DRILL_SUBVALUE = "mt-1 text-sm text-foreground";

export const KV = ({ k, v, mono, link }) => (
  <div className="flex items-baseline justify-between gap-3 border-b border-zinc-200 py-2 last:border-0 dark:border-zinc-800">
    <span className="crt-num text-[10px] uppercase tracking-wider text-muted-foreground">{k}</span>
    {link ? (
      <Link to={link} className="max-w-[60%] truncate text-sm text-primary transition-colors hover:underline">
        {v}
      </Link>
    ) : (
      <span className={`max-w-[60%] truncate text-sm text-foreground ${mono ? "crt-num tabular-nums" : ""}`}>{v}</span>
    )}
  </div>
);

export const SectionTitle = ({ children, count }) => (
  <div className="mb-3 mt-6 flex items-center justify-between">
    <h3 className="crt-num text-[10px] uppercase tracking-[0.15em] text-muted-foreground">{children}</h3>
    {count != null && <span className="crt-num text-[10px] uppercase tracking-wider text-muted-foreground">{count}</span>}
  </div>
);

export const Stat = ({ k, v, severity }) => (
  <div className={`${DRILL_CELL} border-0`}>
    <div className="crt-num text-[10px] uppercase tracking-[0.12em] text-muted-foreground">{k}</div>
    <div
      className={`crt-num mt-2 text-2xl tabular-nums ${
        severity === "critical"
          ? "text-[hsl(var(--destructive))]"
          : severity === "success"
            ? "text-[hsl(var(--chart-4))]"
            : "text-foreground"
      }`}
    >
      {v}
    </div>
  </div>
);

export function ExceptionsTable({ exceptions, nav }) {
  if (!exceptions?.length) {
    return <div className="crt-num py-4 text-xs text-muted-foreground">No exceptions.</div>;
  }
  return (
    <DataTable maxHeightClassName="max-h-[55vh]" testId="drill-exceptions-table">
      <DataTableHead>
        <tr>
          <DataTableTh>Control</DataTableTh>
          <DataTableTh>Title</DataTableTh>
          <DataTableTh className="w-24">Severity</DataTableTh>
          <DataTableTh align="right" className="w-28">
            Exposure
          </DataTableTh>
          <DataTableTh align="right" className="w-20">
            Anomaly
          </DataTableTh>
          <DataTableTh className="w-10" />
        </tr>
      </DataTableHead>
      <DataTableBody>
        {exceptions.map(e => (
          <DataTableRow key={e.id} onClick={() => nav(`/app/evidence/${e.id}`)}>
            <DataTableTd className="crt-num text-xs text-zinc-800 dark:text-zinc-200">{e.control_code}</DataTableTd>
            <DataTableTd className="max-w-md truncate text-sm text-foreground">{e.title}</DataTableTd>
            <DataTableTd>
              <SeverityBadge severity={e.severity} />
            </DataTableTd>
            <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
              {fmtUSD(e.financial_exposure)}
            </DataTableTd>
            <DataTableTd align="right" className="crt-num tabular-nums text-[hsl(var(--chart-3))]">
              {e.anomaly_score?.toFixed(2) || "—"}
            </DataTableTd>
            <DataTableTd className="text-muted-foreground">
              <ArrowRight size={12} />
            </DataTableTd>
          </DataTableRow>
        ))}
      </DataTableBody>
    </DataTable>
  );
}

export function CasesList({ cases, nav }) {
  if (!cases?.length) {
    return <div className="crt-num py-4 text-xs text-muted-foreground">No cases opened.</div>;
  }
  return (
    <div className="space-y-1">
      {cases.map(c => (
        <div
          key={c.id}
          role="button"
          tabIndex={0}
          className="flex cursor-pointer items-center justify-between gap-2 rounded-sm border border-zinc-200 bg-zinc-50/90 p-3 transition-colors hover:bg-zinc-100 dark:border-zinc-800 dark:bg-zinc-900/50 dark:hover:bg-zinc-900/80"
          onClick={() => nav(`/app/cases/${c.id}`)}
          onKeyDown={(ev) => {
            if (ev.key === "Enter" || ev.key === " ") {
              ev.preventDefault();
              nav(`/app/cases/${c.id}`);
            }
          }}
        >
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-medium text-foreground">{c.title}</div>
            <div className="crt-num mt-0.5 text-[10px] text-muted-foreground">
              Case {c.id.slice(0, 6)} · owner {c.owner_email}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <PriorityTag priority={c.priority} />
            <StatusBadge status={c.status} />
          </div>
        </div>
      ))}
    </div>
  );
}
