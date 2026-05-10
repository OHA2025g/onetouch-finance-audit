import React, { useEffect, useState } from "react";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import { StatCard } from "../components/StatCard";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { fmtDate, fmtUSD } from "../lib/format";
import { errorMessageFromAxios } from "../lib/apiErrorMessage";

function safeStr(v) {
  if (v == null) return "";
  return String(v);
}

export default function ReceivablesArAgeingPage() {
  const [ageing, setAgeing] = useState(null);
  const [ageingLoading, setAgeingLoading] = useState(true);
  const [cust, setCust] = useState({ items: [], total: 0 });
  const [inv, setInv] = useState({ items: [], total: 0 });
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("overdue");

  const params = useDashboardFilterParams();
  useEffect(() => {
    let alive = true;
    setAgeingLoading(true);
    http
      .get("/working-capital/ar-ageing", { params })
      .then((r) => {
        if (!alive) return;
        setAgeing(r.data);
      })
      .catch((e) => {
        if (!alive) return;
        setAgeing({});
        toast.error(errorMessageFromAxios(e, "Failed to load AR ageing"));
      })
      .finally(() => {
        if (alive) setAgeingLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [params]);

  useEffect(() => {
    let alive = true;
    http
      .get("/ar/customers", { params: { ...params, q: q || undefined, limit: 200, offset: 0 } })
      .then((r) => {
        if (!alive) return;
        setCust({ items: r.data?.items || [], total: r.data?.total || 0 });
      })
      .catch((e) => toast.error(errorMessageFromAxios(e, "Failed to load customers")));
    return () => {
      alive = false;
    };
  }, [params, q]);

  useEffect(() => {
    let alive = true;
    http
      .get("/ar/invoices", {
        params: {
          ...params,
          status: status || undefined,
          limit: 200,
          offset: 0,
        },
      })
      .then((r) => {
        if (!alive) return;
        setInv({ items: r.data?.items || [], total: r.data?.total || 0 });
      })
      .catch((e) => toast.error(errorMessageFromAxios(e, "Failed to load AR invoices")));
    return () => {
      alive = false;
    };
  }, [params, status]);

  if (ageingLoading) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="ar-receivables-loading">
        Loading receivables…
      </div>
    );
  }

  const arBuckets = (ageing || {}).ar_ageing || (ageing || {}).ar_aging || [];
  const top = (ageing || {}).top_overdue_ar || [];
  const totalOpen = (ageing || {}).ar_open_total ?? 0;

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="ar-receivables-page">
        <PageHeader
          kicker="RECEIVABLES · PHASE 9"
          title="AR ageing, disputes & collections"
          subtitle="Dedicated AR module surface backed by /working-capital/ar-ageing + /ar/customers + /ar/invoices endpoints."
        />

        <MastersFilterStrip className="mb-6" />

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
          <StatCard label="AR open total" value={fmtUSD(totalOpen)} testId="ar-open-total" />
          <StatCard label="Overdue invoices (top list)" value={top.length} severity="warning" testId="ar-top-overdue-count" />
          <StatCard label="Buckets" value={arBuckets.length} testId="ar-buckets-count" />
          <StatCard label="Customers" value={cust.total} testId="ar-customers-count" />
          <StatCard label="Invoices loaded" value={inv.items.length} testId="ar-invoices-loaded" />
          <StatCard label="Entity scope" value={params.entity_code || "All"} testId="ar-entity-scope" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <SectionCard kicker="AGEING" title="AR ageing buckets">
            <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[45vh]" testId="ar-ageing-table">
              <DataTableHead>
                <tr>
                  <DataTableTh>Bucket</DataTableTh>
                  <DataTableTh align="right">Count</DataTableTh>
                  <DataTableTh align="right">Amount</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {arBuckets.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                      No ageing buckets in scope.
                    </td>
                  </tr>
                ) : null}
                {arBuckets.map((b, i) => (
                  <DataTableRow key={`${b.bucket || b.label || i}`}>
                    <DataTableTd className="text-sm text-foreground">{b.bucket || b.label || "—"}</DataTableTd>
                    <DataTableTd align="right" className="crt-num tabular-nums text-muted-foreground">
                      {b.count ?? "—"}
                    </DataTableTd>
                    <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                      {fmtUSD(b.amount ?? b.total_amount ?? 0)}
                    </DataTableTd>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </DataTable>
          </SectionCard>

          <SectionCard kicker="COLLECTIONS" title="Top overdue invoices">
            <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[45vh]" testId="ar-top-overdue-table">
              <DataTableHead>
                <tr>
                  <DataTableTh>Customer</DataTableTh>
                  <DataTableTh>Invoice</DataTableTh>
                  <DataTableTh>Due</DataTableTh>
                  <DataTableTh align="right">Amount</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {top.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                      No overdue AR in scope.
                    </td>
                  </tr>
                ) : null}
                {top.map((r) => (
                  <DataTableRow key={r.id || `${r.customer_id}-${r.invoice_number}`}>
                    <DataTableTd className="text-sm text-foreground">{r.customer_name || r.customer_id || "—"}</DataTableTd>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">{r.invoice_number || r.id}</DataTableTd>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">{fmtDate(r.due_date)}</DataTableTd>
                    <DataTableTd align="right" className="crt-num tabular-nums text-[hsl(var(--destructive))]">
                      {fmtUSD(r.amount)}
                    </DataTableTd>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </DataTable>
          </SectionCard>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4">
          <SectionCard kicker="CUSTOMERS" title="Customer register (scoped)">
            <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div className="crt-num text-[10px] uppercase tracking-wider text-muted-foreground">
                Search by name/code/id (entity scope applies).
              </div>
              <input
                value={q}
                onChange={(e) => setQ(safeStr(e.target.value))}
                placeholder="Search customers…"
                className="w-full sm:w-[280px] rounded-sm border border-zinc-200 bg-white px-3 py-2 text-sm text-foreground outline-none dark:border-zinc-800 dark:bg-zinc-950"
                data-testid="ar-customer-search"
              />
            </div>
            <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[45vh]" testId="ar-customers-table">
              <DataTableHead>
                <tr>
                  <DataTableTh>Customer</DataTableTh>
                  <DataTableTh>Code</DataTableTh>
                  <DataTableTh>Entity</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {cust.items.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                      No customers match the current filter.
                    </td>
                  </tr>
                ) : null}
                {cust.items.map((c) => (
                  <DataTableRow key={c.id}>
                    <DataTableTd className="text-sm text-foreground">{c.customer_name || c.name || "—"}</DataTableTd>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">{c.customer_code || c.code || c.id}</DataTableTd>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">{c.entity || "—"}</DataTableTd>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </DataTable>
          </SectionCard>

          <SectionCard kicker="INVOICES" title="Invoice register (scoped)">
            <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div className="crt-num text-[10px] uppercase tracking-wider text-muted-foreground">
                Status filter drives API query (no client-side truncation).
              </div>
              <select
                value={status}
                onChange={(e) => setStatus(safeStr(e.target.value))}
                className="w-full sm:w-[220px] rounded-sm border border-zinc-200 bg-white px-3 py-2 text-sm text-foreground outline-none dark:border-zinc-800 dark:bg-zinc-950"
                data-testid="ar-invoice-status"
              >
                <option value="">All</option>
                <option value="open">Open</option>
                <option value="overdue">Overdue</option>
                <option value="paid">Paid</option>
              </select>
            </div>
            <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[45vh]" testId="ar-invoices-table">
              <DataTableHead>
                <tr>
                  <DataTableTh>Invoice</DataTableTh>
                  <DataTableTh>Customer</DataTableTh>
                  <DataTableTh>Due</DataTableTh>
                  <DataTableTh align="right">Amount</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {inv.items.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                      No invoices match the current filter.
                    </td>
                  </tr>
                ) : null}
                {inv.items.map((r) => (
                  <DataTableRow key={r.id}>
                    <DataTableTd className="text-sm text-foreground">{r.invoice_number || r.id}</DataTableTd>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">{r.customer_name || r.customer_id || "—"}</DataTableTd>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">{fmtDate(r.due_date || r.due_ts)}</DataTableTd>
                    <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                      {fmtUSD(r.amount)}
                    </DataTableTd>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </DataTable>
          </SectionCard>
        </div>
      </div>
    </PageShell>
  );
}

