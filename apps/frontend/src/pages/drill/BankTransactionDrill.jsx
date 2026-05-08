import React from "react";
import { fmtUSD, fmtDateTime } from "../../lib/format";
import { KV, SectionTitle, ExceptionsTable, CasesList, DRILL_GRID, DRILL_CELL, DRILL_TITLE } from "./shared";

export default function BankTransactionDrill({ data, nav }) {
  const p = data.primary;
  return (
    <>
      <div className={`mb-6 grid grid-cols-1 lg:grid-cols-2 ${DRILL_GRID}`}>
        <div className={DRILL_CELL}>
          <h3 className={DRILL_TITLE}>Transaction</h3>
          <KV k="Reference" v={p.reference} mono />
          <KV k="Direction" v={p.direction} />
          <KV k="Timestamp" v={fmtDateTime(p.txn_ts)} mono />
          <KV k="Amount" v={fmtUSD(p.amount)} mono />
          <KV k="Currency" v={p.currency} mono />
          <KV k="Counterparty" v={p.counterparty} />
        </div>
        <div className={DRILL_CELL}>
          <h3 className={DRILL_TITLE}>Bank account</h3>
          {data.bank_account ? (
            <>
              <KV k="Bank" v={data.bank_account.bank_name} />
              <KV k="Account" v={data.bank_account.account_number_masked} mono />
              <KV k="Entity" v={data.bank_account.entity} mono />
              <KV k="Currency" v={data.bank_account.currency} mono />
              <KV k="Balance" v={fmtUSD(data.bank_account.balance)} mono />
            </>
          ) : <div className="font-mono text-xs text-muted-foreground">—</div>}
        </div>
      </div>
      <SectionTitle count={data.exceptions.length}>Exceptions</SectionTitle>
      <ExceptionsTable exceptions={data.exceptions} nav={nav} />
      <SectionTitle count={data.cases.length}>Cases</SectionTitle>
      <CasesList cases={data.cases} nav={nav} />
    </>
  );
}
