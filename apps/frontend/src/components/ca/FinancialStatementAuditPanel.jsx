import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { http } from "../../lib/api";
import { toast } from "sonner";
import { ArrowSquareOut, FileArrowUp } from "@phosphor-icons/react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { PageHeader, SectionCard } from "../PageShell";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../DataTable";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "../ui/dialog";
import { RC_STROKE, RC_TICK, rcTooltipStyle } from "../../lib/rechartsTheme";

const VIEWS = [
  { id: "upload", label: "TB upload" },
  { id: "tb", label: "TB viewer" },
  { id: "bs", label: "Balance sheet" },
  { id: "pl", label: "P&L" },
  { id: "cf", label: "Cash flow" },
  { id: "adj", label: "Adjustments" },
];

function MaterialityLineBadge({ flag }) {
  const f = flag || "none";
  if (f === "none") return <span className="text-[10px] font-mono text-[#525252]">—</span>;
  if (f === "performance") {
    return (
      <span className="font-mono text-[9px] uppercase px-1.5 py-0.5 bg-[#854D0E]/35 text-[#FDE047] border border-[#A16207]/50" title="Performance materiality">
        PM
      </span>
    );
  }
  return (
    <span className="font-mono text-[9px] uppercase px-1.5 py-0.5 bg-[#7F1D1D]/45 text-[#FECACA] border border-[#991B1B]/60" title="Material / high attention">
      MAT
    </span>
  );
}

