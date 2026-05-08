import React from "react";
import { Link } from "react-router-dom";
import { fmtUSD, fmtDate, fmtDateTime } from "../../lib/format";
import { KV, SectionTitle, ExceptionsTable, CasesList, DRILL_GRID, DRILL_CELL, DRILL_TITLE, DRILL_INSET_LINK } from "./shared";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../../components/DataTable";

export default function JournalDrill({ data, nav }) {
  const p = data.primary;
  return (
    <>
      <div className={`grid grid-cols-1 lg:grid-cols-3 ${DRILL_GRID}`}>
        <div className={DRILL_CELL}>
          <h3 className={DRILL_TITLE}>Journal</h3>
          <KV k="Journal #" v={p.journal_number} mono />
          <KV k="Entity" v={p.entity} mono />
          <KV k="Posting date" v={fmtDate(p.posting_date)} mono />
          <KV k="Created at" v={fmtDateTime(p.created_at)} mono />
          <KV k="Amount" v={fmtUSD(p.total_amount)} mono />
          <KV k="Manual" v={p.is_manual ? "YES" : "no"} />
          <KV k="Privileged poster" v={p.is_privileged_poster ? "YES" : "no"} />
          <KV k="Approver" v={p.approver_email || "— MISSING —"} />
        </div>
        <div className={DRILL_CELL}>
          <h3 className={DRILL_TITLE}>Poster</h3>
          {data.creator ? (
            <Link to={`/app/drill/user/${data.creator.email}`} className={DRILL_INSET_LINK}>
              <div className="font-mono text-[10px] text-muted-foreground">{data.creator.role}</div>
              <div className="mt-1 text-sm text-foreground">{data.creator.full_name || data.creator.email}</div>
              <div className="mt-2 font-mono text-xs text-primary">{data.creator.email} →</div>
            </Link>
          ) : <div className="font-mono text-xs text-muted-foreground">Unknown poster.</div>}
        </div>
        <div className={DRILL_CELL}>
          <h3 className={DRILL_TITLE}>Approver</h3>
          {data.approver ? (
            <Link to={`/app/drill/user/${data.approver.email}`} className={DRILL_INSET_LINK}>
              <div className="text-sm text-foreground">{data.approver.full_name || data.approver.email}</div>
              <div className="mt-2 font-mono text-xs text-primary">{data.approver.email} →</div>
            </Link>
          ) : <div className="border border-destructive/30 bg-destructive/5 p-3 font-mono text-xs text-destructive">⚠ No approver documented.</div>}
        </div>
      </div>

      <SectionTitle count={data.recent_by_same_user?.length}>Recent journals by the same user</SectionTitle>
      <DataTable maxHeightClassName="max-h-[50vh]" testId="journal-drill-recent-journals-table">
        <DataTableHead>
          <tr>
            <DataTableTh>Journal #</DataTableTh>
            <DataTableTh>Posting</DataTableTh>
            <DataTableTh>Entity</DataTableTh>
            <DataTableTh align="right">Amount</DataTableTh>
            <DataTableTh>Manual</DataTableTh>
          </tr>
        </DataTableHead>
        <DataTableBody>
          {data.recent_by_same_user.map(j => (
            <DataTableRow key={j.id} onClick={() => nav(`/app/drill/journal/${j.id}`)}>
              <DataTableTd className="font-mono text-xs text-primary">{j.journal_number}</DataTableTd>
              <DataTableTd className="font-mono text-xs text-muted-foreground">{fmtDate(j.posting_date)}</DataTableTd>
              <DataTableTd className="font-mono text-xs text-foreground">{j.entity}</DataTableTd>
              <DataTableTd align="right" className="font-mono tabular-nums text-foreground">{fmtUSD(j.total_amount)}</DataTableTd>
              <DataTableTd className="font-mono text-xs text-foreground">{j.is_manual ? "yes" : "no"}</DataTableTd>
            </DataTableRow>
          ))}
        </DataTableBody>
      </DataTable>

      <SectionTitle count={data.exceptions.length}>Exceptions</SectionTitle>
      <ExceptionsTable exceptions={data.exceptions} nav={nav} />
      <SectionTitle count={data.cases.length}>Cases</SectionTitle>
      <CasesList cases={data.cases} nav={nav} />
    </>
  );
}
