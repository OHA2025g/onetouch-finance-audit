import React, { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import clsx from "clsx";
import { http } from "../lib/api";
import { toast } from "sonner";
import { fmtUSD, fmtDate } from "../lib/format";
import { CaretLeft } from "@phosphor-icons/react";
import DrillContextBar from "../components/DrillContextBar";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { errorMessageFromAxios } from "../lib/apiErrorMessage";

export default function BankReconciliationDetailPage() {
  const { statementId } = useParams();
  const nav = useNavigate();
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const [classRef, setClassRef] = useState("");
  const [classType, setClassType] = useState("bank_fee");
  const [classNotes, setClassNotes] = useState("");
  const [signoffNotes, setSignoffNotes] = useState("");
  const [waiver, setWaiver] = useState(false);

  const load = useCallback(() => {
    if (!statementId) return Promise.resolve();
    setErr(null);
    return http
      .get(`/bank-recon/${encodeURIComponent(statementId)}`)
      .then((r) => setData(r.data))
      .catch((e) => setErr(errorMessageFromAxios(e, "Failed to load statement")));
  }, [statementId]);

  useEffect(() => {
    load();
  }, [load]);

  const runAction = async (label, fn) => {
    try {
      setBusy(true);
      await fn();
      toast.success(label);
      await load();
    } catch (e) {
      toast.error(errorMessageFromAxios(e, `${label} failed`));
    } finally {
      setBusy(false);
    }
  };

  if (err) {
    return (
      <PageShell maxWidth="max-w-[1100px]">
        <div className="p-8 font-mono text-xs text-[#FF9F0A]">{err}</div>
      </PageShell>
    );
  }
  if (!data?.statement) {
    return <div className="p-8 font-mono text-xs uppercase tracking-wider text-[#737373]">Loading bank statement…</div>;
  }

  const st = data.statement;
  const items = st.items || [];
  const status = String(st.status || "uploaded").toLowerCase();
  const canSignOff = status !== "signed_off";

  return (
    <PageShell maxWidth="max-w-[1100px]">
      <button
        type="button"
        onClick={() => nav(-1)}
        className="mb-2 flex items-center gap-1 text-xs font-mono uppercase tracking-wider text-muted-foreground transition-colors hover:text-foreground"
      >
        <CaretLeft size={12} /> Back
      </button>
      <DrillContextBar
        crumbs={[
          { label: "App", to: "/app" },
          { label: "Bank recon", to: "/app/financial-audit/bank-reconciliation-dashboard" },
          { label: st.id },
        ]}
      />
      <div data-testid="bank-recon-detail">
        <PageHeader
          kicker="BANK STATEMENT"
          title={`${st.bank_account_id || "Account"} · ${st.statement_period || "—"}`}
          subtitle={`${st.entity} · ${st.status} · ${items.length} lines`}
          right={
            <div className="flex flex-wrap gap-2" data-testid="br-detail-actions">
              {canSignOff && status === "uploaded" ? (
                <Button
                  type="button"
                  size="sm"
                  disabled={busy}
                  data-testid="br-action-auto-match"
                  onClick={() =>
                    runAction("Auto-match complete", () =>
                      http.post(`/bank-recon/${encodeURIComponent(statementId)}/auto-match`),
                    )
                  }
                >
                  Auto-match
                </Button>
              ) : null}
              {canSignOff ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={busy}
                  data-testid="br-action-signoff"
                  onClick={() =>
                    runAction("Signed off", () =>
                      http.post(`/bank-recon/${encodeURIComponent(statementId)}/signoff`, {
                        notes: signoffNotes.trim() || undefined,
                        acknowledge_residual_exceptions: waiver,
                      }),
                    )
                  }
                >
                  Sign off
                </Button>
              ) : null}
            </div>
          }
        />

        <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
          <div className="rounded-lg border border-zinc-200 p-3 text-xs dark:border-zinc-700">
            <div className="crt-num text-[10px] uppercase text-muted-foreground">Matched</div>
            <div className="mt-1 text-lg font-medium tabular-nums">{st.matched_count ?? 0}</div>
          </div>
          <div className="rounded-lg border border-zinc-200 p-3 text-xs dark:border-zinc-700">
            <div className="crt-num text-[10px] uppercase text-muted-foreground">Classified</div>
            <div className="mt-1 text-lg font-medium tabular-nums">{st.classified_count ?? 0}</div>
          </div>
          <div className="rounded-lg border border-zinc-200 p-3 text-xs dark:border-zinc-700">
            <div className="crt-num text-[10px] uppercase text-muted-foreground">Unmatched</div>
            <div className={clsx("mt-1 text-lg font-medium tabular-nums", (st.unmatched_count || 0) > 0 && "text-rose-600")}>
              {st.unmatched_count ?? 0}
            </div>
          </div>
          <div className="rounded-lg border border-zinc-200 p-3 text-xs dark:border-zinc-700">
            <div className="crt-num text-[10px] uppercase text-muted-foreground">Lines</div>
            <div className="mt-1 text-lg font-medium tabular-nums">{st.line_count ?? items.length}</div>
          </div>
        </div>

        {canSignOff ? (
          <SectionCard kicker="CLASSIFY" title="Classify unmatched line" className="mb-6">
            <div className="grid gap-3 p-4 sm:grid-cols-4">
              <Input placeholder="Reference" value={classRef} onChange={(e) => setClassRef(e.target.value)} data-testid="br-classify-ref" />
              <Input placeholder="Classification" value={classType} onChange={(e) => setClassType(e.target.value)} data-testid="br-classify-type" />
              <Input placeholder="Notes" value={classNotes} onChange={(e) => setClassNotes(e.target.value)} data-testid="br-classify-notes" />
              <Button
                type="button"
                size="sm"
                disabled={busy || !classRef.trim()}
                data-testid="br-action-classify"
                onClick={() =>
                  runAction("Classified", () =>
                    http.post(`/bank-recon/${encodeURIComponent(statementId)}/classify`, {
                      items: [{ reference: classRef.trim(), classification: classType.trim(), notes: classNotes.trim() || undefined }],
                    }),
                  ).then(() => {
                    setClassRef("");
                    setClassNotes("");
                  })
                }
              >
                Apply
              </Button>
            </div>
            <div className="border-t border-zinc-200 px-4 pb-4 dark:border-zinc-700">
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                <input type="checkbox" checked={waiver} onChange={(e) => setWaiver(e.target.checked)} data-testid="br-waiver-checkbox" />
                Acknowledge residual unmatched lines on sign-off
              </label>
              <Input
                className="mt-2"
                placeholder="Sign-off notes"
                value={signoffNotes}
                onChange={(e) => setSignoffNotes(e.target.value)}
                data-testid="br-signoff-notes"
              />
            </div>
          </SectionCard>
        ) : null}

        <SectionCard kicker="LINES" title="Statement lines">
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[50vh]" testId="br-lines-table">
            <DataTableHead>
              <tr>
                <DataTableTh>Date</DataTableTh>
                <DataTableTh>Reference</DataTableTh>
                <DataTableTh>Status</DataTableTh>
                <DataTableTh align="right">Amount</DataTableTh>
                <DataTableTh>Book match</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {items.map((line, idx) => (
                <DataTableRow key={`${line.reference}-${idx}`} testId={`br-line-${idx}`}>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{line.date ? fmtDate(line.date) : "—"}</DataTableTd>
                  <DataTableTd className="crt-num text-xs font-mono">{line.reference || "—"}</DataTableTd>
                  <DataTableTd className="crt-num text-[10px] uppercase">{line.match_status || "—"}</DataTableTd>
                  <DataTableTd align="right" className="crt-num tabular-nums">
                    {fmtUSD(line.amount)}
                  </DataTableTd>
                  <DataTableTd className="text-xs text-muted-foreground">
                    {line.book_match ? `${line.book_match.type} · ${line.book_match.id || line.book_match.rule || ""}` : line.classification || "—"}
                  </DataTableTd>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </SectionCard>

        <Link
          to="/app/financial-audit/reconciliations-dashboard"
          className="mt-4 inline-block text-xs font-mono uppercase text-primary hover:underline"
          data-testid="br-phase17-link"
        >
          Phase 17 reconciliation packages →
        </Link>
      </div>
    </PageShell>
  );
}
