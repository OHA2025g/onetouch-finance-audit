import React from "react";
import { fmtUSD, fmtDate } from "../../lib/format";
import { KV, SectionTitle, ExceptionsTable, CasesList, DRILL_GRID, DRILL_CELL, DRILL_TITLE, DRILL_INSET } from "./shared";

export default function ARInvoiceDrill({ data, nav }) {
  const p = data.primary;
  const now = new Date();
  const due = new Date(p.due_date);
  const daysOverdue = Math.floor((now - due) / (1000 * 60 * 60 * 24));
  return (
    <>
      <div className={`mb-6 grid grid-cols-1 lg:grid-cols-3 ${DRILL_GRID}`}>
        <div className={DRILL_CELL}>
          <h3 className={DRILL_TITLE}>Invoice</h3>
          <KV k="AR #" v={p.ar_number} mono />
          <KV k="Customer" v={data.customer?.customer_name || p.customer_name}
            link={data.customer && `/app/drill/customer/${data.customer.id}`} />
          <KV k="Entity" v={p.entity} mono />
          <KV k="Date" v={fmtDate(p.invoice_date)} mono />
          <KV k="Due" v={fmtDate(p.due_date)} mono />
          <KV k="Shipment" v={fmtDate(p.shipment_date)} mono />
          <KV k="Amount" v={fmtUSD(p.amount)} mono />
          <KV k="Status" v={p.status} />
        </div>
        <div className={DRILL_CELL}>
          <h3 className={DRILL_TITLE}>Aging</h3>
          {p.status === "open" ? (
            <div className={`font-mono text-2xl ${daysOverdue > 90 ? "text-destructive" : daysOverdue > 0 ? "text-amber-600 dark:text-amber-400" : "text-[hsl(var(--chart-4))]"}`}>
              {daysOverdue > 0 ? `+${daysOverdue}d overdue` : `${-daysOverdue}d remaining`}
            </div>
          ) : (
            <div className="font-mono text-xs text-[hsl(var(--chart-4))]">Paid / closed.</div>
          )}
        </div>
        <div className={DRILL_CELL}>
          <h3 className={DRILL_TITLE}>Receipts ({data.receipts.length})</h3>
          {data.receipts.length === 0 ? (
            <div className="font-mono text-xs text-muted-foreground">No receipts received.</div>
          ) : data.receipts.map(r => (
            <div key={r.id} className={`${DRILL_INSET} mb-2`}>
              <div className="font-mono text-[10px] text-muted-foreground">{r.bank_reference} · {fmtDate(r.receipt_date)}</div>
              <div className="font-mono text-sm tabular-nums text-foreground">{fmtUSD(r.amount)}</div>
            </div>
          ))}
        </div>
      </div>

      <SectionTitle count={data.exceptions.length}>Exceptions</SectionTitle>
      <ExceptionsTable exceptions={data.exceptions} nav={nav} />
      <SectionTitle count={data.cases.length}>Cases</SectionTitle>
      <CasesList cases={data.cases} nav={nav} />
    </>
  );
}
