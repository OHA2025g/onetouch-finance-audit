import React from "react";
import { fmtUSD, fmtDate, fmtDateTime } from "../../lib/format";
import { PriorityTag } from "../../components/Badges";
import { KV, SectionTitle, DRILL_GRID, DRILL_CELL, DRILL_TITLE } from "./shared";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../../components/DataTable";

export default function UserDrill({ data, nav }) {
  const p = data.primary;
  return (
    <>
      <div className={`mb-6 grid grid-cols-1 lg:grid-cols-3 ${DRILL_GRID}`}>
        <div className={DRILL_CELL}>
          <h3 className={DRILL_TITLE}>Identity</h3>
          <KV k="Name" v={p.full_name || "—"} />
          <KV k="Email" v={p.email} mono />
          <KV k="Role" v={p.role || "—"} />
          <KV k="Entity" v={p.entity || "—"} mono />
          <KV k="Status" v={p.status || "—"} />
        </div>
        <div className={DRILL_CELL}>
          <h3 className={DRILL_TITLE}>Assigned roles / SoD</h3>
          {data.roles.length === 0 && <div className="font-mono text-xs text-muted-foreground">None.</div>}
          {data.roles.map((r, i) => (
            <div key={i} className="flex items-center justify-between border-b border-zinc-200 py-2 last:border-0 dark:border-zinc-800">
              <span className="text-sm text-foreground">{r.role}</span>
              <span className="font-mono text-[10px] text-muted-foreground">{r.entity}</span>
            </div>
          ))}
        </div>
        <div className={DRILL_CELL}>
          <h3 className={DRILL_TITLE}>Assigned cases ({data.cases.length})</h3>
          <div className="max-h-60 space-y-1 overflow-y-auto">
            {data.cases.map(c => (
              <div
                key={c.id}
                onClick={() => nav(`/app/cases/${c.id}`)}
                className="flex cursor-pointer items-center justify-between gap-2 rounded-sm border border-zinc-200 bg-zinc-50/90 p-2 transition-colors hover:bg-zinc-100 dark:border-zinc-800 dark:bg-zinc-900/50 dark:hover:bg-zinc-900/80"
              >
                <div className="min-w-0 flex-1 truncate text-xs text-foreground">{c.title}</div>
                <PriorityTag priority={c.priority} />
              </div>
            ))}
            {data.cases.length === 0 && <div className="font-mono text-xs text-muted-foreground">No cases.</div>}
          </div>
        </div>
      </div>

      <SectionTitle count={data.access_events.length}>Access events</SectionTitle>
      <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-64" testId="user-drill-access-events-table">
        <DataTableHead>
          <tr>
            <DataTableTh>When</DataTableTh>
            <DataTableTh>System</DataTableTh>
            <DataTableTh>Event</DataTableTh>
            <DataTableTh>Terminated?</DataTableTh>
          </tr>
        </DataTableHead>
        <DataTableBody>
          {data.access_events.map(e => (
            <DataTableRow key={e.id}>
              <DataTableTd className="font-mono text-xs text-muted-foreground">{fmtDateTime(e.event_ts)}</DataTableTd>
              <DataTableTd className="font-mono text-xs text-foreground">{e.system}</DataTableTd>
              <DataTableTd className="font-mono text-xs text-primary">{e.event_type}</DataTableTd>
              <DataTableTd className={`font-mono text-xs ${e.user_terminated ? "text-destructive" : "text-[hsl(var(--chart-4))]"}`}>
                {e.user_terminated ? "YES ⚠" : "no"}
              </DataTableTd>
            </DataTableRow>
          ))}
        </DataTableBody>
      </DataTable>

      <SectionTitle count={data.journals_posted?.length}>Journals posted by this user</SectionTitle>
      <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-60" testId="user-drill-journals-posted-table">
        <DataTableHead>
          <tr>
            <DataTableTh>#</DataTableTh>
            <DataTableTh>Posting</DataTableTh>
            <DataTableTh align="right">Amount</DataTableTh>
            <DataTableTh>Manual</DataTableTh>
          </tr>
        </DataTableHead>
        <DataTableBody>
          {data.journals_posted.map(j => (
            <DataTableRow key={j.id} onClick={() => nav(`/app/drill/journal/${j.id}`)}>
              <DataTableTd className="font-mono text-xs text-primary">{j.journal_number}</DataTableTd>
              <DataTableTd className="font-mono text-xs text-foreground">{fmtDate(j.posting_date)}</DataTableTd>
              <DataTableTd align="right" className="font-mono tabular-nums text-foreground">{fmtUSD(j.total_amount)}</DataTableTd>
              <DataTableTd className="font-mono text-xs text-foreground">{j.is_manual ? "yes" : "no"}</DataTableTd>
            </DataTableRow>
          ))}
        </DataTableBody>
      </DataTable>

      <SectionTitle count={data.audit_log.length}>Recent audit log</SectionTitle>
      <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-60" testId="user-drill-audit-log-table">
        <DataTableHead>
          <tr>
            <DataTableTh>When</DataTableTh>
            <DataTableTh>Action</DataTableTh>
            <DataTableTh>Object</DataTableTh>
            <DataTableTh className="w-28">Event</DataTableTh>
          </tr>
        </DataTableHead>
        <DataTableBody>
          {data.audit_log.map(l => (
            <DataTableRow key={l.id}>
              <DataTableTd className="font-mono text-xs text-muted-foreground">{fmtDateTime(l.event_ts)}</DataTableTd>
              <DataTableTd className="font-mono text-xs text-primary">{l.action_type}</DataTableTd>
              <DataTableTd className="font-mono text-xs text-muted-foreground">{l.object_type}: {(l.object_id || "").slice(0, 20)}</DataTableTd>
              <DataTableTd className="font-mono text-xs">
                <span
                  onClick={() => nav(`/app/audit-log/${encodeURIComponent(l.id)}`)}
                  className="cursor-pointer text-primary hover:underline"
                >
                  open →
                </span>
              </DataTableTd>
            </DataTableRow>
          ))}
        </DataTableBody>
      </DataTable>
    </>
  );
}
