import React from "react";
import { Link } from "react-router-dom";
import { fmtUSD, fmtDate } from "../../lib/format";
import { Warning } from "@phosphor-icons/react";
import {
  KV,
  SectionTitle,
  ExceptionsTable,
  CasesList,
  DRILL_GRID,
  DRILL_CELL,
  DRILL_TITLE,
  DRILL_INSET,
  DRILL_INSET_LINK,
} from "./shared";

export default function InvoiceDrill({ data, nav }) {
  const p = data.primary;
  return (
    <>
      <div className={`grid grid-cols-1 lg:grid-cols-3 ${DRILL_GRID}`}>
        <div className={DRILL_CELL}>
          <h3 className={DRILL_TITLE}>Invoice</h3>
          <KV k="Invoice #" v={p.invoice_number} mono />
          <KV k="Vendor" v={data.vendor?.vendor_name || p.vendor_name} link={data.vendor && `/app/drill/vendor/${data.vendor.id}`} />
          <KV k="Entity" v={p.entity} mono />
          <KV k="Date" v={fmtDate(p.invoice_date)} mono />
          <KV k="Amount" v={fmtUSD(p.amount)} mono />
          <KV k="Tax" v={`${fmtUSD(p.tax_amount)} (expected ${fmtUSD(p.expected_tax_amount)})`} mono />
          <KV k="Status" v={p.status} />
          <KV k="Approver" v={p.approver_email || "— MISSING —"} />
        </div>
        <div className={DRILL_CELL}>
          <h3 className={DRILL_TITLE}>Purchase chain</h3>
          {data.purchase_order ? (
            <>
              <KV k="PO #" v={data.purchase_order.po_number} mono />
              <KV k="PO amount" v={fmtUSD(data.purchase_order.amount)} mono />
              <KV k="PO date" v={fmtDate(data.purchase_order.po_date)} mono />
              {data.goods_receipt ? (
                <>
                  <KV k="GRN #" v={data.goods_receipt.grn_number} mono />
                  <KV k="GRN amount" v={fmtUSD(data.goods_receipt.amount)} mono />
                  <KV k="GRN date" v={fmtDate(data.goods_receipt.receipt_date)} mono />
                </>
              ) : <div className="py-3 font-mono text-xs text-destructive">No GRN</div>}
              <div className={`mt-3 ${DRILL_INSET}`}>
                <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">3-way variance</div>
                <div className="mt-1 font-mono text-sm tabular-nums text-foreground">
                  {((Math.abs(p.amount - (data.purchase_order.amount || 0)) / Math.max(1, data.purchase_order.amount)) * 100).toFixed(1)}%
                </div>
              </div>
            </>
          ) : <div className="font-mono text-xs text-muted-foreground">No PO linked (direct invoice).</div>}
        </div>
        <div className={DRILL_CELL}>
          <h3 className={DRILL_TITLE}>Payment trail</h3>
          {data.payments.length === 0 ? (
            <div className="font-mono text-xs text-muted-foreground">Unpaid.</div>
          ) : (
            <div className="space-y-2">
              {data.payments.map(pay => (
                <Link key={pay.id} to={`/app/drill/payment/${pay.id}`} className={DRILL_INSET_LINK}>
                  <div className="font-mono text-[10px] text-muted-foreground">{pay.bank_reference} · {fmtDate(pay.payment_date)}</div>
                  <div className="font-mono text-sm tabular-nums text-foreground">{fmtUSD(pay.amount)}</div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>

      {data.duplicates?.length > 0 && (
        <>
          <SectionTitle count={data.duplicates.length}>Potential duplicates of this invoice</SectionTitle>
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
            {data.duplicates.map(d => (
              <Link key={d.id} to={`/app/drill/invoice/${d.id}`} className="flex items-center justify-between gap-3 border border-destructive/25 bg-destructive/5 p-3 transition-colors hover:bg-destructive/10">
                <div>
                  <div className="font-mono text-xs text-foreground">{d.invoice_number}</div>
                  <div className="font-mono text-[10px] text-muted-foreground">{fmtDate(d.invoice_date)} · {d.entity}</div>
                </div>
                <Warning size={14} className="text-destructive" />
              </Link>
            ))}
          </div>
        </>
      )}

      <SectionTitle count={data.exceptions.length}>Exceptions</SectionTitle>
      <ExceptionsTable exceptions={data.exceptions} nav={nav} />

      <SectionTitle count={data.cases.length}>Cases</SectionTitle>
      <CasesList cases={data.cases} nav={nav} />
    </>
  );
}
