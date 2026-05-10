import React, { useCallback, useEffect, useState } from "react";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useMastersFilters } from "../lib/MastersFilterContext";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { StatCard } from "../components/StatCard";
import { fmtDateTime, fmtUSD } from "../lib/format";
import { errorMessageFromAxios } from "../lib/apiErrorMessage";

function safeStr(v) {
  if (v == null) return "";
  return String(v);
}

function validateBudgetDraft({ name, periodYm, glAccount, amount }) {
  if (!safeStr(name).trim()) return "Budget name is required.";
  const p = safeStr(periodYm).trim();
  if (p && !/^\d{4}-\d{2}$/.test(p)) return "Period must be YYYY-MM (e.g. 2026-04) or left empty.";
  if (!safeStr(glAccount).trim()) return "GL account is required for the line item.";
  const amt = Number(amount);
  if (!Number.isFinite(amt)) return "Amount must be a valid number.";
  return null;
}

export default function BudgetMasterPage() {
  const { entityCode } = useMastersFilters();
  const dashboardParams = useDashboardFilterParams();
  const [versions, setVersions] = useState({ items: [], count: 0, note: "" });
  const [list, setList] = useState({ items: [], count: 0 });
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("Budget v1");
  const [periodYm, setPeriodYm] = useState("");
  const [glAccount, setGlAccount] = useState("6100");
  const [amount, setAmount] = useState("100000");

  const refresh = useCallback(() => {
    http
      .get("/budget/versions", { params: dashboardParams })
      .then((r) => setVersions({ items: r.data?.items || [], count: r.data?.count || 0, note: r.data?.note || "" }))
      .catch((e) => toast.error(errorMessageFromAxios(e, "Failed to load budget versions")));
    http
      .get("/budget", { params: dashboardParams })
      .then((r) => setList({ items: r.data?.items || [], count: r.data?.count || 0 }))
      .catch((e) => toast.error(errorMessageFromAxios(e, "Failed to load budgets")));
  }, [dashboardParams]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const createDraft = async () => {
    const msg = validateBudgetDraft({ name, periodYm, glAccount, amount });
    if (msg) {
      toast.error(msg);
      return;
    }
    try {
      setCreating(true);
      const lines = [
        {
          period_ym: safeStr(periodYm).trim() || undefined,
          gl_account: safeStr(glAccount).trim() || undefined,
          amount: Number(amount),
        },
      ];
      await http.post("/budget/upload", {
        name: safeStr(name).trim() || "Budget",
        entity: dashboardParams.entity_code || entityCode || undefined,
        status: "draft",
        locked: false,
        lines,
      });
      toast.success("Budget draft created");
      refresh();
    } catch (e) {
      toast.error(errorMessageFromAxios(e, "Failed to create budget draft"));
    } finally {
      setCreating(false);
    }
  };

  const doAction = async (id, action) => {
    try {
      await http.post(`/budget/${encodeURIComponent(id)}/${action}`);
      toast.success(`${action} ok`);
      refresh();
    } catch (e) {
      toast.error(errorMessageFromAxios(e, `Failed to ${action}`));
    }
  };

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="budget-master-page">
        <PageHeader
          kicker="BUDGET MASTER · PHASE 12"
          title="Budget versions, approvals & locking"
          subtitle="Backed by /budget list + versions + upload + approve/lock/unlock APIs."
        />

        <MastersFilterStrip className="mb-6" />

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
          <StatCard label="Budget versions" value={versions.count} testId="budget-versions-count" />
          <StatCard label="Budgets listed" value={list.count} testId="budget-list-count" />
          <StatCard label="Entity scope" value={entityCode || "All"} testId="budget-entity" />
          <StatCard label="Uploads" value="API" testId="budget-upload-mode" />
          <StatCard label="Approvals" value="API" testId="budget-approve-mode" />
          <StatCard label="Locks" value="API" testId="budget-lock-mode" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <SectionCard kicker="CREATE" title="Create budget draft (JSON payload)">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <div className="crt-num mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">Name</div>
                <input
                  value={name}
                  onChange={(e) => setName(safeStr(e.target.value))}
                  className="w-full rounded-sm border border-zinc-200 bg-white px-3 py-2 text-sm text-foreground outline-none dark:border-zinc-800 dark:bg-zinc-950"
                  data-testid="budget-name"
                />
              </div>
              <div>
                <div className="crt-num mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">Period (optional)</div>
                <input
                  value={periodYm}
                  onChange={(e) => setPeriodYm(safeStr(e.target.value))}
                  placeholder="2026-04"
                  className="w-full rounded-sm border border-zinc-200 bg-white px-3 py-2 text-sm text-foreground outline-none dark:border-zinc-800 dark:bg-zinc-950"
                  data-testid="budget-period"
                />
              </div>
              <div>
                <div className="crt-num mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">GL account</div>
                <input
                  value={glAccount}
                  onChange={(e) => setGlAccount(safeStr(e.target.value))}
                  className="w-full rounded-sm border border-zinc-200 bg-white px-3 py-2 text-sm text-foreground outline-none dark:border-zinc-800 dark:bg-zinc-950"
                  data-testid="budget-gl"
                />
              </div>
              <div>
                <div className="crt-num mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">Amount</div>
                <input
                  value={amount}
                  onChange={(e) => setAmount(safeStr(e.target.value))}
                  className="w-full rounded-sm border border-zinc-200 bg-white px-3 py-2 text-sm text-foreground outline-none dark:border-zinc-800 dark:bg-zinc-950"
                  data-testid="budget-amount"
                />
              </div>
            </div>
            {versions.note ? (
              <p className="crt-num mt-3 text-[10px] uppercase tracking-wider text-muted-foreground">{versions.note}</p>
            ) : null}
            <button
              type="button"
              disabled={creating}
              onClick={createDraft}
              className="crt-num mt-4 w-full rounded-sm border border-zinc-200 bg-zinc-50 px-3 py-2 text-[10px] uppercase tracking-wider text-foreground hover:bg-zinc-100 disabled:opacity-60 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:bg-zinc-800"
              data-testid="budget-create"
            >
              {creating ? "Creating…" : "Create draft"}
            </button>
          </SectionCard>

          <SectionCard kicker="VERSIONS" title="Budget versions">
            <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[55vh]" testId="budget-versions-table">
              <DataTableHead>
                <tr>
                  <DataTableTh>ID</DataTableTh>
                  <DataTableTh>Status</DataTableTh>
                  <DataTableTh>Locked</DataTableTh>
                  <DataTableTh>Created</DataTableTh>
                  <DataTableTh align="right">Actions</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {versions.items.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                      No budget versions in scope.
                    </td>
                  </tr>
                ) : null}
                {versions.items.map((b) => (
                  <DataTableRow key={b.id}>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">{b.id}</DataTableTd>
                    <DataTableTd className="text-sm text-foreground">{b.status || "—"}</DataTableTd>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">{b.locked ? "Yes" : "No"}</DataTableTd>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">{fmtDateTime(b.created_at)}</DataTableTd>
                    <DataTableTd align="right">
                      <div className="flex justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => doAction(b.id, "approve")}
                          className="crt-num rounded-sm border border-zinc-200 bg-white px-2 py-1 text-[10px] uppercase tracking-wider hover:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-950 dark:hover:bg-zinc-900"
                        >
                          Approve
                        </button>
                        {b.locked ? (
                          <button
                            type="button"
                            onClick={() => doAction(b.id, "unlock")}
                            className="crt-num rounded-sm border border-zinc-200 bg-white px-2 py-1 text-[10px] uppercase tracking-wider hover:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-950 dark:hover:bg-zinc-900"
                          >
                            Unlock
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={() => doAction(b.id, "lock")}
                            className="crt-num rounded-sm border border-zinc-200 bg-white px-2 py-1 text-[10px] uppercase tracking-wider hover:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-950 dark:hover:bg-zinc-900"
                          >
                            Lock
                          </button>
                        )}
                      </div>
                    </DataTableTd>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </DataTable>
          </SectionCard>
        </div>

        <div className="mt-4">
          <SectionCard kicker="SUMMARY" title="Latest budget totals (informational)">
            <div className="crt-num text-xs text-muted-foreground">
              This page focuses on budget governance (upload/approve/lock). Budget vs actual and variance workflows are in Phase 13.
            </div>
            <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-3">
              <StatCard
                label="Latest version lines"
                value={(versions.items?.[0]?.lines || []).length}
                testId="budget-lines-count"
              />
              <StatCard
                label="Latest version total"
                value={fmtUSD(
                  (versions.items?.[0]?.lines || []).reduce((acc, ln) => acc + Number(ln.amount || 0), 0),
                )}
                testId="budget-lines-total"
              />
              <StatCard label="Approved by" value={versions.items?.[0]?.approved_by || "—"} testId="budget-approved-by" />
              <StatCard label="Locked" value={versions.items?.[0]?.locked ? "Yes" : "No"} testId="budget-locked" />
            </div>
          </SectionCard>
        </div>
      </div>
    </PageShell>
  );
}

