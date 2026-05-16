import React, { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useMastersFilters } from "../lib/MastersFilterContext";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import { StatCard } from "../components/StatCard";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { errorMessageFromAxios } from "../lib/apiErrorMessage";

const SAMPLE_CSV = `date,amount,direction,reference
2026-04-05,5000,outbound,WIRE-90001
2026-04-06,1200,outbound,CARD-XYZ-1`;

export default function BankReconciliationWorkbenchPage() {
  const navigate = useNavigate();
  const { hrefWithMasterParams } = useMastersFilters();
  const [items, setItems] = useState(null);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [bankAccountId, setBankAccountId] = useState("BA-100");
  const [statementPeriod, setStatementPeriod] = useState("2026-04");
  const [csvText, setCsvText] = useState(SAMPLE_CSV);

  const params = useDashboardFilterParams();

  const refresh = useCallback(() => {
    setLoading(true);
    const qp = { entity_code: params.entity_code, limit: 50 };
    return Promise.all([http.get("/bank-recon/summary", { params }), http.get("/bank-recon/statements", { params: qp })])
      .then(([sumRes, listRes]) => {
        setSummary(sumRes.data || {});
        setItems(listRes.data?.items || []);
      })
      .catch((e) => toast.error(errorMessageFromAxios(e, "Failed to load bank reconciliation")))
      .finally(() => setLoading(false));
  }, [params.entity_code]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const openStatement = (st) => {
    if (!st?.id) return;
    navigate(hrefWithMasterParams(`/app/bank-recon/${encodeURIComponent(st.id)}`));
  };

  const uploadCsv = async () => {
    if (!params.entity_code) {
      toast.error("Select an entity in the filter strip first");
      return;
    }
    try {
      setUploading(true);
      const res = await http.post("/bank-recon/upload-statement/csv", {
        entity: params.entity_code,
        bank_account_id: bankAccountId,
        statement_period: statementPeriod,
        csv_text: csvText,
      });
      toast.success(`Statement uploaded (${res.data?.statement_id})`);
      refresh();
    } catch (e) {
      toast.error(errorMessageFromAxios(e, "Upload failed"));
    } finally {
      setUploading(false);
    }
  };

  if (loading && items === null) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="bank-recon-loading">
        Loading bank reconciliation…
      </div>
    );
  }

  const k = summary?.kpis || {};
  const rows = items || [];

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="bank-recon-workbench-page" data-bank-recon-surface="true">
        <PageHeader
          kicker="BANK RECON · PHASE 18"
          title="Bank reconciliation automation"
          subtitle="Upload CSV · auto-match to payments & bank transactions · classify exceptions · sign-off."
        />

        <MastersFilterStrip className="mb-6" />

        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-6 mb-4" data-testid="br-kpi-strip">
          <StatCard label="Statements" value={k.total_statements ?? rows.length} testId="br-kpi-statements" />
          <StatCard label="Pending sign-off" value={k.pending_signoff_count ?? 0} severity="warning" testId="br-kpi-pending-signoff" />
          <StatCard label="Signed off" value={k.signed_off_count ?? 0} severity="low" testId="br-kpi-signed-off" />
          <StatCard label="Total lines" value={k.total_lines ?? 0} testId="br-kpi-total-lines" />
          <StatCard label="Matched lines" value={k.total_matched_lines ?? 0} testId="br-kpi-matched-lines" />
          <StatCard label="Unmatched lines" value={k.total_unmatched_lines ?? 0} severity="critical" testId="br-kpi-unmatched-lines" />
        </div>

        <SectionCard kicker="UPLOAD" title="Import bank statement (CSV)" className="mb-6">
          <div className="grid gap-3 p-4 lg:grid-cols-2">
            <div className="space-y-2">
              <Input value={bankAccountId} onChange={(e) => setBankAccountId(e.target.value)} placeholder="Bank account id" data-testid="br-upload-account" />
              <Input value={statementPeriod} onChange={(e) => setStatementPeriod(e.target.value)} placeholder="Period YYYY-MM" data-testid="br-upload-period" />
              <Button type="button" size="sm" disabled={uploading} onClick={uploadCsv} data-testid="br-upload-csv-btn">
                {uploading ? "Uploading…" : "Upload CSV statement"}
              </Button>
            </div>
            <textarea
              className="min-h-[120px] w-full rounded-md border border-zinc-300 bg-transparent p-3 font-mono text-xs dark:border-zinc-600"
              value={csvText}
              onChange={(e) => setCsvText(e.target.value)}
              data-testid="br-upload-csv-text"
            />
          </div>
        </SectionCard>

        <SectionCard kicker="STATEMENTS" title="Bank statement uploads">
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[52vh]" testId="br-statements-table">
            <DataTableHead>
              <tr>
                <DataTableTh>Statement</DataTableTh>
                <DataTableTh>Account</DataTableTh>
                <DataTableTh>Period</DataTableTh>
                <DataTableTh>Entity</DataTableTh>
                <DataTableTh>Status</DataTableTh>
                <DataTableTh align="right">Matched</DataTableTh>
                <DataTableTh align="right">Unmatched</DataTableTh>
                <DataTableTh />
              </tr>
            </DataTableHead>
            <DataTableBody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={8} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                    No bank statements — upload CSV above (select entity first).
                  </td>
                </tr>
              ) : null}
              {rows.map((st) => (
                <DataTableRow key={st.id} testId={`br-row-${st.id}`} onClick={() => openStatement(st)}>
                  <DataTableTd className="crt-num text-xs font-mono text-muted-foreground">{st.id}</DataTableTd>
                  <DataTableTd className="text-sm text-foreground">{st.bank_account_id || "—"}</DataTableTd>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{st.statement_period || "—"}</DataTableTd>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{st.entity || "—"}</DataTableTd>
                  <DataTableTd className="crt-num text-xs uppercase text-muted-foreground">{st.status || "—"}</DataTableTd>
                  <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                    {st.matched_count ?? "—"}
                  </DataTableTd>
                  <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                    {st.unmatched_count ?? "—"}
                  </DataTableTd>
                  <DataTableTd>
                    <span className="crt-num text-[10px] uppercase text-primary">Open →</span>
                  </DataTableTd>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </SectionCard>
      </div>
    </PageShell>
  );
}
