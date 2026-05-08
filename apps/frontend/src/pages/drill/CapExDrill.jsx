import React from "react";
import { fmtUSD, fmtDate } from "../../lib/format";
import { KV, SectionTitle, ExceptionsTable, CasesList, Stat, DRILL_GRID, DRILL_CELL, DRILL_TITLE } from "./shared";

export default function CapExDrill({ data, nav }) {
  const p = data.primary;
  const s = data.stats;
  return (
    <>
      <div className={`mb-6 grid grid-cols-2 md:grid-cols-4 ${DRILL_GRID}`}>
        <Stat k="Budget" v={fmtUSD(p.budget_amount)} />
        <Stat k="Actual" v={fmtUSD(p.actual_amount)} severity={s.variance > 0 ? "critical" : "success"} />
        <Stat k="Variance" v={fmtUSD(s.variance)} severity={s.variance > 0 ? "critical" : "success"} />
        <Stat k="Variance %" v={`${s.variance_pct.toFixed(1)}%`} severity={s.variance > 0 ? "critical" : "success"} />
      </div>
      <div className={`mb-6 grid grid-cols-1 lg:grid-cols-2 ${DRILL_GRID}`}>
        <div className={DRILL_CELL}>
          <h3 className={DRILL_TITLE}>Project</h3>
          <KV k="Code" v={p.project_code} mono />
          <KV k="Name" v={p.project_name} />
          <KV k="Entity" v={p.entity} mono />
          <KV k="Sponsor" v={p.sponsor} />
          <KV k="Start" v={fmtDate(p.start_date)} mono />
          <KV k="Status" v={p.status} />
        </div>
      </div>
      <SectionTitle count={data.exceptions.length}>Exceptions</SectionTitle>
      <ExceptionsTable exceptions={data.exceptions} nav={nav} />
      <SectionTitle count={data.cases.length}>Cases</SectionTitle>
      <CasesList cases={data.cases} nav={nav} />
    </>
  );
}
