import React from "react";
import { Link } from "react-router-dom";
import { fmtUSD, fmtDate } from "../../lib/format";
import { KV, SectionTitle, ExceptionsTable, CasesList, DRILL_GRID, DRILL_CELL, DRILL_TITLE, DRILL_INSET_LINK } from "./shared";

export default function PayrollEntryDrill({ data, nav }) {
  const p = data.primary;
  return (
    <>
      <div className={`mb-6 grid grid-cols-1 lg:grid-cols-3 ${DRILL_GRID}`}>
        <div className={DRILL_CELL}>
          <h3 className={DRILL_TITLE}>Entry</h3>
          <KV k="ID" v={p.id} mono />
          <KV k="Period" v={p.period} mono />
          <KV k="Entity" v={p.entity} mono />
          <KV k="Gross" v={fmtUSD(p.gross_amount)} mono />
          <KV k="Tax" v={fmtUSD(p.tax_amount)} mono />
          <KV k="Net" v={fmtUSD(p.net_amount)} mono />
          <KV k="Status" v={p.status} />
        </div>
        <div className={DRILL_CELL}>
          <h3 className={DRILL_TITLE}>Employee</h3>
          {data.employee ? (
            <Link to={`/app/drill/employee/${data.employee.id}`} className={DRILL_INSET_LINK}>
              <div className="text-sm text-foreground">{data.employee.full_name}</div>
              <div className="mt-1 font-mono text-[10px] text-muted-foreground">{data.employee.email} · {data.employee.department}</div>
              <div className={`mt-2 font-mono text-xs ${data.employee.status === "terminated" ? "text-destructive" : "text-[hsl(var(--chart-4))]"}`}>
                {data.employee.status}
              </div>
            </Link>
          ) : <div className="font-mono text-xs text-muted-foreground">—</div>}
        </div>
        <div className={DRILL_CELL}>
          <h3 className={DRILL_TITLE}>Payroll run</h3>
          {data.payroll_run ? (
            <>
              <KV k="Run ID" v={data.payroll_run.id} mono />
              <KV k="Run date" v={fmtDate(data.payroll_run.run_date)} mono />
              <KV k="Total gross" v={fmtUSD(data.payroll_run.total_gross)} mono />
              <KV k="Status" v={data.payroll_run.status} />
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
