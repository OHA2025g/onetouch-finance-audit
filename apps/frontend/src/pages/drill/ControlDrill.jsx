import React from "react";
import { fmtUSD, fmtDate, fmtDateTime, fmtNum } from "../../lib/format";
import {
  SectionTitle,
  ExceptionsTable,
  Stat,
  DRILL_GRID,
  DRILL_CELL,
  DRILL_TITLE,
  DRILL_SUBGRID,
  DRILL_SUBCELL,
  DRILL_SUBLABEL,
  DRILL_SUBVALUE,
} from "./shared";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../../components/DataTable";

export default function ControlDrill({ data, nav }) {
  const p = data.primary;
  const s = data.stats;
  return (
    <>
      <div className={`mb-6 grid grid-cols-2 md:grid-cols-4 ${DRILL_GRID}`}>
        <Stat k="Exceptions" v={fmtNum(s.exception_count)} severity={s.exception_count > 0 ? "critical" : "success"} />
        <Stat k="Total exposure" v={fmtUSD(s.total_exposure)} severity="critical" />
        <Stat k="Open cases" v={fmtNum(s.open_cases)} />
        <Stat k="Last run" v={p.last_run_at ? fmtDate(p.last_run_at) : "—"} />
      </div>

      <div className={`mb-6 grid grid-cols-1 lg:grid-cols-3 ${DRILL_GRID}`}>
        <div className={`${DRILL_CELL} lg:col-span-2`}>
          <h3 className={DRILL_TITLE}>Control definition</h3>
          <p className="text-sm leading-relaxed text-foreground">{p.description}</p>
          <div className={DRILL_SUBGRID}>
            <div className={DRILL_SUBCELL}><div className={DRILL_SUBLABEL}>Process</div><div className={DRILL_SUBVALUE}>{p.process}</div></div>
            <div className={DRILL_SUBCELL}><div className={DRILL_SUBLABEL}>Risk</div><div className={DRILL_SUBVALUE}>{p.risk}</div></div>
            <div className={DRILL_SUBCELL}><div className={DRILL_SUBLABEL}>Criticality</div><div className={DRILL_SUBVALUE}>{p.criticality}</div></div>
            <div className={DRILL_SUBCELL}><div className={DRILL_SUBLABEL}>Framework</div><div className={DRILL_SUBVALUE}>{p.framework}</div></div>
          </div>
        </div>
        <div className={DRILL_CELL}>
          <h3 className={DRILL_TITLE}>By entity</h3>
          {Object.entries(s.by_entity).length === 0 && <div className="font-mono text-xs text-muted-foreground">No data.</div>}
          {Object.entries(s.by_entity).map(([e, c]) => (
            <div key={e} className="flex items-center justify-between border-b border-zinc-200 py-2 last:border-0 dark:border-zinc-800">
              <span className="font-mono text-sm text-foreground">{e}</span>
              <span className="font-mono text-sm tabular-nums text-amber-700 dark:text-amber-400">{c}</span>
            </div>
          ))}
        </div>
      </div>

      <SectionTitle count={data.recent_runs?.length}>Recent test runs</SectionTitle>
      <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-64" testId="control-drill-recent-runs-table">
        <DataTableHead>
          <tr>
            <DataTableTh>When</DataTableTh>
            <DataTableTh>Status</DataTableTh>
            <DataTableTh align="right">Exceptions</DataTableTh>
          </tr>
        </DataTableHead>
        <DataTableBody>
          {data.recent_runs.map(r => (
            <DataTableRow key={r.id}>
              <DataTableTd className="font-mono text-xs text-muted-foreground">{fmtDateTime(r.run_ts)}</DataTableTd>
              <DataTableTd className={`font-mono text-xs ${r.status === "success" ? "text-[hsl(var(--chart-4))]" : "text-destructive"}`}>{r.status}</DataTableTd>
              <DataTableTd align="right" className="font-mono tabular-nums text-foreground">{r.exceptions_count}</DataTableTd>
            </DataTableRow>
          ))}
        </DataTableBody>
      </DataTable>

      <SectionTitle count={data.exceptions.length}>Exceptions from this control</SectionTitle>
      <ExceptionsTable exceptions={data.exceptions} nav={nav} />
    </>
  );
}
