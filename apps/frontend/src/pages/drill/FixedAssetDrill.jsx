import React from "react";
import { fmtUSD, fmtDate } from "../../lib/format";
import { KV, SectionTitle, ExceptionsTable, CasesList, Stat, DRILL_GRID, DRILL_CELL, DRILL_TITLE } from "./shared";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../../components/DataTable";

export default function FixedAssetDrill({ data, nav }) {
  const p = data.primary;
  const s = data.stats;
  return (
    <>
      <div className={`mb-6 grid grid-cols-2 md:grid-cols-4 ${DRILL_GRID}`}>
        <Stat k="Cost" v={fmtUSD(p.cost)} />
        <Stat k="Accumulated Dep." v={fmtUSD(s.accumulated_depreciation)} />
        <Stat k="Net Book Value" v={fmtUSD(s.net_book_value)} />
        <Stat k="Status" v={p.status.toUpperCase()} severity={p.status === "disposed" ? "critical" : "success"} />
      </div>
      <div className={`mb-6 grid grid-cols-1 lg:grid-cols-3 ${DRILL_GRID}`}>
        <div className={DRILL_CELL}>
          <h3 className={DRILL_TITLE}>Asset master</h3>
          <KV k="Code" v={p.asset_code} mono />
          <KV k="Name" v={p.asset_name} />
          <KV k="Category" v={p.category} />
          <KV k="Entity" v={p.entity} mono />
          <KV k="In service" v={fmtDate(p.in_service_date)} mono />
          <KV k="Useful life" v={`${p.useful_life_months} months`} mono />
          <KV k="Monthly dep." v={fmtUSD(p.monthly_depreciation)} mono />
          {p.disposed_at && <KV k="Disposed" v={fmtDate(p.disposed_at)} mono />}
        </div>
        <div className={`${DRILL_CELL} lg:col-span-2`}>
          <h3 className={DRILL_TITLE}>Depreciation schedule ({data.depreciation.length})</h3>
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-80" testId="fixed-asset-drill-depreciation-table">
            <DataTableHead>
              <tr>
                <DataTableTh>Period</DataTableTh>
                <DataTableTh align="right">Amount</DataTableTh>
                <DataTableTh>Posted</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {data.depreciation.map(dep => (
                <DataTableRow key={dep.id}>
                  <DataTableTd className="font-mono text-xs text-primary">{dep.period}</DataTableTd>
                  <DataTableTd align="right" className="font-mono tabular-nums text-foreground">{fmtUSD(dep.amount)}</DataTableTd>
                  <DataTableTd className="font-mono text-xs text-muted-foreground">{fmtDate(dep.posted_at)}</DataTableTd>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </div>
      </div>
      <SectionTitle count={data.exceptions.length}>Exceptions</SectionTitle>
      <ExceptionsTable exceptions={data.exceptions} nav={nav} />
      <SectionTitle count={data.cases.length}>Cases</SectionTitle>
      <CasesList cases={data.cases} nav={nav} />
    </>
  );
}
