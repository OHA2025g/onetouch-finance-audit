import React from "react";
import { Link } from "react-router-dom";
import { fmtUSD, fmtDate } from "../../lib/format";
import { KV, SectionTitle, ExceptionsTable, CasesList, DRILL_GRID, DRILL_CELL, DRILL_TITLE, DRILL_INSET_LINK } from "./shared";

export default function PaymentDrill({ data, nav }) {
  const p = data.primary;
  return (
    <>
      <div className={`grid grid-cols-1 lg:grid-cols-3 ${DRILL_GRID}`}>
        <div className={DRILL_CELL}>
          <h3 className={DRILL_TITLE}>Payment</h3>
          <KV k="Reference" v={p.bank_reference} mono />
          <KV k="Vendor" v={data.vendor?.vendor_name || p.vendor_name} link={data.vendor && `/app/drill/vendor/${data.vendor.id}`} />
          <KV k="Entity" v={p.entity} mono />
          <KV k="Date" v={fmtDate(p.payment_date)} mono />
          <KV k="Amount" v={fmtUSD(p.amount)} mono />
        </div>
        <div className={`${DRILL_CELL} lg:col-span-2`}>
          <h3 className={DRILL_TITLE}>Linked invoice</h3>
          {data.invoice ? (
            <Link to={`/app/drill/invoice/${data.invoice.id}`} className={DRILL_INSET_LINK}>
              <div className="font-mono text-xs text-primary">{data.invoice.invoice_number} →</div>
              <div className="mt-1 text-sm text-foreground">{data.invoice.vendor_name}</div>
              <div className="mt-3 grid grid-cols-3 gap-4 font-mono text-xs text-muted-foreground">
                <div><span className="text-muted-foreground">Amount</span><div className="tabular-nums text-foreground">{fmtUSD(data.invoice.amount)}</div></div>
                <div><span className="text-muted-foreground">Invoice date</span><div className="text-foreground">{fmtDate(data.invoice.invoice_date)}</div></div>
                <div><span className="text-muted-foreground">Status</span><div className="text-foreground">{data.invoice.status}</div></div>
              </div>
            </Link>
          ) : <div className="font-mono text-xs text-muted-foreground">No invoice linked.</div>}
        </div>
      </div>

      <SectionTitle count={data.exceptions.length}>Exceptions</SectionTitle>
      <ExceptionsTable exceptions={data.exceptions} nav={nav} />

      <SectionTitle count={data.cases.length}>Cases</SectionTitle>
      <CasesList cases={data.cases} nav={nav} />
    </>
  );
}