function formatMoney(n) {
  if (n == null || Number.isNaN(Number(n))) return "—";
  const v = Number(n);
  return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

export default function FinancialStatementAuditPanel({ engagementId, compact = false }) {
  const eid = engagementId;
  const [view, setView] = useState("upload");
  const [tbData, setTbData] = useState(null);
  const [fsSnap, setFsSnap] = useState(null);
  const [bsPack, setBsPack] = useState(null);
  const [plPack, setPlPack] = useState(null);
  const [cfPack, setCfPack] = useState(null);
  const [materiality, setMateriality] = useState(null);
  const [adjustments, setAdjustments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [drillCode, setDrillCode] = useState(null);
  const [drillRow, setDrillRow] = useState(null);
  const [drillLoading, setDrillLoading] = useState(false);

  const loadFsBundle = useCallback(async () => {
    if (!eid) return;
    try {
      const [tbRes, fsRes, matRes, bsRes, plRes, cfRes, adjRes] = await Promise.all([
        http.get(`/audit-engagements/${encodeURIComponent(eid)}/trial-balance`),
        http.get(`/audit-engagements/${encodeURIComponent(eid)}/financial-statements/latest`).catch(() => ({ data: {} })),
        http.get(`/audit-engagements/${encodeURIComponent(eid)}/materiality`).catch(() => ({ data: null })),
        http.get(`/audit-engagements/${encodeURIComponent(eid)}/balance-sheet`).catch(() => ({ data: {} })),
        http.get(`/audit-engagements/${encodeURIComponent(eid)}/profit-loss`).catch(() => ({ data: {} })),
        http.get(`/audit-engagements/${encodeURIComponent(eid)}/cash-flow`).catch(() => ({ data: {} })),
        http.get(`/audit-engagements/${encodeURIComponent(eid)}/audit-adjustments`).catch(() => ({ data: { items: [] } })),
      ]);
      setTbData(tbRes.data || null);
      setFsSnap(fsRes.data?.snapshot || null);
      setMateriality(matRes.data || null);
      setBsPack(bsRes.data || null);
      setPlPack(plRes.data || null);
      setCfPack(cfRes.data || null);
      setAdjustments(adjRes.data?.items || []);
    } catch {
      toast.error("Failed to load FS data");
    }
  }, [eid]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!eid) return;
      setLoading(true);
      await loadFsBundle();
      if (!cancelled) setLoading(false);
    })();
    return () => { cancelled = true; };
  }, [eid, loadFsBundle]);

  const genFs = async () => {
    try {
      await http.post(`/audit-engagements/${encodeURIComponent(eid)}/fs/generate`, { mapping_profile: "default_ind_as" });
      toast.success("Financial statements generated");
      await loadFsBundle();
    } catch {
      toast.error("FS generation failed — upload a balanced trial balance first");
    }
  };

  const chartRows = (bsPack?.variances && bsPack.variances.length ? bsPack.variances : plPack?.variances) || [];

  const openDrill = async (accountCode, label) => {
    if (!accountCode) return;
    setDrillCode(accountCode);
    setDrillRow({ account_code: accountCode, account_name: label });
    setDrillLoading(true);
    try {
      const { data } = await http.get(
        `/audit-engagements/${encodeURIComponent(eid)}/fs/drilldown`,
        { params: { account_code: accountCode } },
      );
      setDrillRow(data);
    } catch {
      toast.error("Drilldown failed");
      setDrillRow(null);
    } finally {
      setDrillLoading(false);
    }
  };

  const submitAdjustment = async (ev) => {
    ev.preventDefault();
    const fd = new FormData(ev.target);
    const body = {
      account_code: String(fd.get("account_code") || "").trim(),
      account_name: String(fd.get("account_name") || "").trim(),
      debit: parseFloat(fd.get("debit") || "0", 10) || 0,
      credit: parseFloat(fd.get("credit") || "0", 10) || 0,
      narrative: String(fd.get("narrative") || "").trim(),
      status: "proposed",
    };
    if (!body.account_code || !body.narrative) {
      toast.error("Account code and narrative are required");
      return;
    }
    try {
      await http.post(`/audit-engagements/${encodeURIComponent(eid)}/audit-adjustments`, body);
      toast.success("Adjustment proposed");
      ev.target.reset();
      const { data } = await http.get(`/audit-engagements/${encodeURIComponent(eid)}/audit-adjustments`);
      setAdjustments(data?.items || []);
    } catch {
      toast.error("Could not save adjustment");
    }
  };

  const patchAdjStatus = async (id, status) => {
    try {
      await http.put(`/audit-adjustments/${encodeURIComponent(id)}`, { status });
      toast.success(`Status: ${status}`);
      const { data } = await http.get(`/audit-engagements/${encodeURIComponent(eid)}/audit-adjustments`);
      setAdjustments(data?.items || []);
    } catch {
      toast.error("Update failed");
    }
  };

  const fm = materiality?.final_materiality;
  const perf = materiality?.performance_materiality ?? materiality?.performance_materiality_high;

  const header = compact ? null : (
    <PageHeader
      kicker="FS AUDIT ENGINE"
      title="Financial statement audit"
      subtitle={`Engagement ${eid} · mapping & variance review`}
      right={null}
    />
  );

  return (
    <div className="space-y-4">
      {header}
      <div className="flex flex-wrap items-center gap-2 justify-between">
        <div className="flex flex-wrap gap-1 items-center">
          {compact ? (
            <Link
              to={`/app/audit-planning/engagements/${encodeURIComponent(eid)}/fs-audit`}
              className="text-[10px] font-mono uppercase text-[#0A84FF] inline-flex items-center gap-1 mr-2"
            >
              Full FS module <ArrowSquareOut size={12} />
            </Link>
          ) : null}
        <div className="flex flex-wrap gap-1">
          {VIEWS.map((v) => (
            <button
              key={v.id}
              type="button"
              onClick={() => setView(v.id)}
              className={`px-2.5 h-8 font-mono text-[10px] uppercase border ${view === v.id ? "bg-white text-black border-white" : "border-[#262626] text-[#A3A3A3] hover:text-white"}`}
            >
              {v.label}
            </button>
          ))}
        </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-[10px] font-mono text-[#737373]">
          {fm != null ? (
            <span className="border border-[#262626] px-2 py-1 text-[#E5E5E5]" title="Overall materiality">
              OM {formatMoney(fm)}
            </span>
          ) : null}
          {perf != null ? (
            <span className="border border-[#262626] px-2 py-1 text-[#A3A3A3]" title="Performance materiality (reference)">
              Perf {formatMoney(perf)}
            </span>
          ) : null}
          <button type="button" onClick={loadFsBundle} className="px-2 h-8 border border-[#262626] uppercase hover:border-white">
            Refresh
          </button>
        </div>
      </div>

      {view === "upload" ? (
        <SectionCard kicker="TRIAL BALANCE" title="Upload CSV / XLSX" bodyClassName="p-6">
          <p className="text-sm text-[#A3A3A3] mb-3">
            Columns: <span className="text-white">account_code</span>, <span className="text-white">account_name</span>,{" "}
            <span className="text-white">debit</span>, <span className="text-white">credit</span>. Optional: opening_debit, opening_credit,
            closing_debit, closing_credit, classification (assets|liabilities|equity|revenue|expenses).
          </p>
          <label className="inline-flex items-center gap-2 text-xs font-mono uppercase text-[#0A84FF] cursor-pointer">
            <FileArrowUp size={18} />
            Choose file
            <input
              type="file"
              accept=".csv,.xlsx,.xls"
              className="hidden"
              onChange={async (ev) => {
                const f = ev.target.files?.[0];
                if (!f) return;
                const body = new FormData();
                body.append("file", f);
                try {
                  await http.post(`/audit-engagements/${encodeURIComponent(eid)}/trial-balance/upload`, body, {
                    headers: { "Content-Type": "multipart/form-data" },
                  });
                  toast.success("Trial balance uploaded");
                  await loadFsBundle();
                } catch {
                  toast.error("Upload failed — file must be balanced (debits = credits)");
                }
                ev.target.value = "";
              }}
            />
          </label>
          {tbData?.meta ? (
            <div className="mt-4 font-mono text-xs text-[#E5E5E5] space-y-1">
              <div>
                Rows {tbData.meta.rows} · DR {tbData.meta.total_debit} · CR {tbData.meta.total_credit} · Balanced:{" "}
                {tbData.meta.balanced ? "yes" : "no"}
              </div>
              {(tbData.meta.validation_warnings || []).length ? (
                <div className="text-[#FF9F0A]">Warnings: {(tbData.meta.validation_warnings || []).join(" · ")}</div>
              ) : null}
            </div>
          ) : (
            <div className="mt-4 text-xs text-[#737373] font-mono">No trial balance on file.</div>
          )}
          <button type="button" onClick={genFs} className="mt-4 px-4 h-10 bg-white text-black font-mono text-xs uppercase">
            Generate FS from TB
          </button>
        </SectionCard>
      ) : null}

      {view === "tb" ? (
        <SectionCard kicker="GL" title="Trial balance lines" bodyClassName="p-0">
          <div className="max-h-[min(70vh,560px)] overflow-auto">
            <DataTable className="rounded-none border-0">
              <DataTableHead>
                <tr>
                  <DataTableTh>Code</DataTableTh>
                  <DataTableTh>Name</DataTableTh>
                  <DataTableTh className="text-right">Debit</DataTableTh>
                  <DataTableTh className="text-right">Credit</DataTableTh>
                  <DataTableTh className="text-right">Net</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {(tbData?.lines || []).map((r) => (
                  <DataTableRow key={r.id}>
                    <DataTableTd className="font-mono text-xs">{r.account_code}</DataTableTd>
                    <DataTableTd className="text-xs">{r.account_name}</DataTableTd>
                    <DataTableTd className="text-right font-mono text-xs">{formatMoney(r.debit)}</DataTableTd>
                    <DataTableTd className="text-right font-mono text-xs">{formatMoney(r.credit)}</DataTableTd>
                    <DataTableTd className="text-right font-mono text-xs">
                      {formatMoney((Number(r.debit) || 0) - (Number(r.credit) || 0))}
                    </DataTableTd>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </DataTable>
          </div>
        </SectionCard>
      ) : null}

      {view === "bs" || view === "pl" ? (
        <div className="grid gap-4 lg:grid-cols-3">
          <SectionCard
            kicker={view === "bs" ? "BALANCE SHEET" : "P&L"}
            title={view === "bs" ? "Statement lines" : "Statement lines"}
            bodyClassName="p-0 lg:col-span-2"
          >
            <DataTable className="rounded-none border-0">
              <DataTableHead>
                <tr>
                  <DataTableTh>Line</DataTableTh>
                  <DataTableTh className="text-right">Current</DataTableTh>
                  <DataTableTh className="text-right">Prior</DataTableTh>
                  <DataTableTh className="text-right">Variance</DataTableTh>
                  <DataTableTh className="text-center">Mat.</DataTableTh>
                  <DataTableTh>Drill</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {((view === "bs" ? bsPack?.lines : plPack?.lines) ?? []).map((row) => (
                  <DataTableRow key={row.id}>
                    <DataTableTd className="text-sm text-white">{row.line}</DataTableTd>
                    <DataTableTd className="text-right font-mono text-xs">{formatMoney(row.amount)}</DataTableTd>
                    <DataTableTd className="text-right font-mono text-xs text-[#A3A3A3]">{formatMoney(row.prior_amount)}</DataTableTd>
                    <DataTableTd className="text-right font-mono text-xs">{formatMoney(row.variance)}</DataTableTd>
                    <DataTableTd className="text-center">
                      <MaterialityLineBadge flag={row.materiality_flag} />
                    </DataTableTd>
                    <DataTableTd>
                      <button
                        type="button"
                        className="text-[10px] font-mono uppercase text-[#0A84FF] hover:underline"
                        onClick={() => {
                          const first = (row.child_accounts || [])[0];
                          if (first?.account_code) openDrill(first.account_code, first.account_name);
                          else toast.message("No mapped accounts under this line");
                        }}
                      >
                        GL sample
                      </button>
                    </DataTableTd>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </DataTable>
            <div className="p-4 border-t border-[#262626] max-h-48 overflow-auto">
              <div className="text-[10px] font-mono uppercase text-[#737373] mb-2">Accounts — click code for journal drilldown</div>
              {((view === "bs" ? bsPack?.lines : plPack?.lines) ?? [])
                .flatMap((row) => row.child_accounts || [])
                .slice(0, 80)
                .map((c) => (
                  <button
                    key={`${c.account_code}-${c.trial_balance_line_id}`}
                    type="button"
                    className="block w-full text-left text-xs font-mono py-1 px-2 hover:bg-[#1A1A1A] text-[#A3A3A3]"
                    onClick={() => openDrill(c.account_code, c.account_name)}
                  >
                    <span className="text-white">{c.account_code}</span> {c.account_name} · net {formatMoney(c.net_amount)}{" "}
                    <MaterialityLineBadge flag={c.materiality_flag} />
                  </button>
                ))}
            </div>
          </SectionCard>
          <SectionCard kicker="VARIANCE" title="Current vs prior" bodyClassName="p-4 h-[320px]">
            {chartRows.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartRows} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={RC_STROKE} />
                  <XAxis dataKey="name" tick={RC_TICK} interval={0} angle={-18} textAnchor="end" height={56} stroke={RC_STROKE} />
                  <YAxis tick={RC_TICK} stroke={RC_STROKE} />
                  <Tooltip
                    contentStyle={rcTooltipStyle()}
                    labelStyle={{ color: "hsl(var(--card-foreground))" }}
                  />
                  <Legend
                    wrapperStyle={{
                      fontSize: 11,
                      fontFamily: "'JetBrains Mono', ui-monospace, monospace",
                      color: "hsl(var(--muted-foreground))",
                    }}
                  />
                  <Bar dataKey="current" name="Current" fill="hsl(var(--chart-1))" radius={[2, 2, 0, 0]} />
                  <Bar dataKey="prior" name="Prior" fill="hsl(var(--muted-foreground))" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="text-xs text-[#737373] font-mono h-full flex items-center">Generate FS to populate variance data.</div>
            )}
          </SectionCard>
        </div>
      ) : null}

      {view === "cf" ? (
        <SectionCard kicker="CASH FLOW" title="Indirect method (demo)" bodyClassName="p-0">
          <DataTable className="rounded-none border-0">
            <DataTableHead>
              <tr>
                <DataTableTh>Line</DataTableTh>
                <DataTableTh>Section</DataTableTh>
                <DataTableTh className="text-right">Amount</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {(cfPack?.lines?.length ? cfPack.lines : cfPack?.summary || []).map((r) => (
                <DataTableRow key={r.id || r.line}>
                  <DataTableTd className="text-sm">{r.line}</DataTableTd>
                  <DataTableTd className="text-xs text-[#737373] font-mono">{r.section || "—"}</DataTableTd>
                  <DataTableTd className="text-right font-mono text-xs">{formatMoney(r.amount)}</DataTableTd>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </SectionCard>
      ) : null}

      {view === "adj" ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <SectionCard kicker="WORKFLOW" title="Propose audit adjustment" bodyClassName="p-6">
            <form className="space-y-3 text-sm" onSubmit={submitAdjustment}>
              <div>
                <label className="text-[10px] font-mono uppercase text-[#737373]">Account code</label>
                <input name="account_code" className="mt-1 w-full bg-[#0A0A0A] border border-[#262626] px-3 h-9 font-mono text-xs" />
              </div>
              <div>
                <label className="text-[10px] font-mono uppercase text-[#737373]">Account name</label>
                <input name="account_name" className="mt-1 w-full bg-[#0A0A0A] border border-[#262626] px-3 h-9 text-xs" />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[10px] font-mono uppercase text-[#737373]">Debit</label>
                  <input name="debit" type="number" step="0.01" className="mt-1 w-full bg-[#0A0A0A] border border-[#262626] px-3 h-9 font-mono text-xs" />
                </div>
                <div>
                  <label className="text-[10px] font-mono uppercase text-[#737373]">Credit</label>
                  <input name="credit" type="number" step="0.01" className="mt-1 w-full bg-[#0A0A0A] border border-[#262626] px-3 h-9 font-mono text-xs" />
                </div>
              </div>
              <div>
                <label className="text-[10px] font-mono uppercase text-[#737373]">Narrative</label>
                <textarea name="narrative" rows={3} className="mt-1 w-full bg-[#0A0A0A] border border-[#262626] px-3 py-2 text-xs" />
              </div>
              <button type="submit" className="px-4 h-10 bg-white text-black font-mono text-xs uppercase">
                Save as proposed
              </button>
            </form>
          </SectionCard>
          <SectionCard kicker="QUEUE" title="Adjustments" bodyClassName="p-0">
            <DataTable className="rounded-none border-0">
              <DataTableHead>
                <tr>
                  <DataTableTh>Account</DataTableTh>
                  <DataTableTh>DR / CR</DataTableTh>
                  <DataTableTh>Status</DataTableTh>
                  <DataTableTh>Actions</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {adjustments.map((a) => (
                  <DataTableRow key={a.id}>
                    <DataTableTd className="font-mono text-xs">
                      {a.account_code}
                      <div className="text-[10px] text-[#737373] normal-case">{a.narrative?.slice(0, 80)}</div>
                    </DataTableTd>
                    <DataTableTd className="text-xs font-mono">
                      DR {formatMoney(a.debit)} / CR {formatMoney(a.credit)}
                    </DataTableTd>
                    <DataTableTd className="text-xs uppercase">{a.status}</DataTableTd>
                    <DataTableTd>
                      <div className="flex flex-wrap gap-1">
                        {["accepted", "rejected", "posted"].map((s) => (
                          <button
                            key={s}
                            type="button"
                            className="px-1.5 py-0.5 text-[9px] font-mono uppercase border border-[#262626] hover:border-white"
                            onClick={() => patchAdjStatus(a.id, s)}
                          >
                            {s}
                          </button>
                        ))}
                      </div>
                    </DataTableTd>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </DataTable>
          </SectionCard>
        </div>
      ) : null}

      {loading ? <div className="text-[10px] font-mono text-[#525252]">Loading…</div> : null}

      {fsSnap?.validation && view === "upload" ? (
        <SectionCard kicker="VALIDATION" title="Last FS snapshot checks" bodyClassName="p-4 text-xs font-mono text-[#A3A3A3] space-y-1">
          <div>TB balanced: {String(fsSnap.validation?.trial_balance_balanced)} · Equation delta: {fsSnap.validation?.accounting_equation_delta}</div>
          <div>Issues: {fsSnap.validation?.issue_total ?? 0}</div>
        </SectionCard>
      ) : null}

      <Dialog open={Boolean(drillCode)} onOpenChange={(o) => { if (!o) { setDrillCode(null); setDrillRow(null); } }}>
        <DialogContent className="max-w-lg bg-[#141414] border-[#262626] text-white">
          <DialogHeader>
            <DialogTitle className="font-mono text-sm uppercase">Ledger drilldown</DialogTitle>
          </DialogHeader>
          {drillLoading ? <div className="text-xs font-mono text-[#737373]">Loading…</div> : null}
          {!drillLoading && drillRow?.transactions ? (
            <div className="space-y-2">
              <div className="text-xs font-mono text-[#A3A3A3]">
                {drillRow.account_code} · {drillRow.account_name} · Net {formatMoney(drillRow.net_balance)}
              </div>
              <DataTable className="rounded-none border border-[#262626]">
                <DataTableHead>
                  <tr>
                    <DataTableTh>JE</DataTableTh>
                    <DataTableTh className="text-right">Debit</DataTableTh>
                    <DataTableTh className="text-right">Credit</DataTableTh>
                  </tr>
                </DataTableHead>
                <DataTableBody>
                  {drillRow.transactions.map((t) => (
                    <DataTableRow key={t.journal_id}>
                      <DataTableTd className="text-[10px] font-mono">{t.journal_id}</DataTableTd>
                      <DataTableTd className="text-right font-mono text-xs">{formatMoney(t.debit)}</DataTableTd>
                      <DataTableTd className="text-right font-mono text-xs">{formatMoney(t.credit)}</DataTableTd>
                    </DataTableRow>
                  ))}
                </DataTableBody>
              </DataTable>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}
