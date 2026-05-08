import React from "react";
import { fmtUSD, fmtDate, fmtNum } from "../../lib/format";
import { KV, SectionTitle, ExceptionsTable, Stat, DRILL_GRID, DRILL_CELL, DRILL_TITLE } from "./shared";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../../components/DataTable";

export default function VendorDrill({ data, nav }) {
  const p = data.primary;
  const s = data.stats;
  return (
    <>
      <div className={`mb-6 grid grid-cols-2 md:grid-cols-5 ${DRILL_GRID}`}>
        <Stat k="Invoices" v={fmtNum(s.invoice_count)} />
        <Stat k="Payments" v={fmtNum(s.payment_count)} />
        <Stat k="Invoiced (USD)" v={fmtUSD(s.total_invoiced)} />
        <Stat k="Paid (USD)" v={fmtUSD(s.total_paid)} />
        <Stat k="Exceptions" v={fmtNum(s.exception_count)} severity={s.exception_count > 0 ? "critical" : "success"} />
      </div>

      <div className={`mb-6 grid grid-cols-1 lg:grid-cols-3 ${DRILL_GRID}`}>
        <div className={DRILL_CELL}>
          <h3 className={DRILL_TITLE}>Vendor master</h3>
          <KV k="Vendor code" v={p.vendor_code} mono />
          <KV k="Entity" v={p.entity} mono />
          <KV k="Status" v={p.status} />
          <KV k="Bank hash" v={p.bank_account_hash} mono />
          <KV k="Bank changed" v={fmtDate(p.bank_changed_at)} mono />
          <KV k="Created" v={fmtDate(p.created_at)} mono />
        </div>
        <div className={`${DRILL_CELL} lg:col-span-2`}>
          <h3 className={DRILL_TITLE}>Recent invoices ({data.invoices.length})</h3>
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-96" testId="vendor-drill-invoices-table">
            <DataTableHead>
              <tr>
                <DataTableTh>#</DataTableTh>
                <DataTableTh>Date</DataTableTh>
                <DataTableTh align="right">Amount</DataTableTh>
                <DataTableTh>Status</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {data.invoices.map(i => (
                <DataTableRow key={i.id} onClick={() => nav(`/app/drill/invoice/${i.id}`)}>
                  <DataTableTd className="font-mono text-xs text-primary">{i.invoice_number}</DataTableTd>
                  <DataTableTd className="font-mono text-xs text-foreground">{fmtDate(i.invoice_date)}</DataTableTd>
                  <DataTableTd align="right" className="font-mono tabular-nums text-foreground">{fmtUSD(i.amount)}</DataTableTd>
                  <DataTableTd className="font-mono text-xs text-foreground">{i.status}</DataTableTd>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </div>
      </div>

      <SectionTitle count={data.payments.length}>Payments</SectionTitle>
      <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-72" testId="vendor-drill-payments-table">
        <DataTableHead>
          <tr>
            <DataTableTh>Ref</DataTableTh>
            <DataTableTh>Date</DataTableTh>
            <DataTableTh align="right">Amount</DataTableTh>
          </tr>
        </DataTableHead>
        <DataTableBody>
          {data.payments.map(pp => (
            <DataTableRow key={pp.id} onClick={() => nav(`/app/drill/payment/${pp.id}`)}>
              <DataTableTd className="font-mono text-xs text-primary">{pp.bank_reference}</DataTableTd>
              <DataTableTd className="font-mono text-xs text-foreground">{fmtDate(pp.payment_date)}</DataTableTd>
              <DataTableTd align="right" className="font-mono tabular-nums text-foreground">{fmtUSD(pp.amount)}</DataTableTd>
            </DataTableRow>
          ))}
        </DataTableBody>
      </DataTable>

      <SectionTitle count={data.exceptions.length}>Exceptions</SectionTitle>
      <ExceptionsTable exceptions={data.exceptions} nav={nav} />
    </>
  );
}
