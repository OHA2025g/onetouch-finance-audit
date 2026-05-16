import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
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

function governanceFromItems(items) {
  const rows = items || [];
  return {
    uploads: rows.length,
    draft: rows.filter((v) => (v.status || "draft") === "draft").length,
    approved: rows.filter((v) => v.status === "approved").length,
    locked: rows.filter((v) => v.locked).length,
  };
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
  const fileRef = useRef(null);
  const [loading, setLoading] = useState(true);
  const [versions, setVersions] = useState({ items: [], count: 0, note: "", governance: null });
  const [list, setList] = useState({ items: [], count: 0, governance: null });
  const [creating, setCreating] = useState(false);
  const [uploadingFile, setUploadingFile] = useState(false);
  const [name, setName] = useState("Budget v1");
  const [periodYm, setPeriodYm] = useState("");
  const [glAccount, setGlAccount] = useState("6100");
  const [amount, setAmount] = useState("100000");

  const refresh = useCallback(() => {
    setLoading(true);
    return Promise.all([
      http.get("/budget/versions", { params: dashboardParams }),
      http.get("/budget", { params: dashboardParams }),
    ])
      .then(([verRes, listRes]) => {
        setVersions({
          items: verRes.data?.items || [],
          count: verRes.data?.count || 0,
          note: verRes.data?.note || "",
          governance: verRes.data?.governance || null,
        });
        setList({
          items: listRes.data?.items || [],
          count: listRes.data?.count || 0,
          governance: listRes.data?.governance || null,
        });
      })
      .catch((e) => toast.error(errorMessageFromAxios(e, "Failed to load budgets")))
      .finally(() => setLoading(false));
  }, [dashboardParams]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const governance = useMemo(() => {
    return versions.governance || list.governance || governanceFromItems(versions.items);
  }, [versions.governance, list.governance, versions.items]);

  const scopeEntity = dashboardParams.entity_code || entityCode || "All";

  const postUpload = async (payload) => {
    const body = {
      ...payload,
      entity: payload.entity || dashboardParams.entity_code || entityCode || undefined,
      status: payload.status || "draft",
      locked: Boolean(payload.locked),
    };
    await http.post("/budget/upload", body);
    toast.success("Budget uploaded");
    refresh();
  };

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
          account_code: safeStr(glAccount).trim() || undefined,
          amount: Number(amount),
        },
      ];
      await postUpload({
        name: safeStr(name).trim() || "Budget",
        lines,
      });
    } catch (e) {
      toast.error(errorMessageFromAxios(e, "Failed to create budget draft"));
    } finally {
      setCreating(false);
    }
  };

  const onFileSelected = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    try {
      setUploadingFile(true);
      const text = await file.text();
      const payload = JSON.parse(text);
      if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
        throw new Error("JSON must be an object with name and optional lines[]");
      }
      await postUpload(payload);
    } catch (err) {
      toast.error(err?.message || "Invalid budget JSON file");
    } finally {
      setUploadingFile(false);
    }
  };

  const doAction = async (id, action) => {
    try {
      await http.post(`/budget/${encodeURIComponent(id)}/${action}`);
      toast.success(`${action} completed`);
      refresh();
    } catch (e) {
      toast.error(errorMessageFromAxios(e, `Failed to ${action}`));
    }
  };

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div
        data-testid="budget-master-page"
        data-budget-master-surface="true"
      >
        <PageHeader
          kicker="BUDGET MASTER · PHASE 12"
          title="Budget versions, approvals & locking"
          subtitle="POST /budget/upload · POST /budget/{id}/approve · lock · unlock — live governance counts below."
        />

        <MastersFilterStrip className="mb-6" />

        {loading ? (
          <p className="crt-num mb-6 text-[10px] uppercase tracking-wider text-muted-foreground" data-testid="budget-loading">
            Loading budgets…
          </p>
        ) : null}

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
          <StatCard label="Budget versions" value={versions.count} testId="budget-versions-count" />
          <StatCard label="Uploads" value={governance.uploads} testId="budget-upload-count" />
          <StatCard label="Draft" value={governance.draft} testId="budget-draft-count" />
          <StatCard label="Approved" value={governance.approved} testId="budget-approved-count" />
          <StatCard label="Locked" value={governance.locked} testId="budget-locked-count" />
          <StatCard label="Entity scope" value={scopeEntity} testId="budget-entity" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <SectionCard kicker="UPLOAD" title="Create or import budget (POST /budget/upload)">
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
            <div className="mt-4 flex flex-col gap-2 sm:flex-row">
              <button
                type="button"
                disabled={creating}
                onClick={createDraft}
                className="crt-num flex-1 rounded-sm border border-zinc-200 bg-zinc-50 px-3 py-2 text-[10px] uppercase tracking-wider text-foreground hover:bg-zinc-100 disabled:opacity-60 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:bg-zinc-800"
                data-testid="budget-create"
              >
                {creating ? "Creating…" : "Create draft"}
              </button>
              <input
                ref={fileRef}
                type="file"
                accept="application/json,.json"
                className="hidden"
                data-testid="budget-file-input"
                onChange={onFileSelected}
              />
              <button
                type="button"
                disabled={uploadingFile}
                onClick={() => fileRef.current?.click()}
                className="crt-num flex-1 rounded-sm border border-zinc-200 bg-white px-3 py-2 text-[10px] uppercase tracking-wider text-foreground hover:bg-zinc-50 disabled:opacity-60 dark:border-zinc-800 dark:bg-zinc-950 dark:hover:bg-zinc-900"
                data-testid="budget-upload-file"
              >
                {uploadingFile ? "Uploading…" : "Import JSON file"}
              </button>
            </div>
          </SectionCard>

          <SectionCard kicker="GOVERNANCE" title="Approve & lock (per version)">
            <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[55vh]" testId="budget-versions-table">
              <DataTableHead>
                <tr>
                  <DataTableTh>Name</DataTableTh>
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
                {versions.items.map((b) => {
                  const isApproved = b.status === "approved";
                  const isLocked = Boolean(b.locked);
                  return (
                    <DataTableRow key={b.id}>
                      <DataTableTd className="text-sm text-foreground">{b.name || b.id}</DataTableTd>
                      <DataTableTd className="text-sm text-foreground">{b.status || "draft"}</DataTableTd>
                      <DataTableTd className="crt-num text-xs text-muted-foreground">{isLocked ? "Yes" : "No"}</DataTableTd>
                      <DataTableTd className="crt-num text-xs text-muted-foreground">{fmtDateTime(b.created_at)}</DataTableTd>
                      <DataTableTd align="right">
                        <div className="flex justify-end gap-2">
                          <button
                            type="button"
                            disabled={isApproved || isLocked}
                            onClick={() => doAction(b.id, "approve")}
                            className="crt-num rounded-sm border border-zinc-200 bg-white px-2 py-1 text-[10px] uppercase tracking-wider hover:bg-zinc-50 disabled:opacity-40 dark:border-zinc-800 dark:bg-zinc-950 dark:hover:bg-zinc-900"
                            data-testid={`budget-approve-${b.id}`}
                          >
                            Approve
                          </button>
                          {isLocked ? (
                            <button
                              type="button"
                              onClick={() => doAction(b.id, "unlock")}
                              className="crt-num rounded-sm border border-zinc-200 bg-white px-2 py-1 text-[10px] uppercase tracking-wider hover:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-950 dark:hover:bg-zinc-900"
                              data-testid={`budget-unlock-${b.id}`}
                            >
                              Unlock
                            </button>
                          ) : (
                            <button
                              type="button"
                              disabled={!isApproved}
                              onClick={() => doAction(b.id, "lock")}
                              className="crt-num rounded-sm border border-zinc-200 bg-white px-2 py-1 text-[10px] uppercase tracking-wider hover:bg-zinc-50 disabled:opacity-40 dark:border-zinc-800 dark:bg-zinc-950 dark:hover:bg-zinc-900"
                              data-testid={`budget-lock-${b.id}`}
                              title={!isApproved ? "Approve before locking" : undefined}
                            >
                              Lock
                            </button>
                          )}
                        </div>
                      </DataTableTd>
                    </DataTableRow>
                  );
                })}
              </DataTableBody>
            </DataTable>
          </SectionCard>
        </div>

        <div className="mt-4">
          <SectionCard kicker="SUMMARY" title="Latest version snapshot">
            <div className="crt-num text-xs text-muted-foreground">
              Listed budgets: {list.count}. Budget vs actual and variance workflows are on the Budget vs Actual page (Phase 13).
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
              <StatCard
                label="Latest locked"
                value={versions.items?.[0]?.locked ? "Yes" : "No"}
                testId="budget-latest-locked"
              />
            </div>
          </SectionCard>
        </div>
      </div>
    </PageShell>
  );
}
