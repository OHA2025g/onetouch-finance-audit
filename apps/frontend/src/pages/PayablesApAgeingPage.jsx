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

export default function PayablesApAgeingPage() {
  const [ageing, setAgeing] = useState(null);
  const [ageingLoading, setAgeingLoading] = useState(true);
  const [vendors, setVendors] = useState({ items: [], total: 0 });
  const [invoices, setInvoices] = useState({ items: [], total: 0 });
  const [calendar, setCalendar] = useState({ items: [], count: 0 });
  const [prio, setPrio] = useState({ items: [], count: 0, note: "" });
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("overdue");
  const [holdInvoiceId, setHoldInvoiceId] = useState("");
  const [holdReason, setHoldReason] = useState("");

  const params = useDashboardFilterParams();
  useEffect(() => {
    let alive = true;
    setAgeingLoading(true);
    http
      .get("/working-capital/ap-ageing", { params })
      .then((r) => {
        if (!alive) return;
        setAgeing(r.data);
      })
      .catch((e) => {
        if (!alive) return;
        setAgeing({});
        toast.error(errorMessageFromAxios(e, "Failed to load AP ageing"));
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
      .get("/ap/vendors", { params: { ...params, q: q || undefined, limit: 200, offset: 0 } })
      .then((r) => {
        if (!alive) return;
        setVendors({ items: r.data?.items || [], total: r.data?.total || 0 });
      })
      .catch((e) => toast.error(errorMessageFromAxios(e, "Failed to load vendors")));
    return () => {
      alive = false;
    };
  }, [params, q]);

  useEffect(() => {
    let alive = true;
    http
      .get("/ap/invoices", {
        params: {
          ...params,
          status: status || undefined,
          limit: 200,
          offset: 0,
        },
      })
      .then((r) => {
        if (!alive) return;
        setInvoices({ items: r.data?.items || [], total: r.data?.total || 0 });
      })
      .catch((e) => toast.error(errorMessageFromAxios(e, "Failed to load AP invoices")));
    return () => {
      alive = false;
    };
  }, [params, status]);

  useEffect(() => {
    let alive = true;
    http
      .get("/ap/payment-calendar", { params: { ...params, limit: 50 } })
      .then((r) => {
        if (!alive) return;
        setCalendar({ items: r.data?.items || [], count: r.data?.count || 0 });
      })
      .catch((e) => toast.error(errorMessageFromAxios(e, "Failed to load payment calendar")));
    return () => {
      alive = false;
    };
  }, [params]);

  useEffect(() => {
    let alive = true;
    http
      .get("/ap/payment-prioritization", { params: { ...params, limit: 30 } })
      .then((r) => {
        if (!alive) return;
        setPrio({ items: r.data?.items || [], count: r.data?.count || 0, note: r.data?.note || "" });
      })
      .catch((e) => toast.error(errorMessageFromAxios(e, "Failed to load payment prioritization")));
    return () => {
      alive = false;
    };
  }, [params]);

  const submitHold = async () => {
    const invoice_id = safeStr(holdInvoiceId).trim();
    if (!invoice_id) {
      toast.error("Invoice id is required to place a hold");
      return;
    }
    try {
      await http.post("/ap/payment-hold", {
        invoice_id,
        reason: safeStr(holdReason).trim() || "Manual hold from AP module",
        entity: params.entity_code || undefined,
      });
      toast.success("Payment hold created");
      setHoldInvoiceId("");
      setHoldReason("");
    } catch (e) {
      toast.error(errorMessageFromAxios(e, "Failed to create payment hold"));
    }
  };

  if (ageingLoading) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="ap-payables-loading">
        Loading payables…
      </div>
    );
  }

  const apBuckets = (ageing || {}).ap_ageing || (ageing || {}).ap_aging || [];
  const top = (ageing || {}).top_overdue_ap || [];
  const totalOpen = (ageing || {}).ap_open_total ?? 0;

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="ap-payables-page">
        <PageHeader
          kicker="PAYABLES · PHASE 10"
          title="AP ageing, payment calendar & holds"
          subtitle="Dedicated AP module surface backed by /working-capital/ap-ageing + /ap/* endpoints."
        />

        <MastersFilterStrip className="mb-6" />

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
          <StatCard label="AP open total" value={fmtUSD(totalOpen)} testId="ap-open-total" />
          <StatCard label="Overdue invoices (top list)" value={top.length} severity="warning" testId="ap-top-overdue-count" />
          <StatCard label="Buckets" value={apBuckets.length} testId="ap-buckets-count" />
          <StatCard label="Vendors" value={vendors.total} testId="ap-vendors-count" />
          <StatCard label="Invoices loaded" value={invoices.items.length} testId="ap-invoices-loaded" />
          <StatCard label="Entity scope" value={params.entity_code || "All"} testId="ap-entity-scope" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <SectionCard kicker="AGEING" title="AP ageing buckets">
            <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[45vh]" testId="ap-ageing-table">
              <DataTableHead>
                <tr>
                  <DataTableTh>Bucket</DataTableTh>
                  <DataTableTh align="right">Count</DataTableTh>
                  <DataTableTh align="right">Amount</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {apBuckets.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                      No ageing buckets in scope.
                    </td>
                  </tr>
                ) : null}
                {apBuckets.map((b, i) => (
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

          <SectionCard kicker="PAYMENT RUN" title="Top overdue invoices">
            <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[45vh]" testId="ap-top-overdue-table">
              <DataTableHead>
                <tr>
                  <DataTableTh>Vendor</DataTableTh>
                  <DataTableTh>Invoice</DataTableTh>
                  <DataTableTh>Due</DataTableTh>
                  <DataTableTh align="right">Amount</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {top.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                      No overdue AP in scope.
                    </td>
                  </tr>
                ) : null}
                {top.map((r) => (
                  <DataTableRow key={r.id || `${r.vendor_id}-${r.invoice_number}`}>
                    <DataTableTd className="text-sm text-foreground">{r.vendor_name || r.vendor_id || "—"}</DataTableTd>
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
          <SectionCard kicker="VENDORS" title="Vendor register (scoped)">
            <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div className="crt-num text-[10px] uppercase tracking-wider text-muted-foreground">Search by name/code/id.</div>
              <input
                value={q}
                onChange={(e) => setQ(safeStr(e.target.value))}
                placeholder="Search vendors…"
                className="w-full sm:w-[280px] rounded-sm border border-zinc-200 bg-white px-3 py-2 text-sm text-foreground outline-none dark:border-zinc-800 dark:bg-zinc-950"
                data-testid="ap-vendor-search"
              />
            </div>
            <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[45vh]" testId="ap-vendors-table">
              <DataTableHead>
                <tr>
                  <DataTableTh>Vendor</DataTableTh>
                  <DataTableTh>Code</DataTableTh>
                  <DataTableTh>Entity</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {vendors.items.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                      No vendors match the current filter.
                    </td>
                  </tr>
                ) : null}
                {vendors.items.map((v) => (
                  <DataTableRow key={v.id}>
                    <DataTableTd className="text-sm text-foreground">{v.vendor_name || v.name || "—"}</DataTableTd>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">{v.vendor_code || v.code || v.id}</DataTableTd>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">{v.entity || "—"}</DataTableTd>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </DataTable>
          </SectionCard>

          <SectionCard kicker="INVOICES" title="Invoice register + payment holds">
            <div className="mb-3 grid grid-cols-1 gap-2 sm:grid-cols-3 sm:items-end">
              <div className="sm:col-span-1">
                <div className="crt-num mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">Status</div>
                <select
                  value={status}
                  onChange={(e) => setStatus(safeStr(e.target.value))}
                  className="w-full rounded-sm border border-zinc-200 bg-white px-3 py-2 text-sm text-foreground outline-none dark:border-zinc-800 dark:bg-zinc-950"
                  data-testid="ap-invoice-status"
                >
                  <option value="">All</option>
                  <option value="open">Open</option>
                  <option value="overdue">Overdue</option>
                  <option value="paid">Paid</option>
                </select>
              </div>
              <div className="sm:col-span-1">
                <div className="crt-num mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">Hold invoice id</div>
                <input
                  value={holdInvoiceId}
                  onChange={(e) => setHoldInvoiceId(safeStr(e.target.value))}
                  placeholder="INV-…"
                  className="w-full rounded-sm border border-zinc-200 bg-white px-3 py-2 text-sm text-foreground outline-none dark:border-zinc-800 dark:bg-zinc-950"
                  data-testid="ap-hold-invoice-id"
                />
              </div>
              <div className="sm:col-span-1">
                <button
                  type="button"
                  onClick={submitHold}
                  className="crt-num w-full rounded-sm border border-zinc-200 bg-zinc-50 px-3 py-2 text-[10px] uppercase tracking-wider text-foreground hover:bg-zinc-100 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:bg-zinc-800"
                  data-testid="ap-submit-hold"
                >
                  Place hold
                </button>
              </div>
              <div className="sm:col-span-3">
                <div className="crt-num mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">Reason (optional)</div>
                <input
                  value={holdReason}
                  onChange={(e) => setHoldReason(safeStr(e.target.value))}
                  placeholder="Reason for hold…"
                  className="w-full rounded-sm border border-zinc-200 bg-white px-3 py-2 text-sm text-foreground outline-none dark:border-zinc-800 dark:bg-zinc-950"
                  data-testid="ap-hold-reason"
                />
              </div>
            </div>

            <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[34vh]" testId="ap-invoices-table">
              <DataTableHead>
                <tr>
                  <DataTableTh>Invoice</DataTableTh>
                  <DataTableTh>Vendor</DataTableTh>
                  <DataTableTh>Due</DataTableTh>
                  <DataTableTh align="right">Amount</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {invoices.items.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                      No invoices match the current filter.
                    </td>
                  </tr>
                ) : null}
                {invoices.items.map((r) => (
                  <DataTableRow key={r.id}>
                    <DataTableTd className="text-sm text-foreground">{r.invoice_number || r.id}</DataTableTd>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">{r.vendor_name || r.vendor_id || "—"}</DataTableTd>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">{fmtDate(r.due_date || r.due_ts)}</DataTableTd>
                    <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                      {fmtUSD(r.amount)}
                    </DataTableTd>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </DataTable>

            <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-2">
              <div className="rounded-sm border border-zinc-200 bg-zinc-50/80 p-3 text-sm dark:border-zinc-800 dark:bg-zinc-900/40">
                <div className="crt-num text-[10px] uppercase tracking-wider text-muted-foreground">Payment calendar</div>
                <div className="mt-2 space-y-2">
                  {calendar.items.length === 0 ? (
                    <div className="crt-num text-xs text-muted-foreground">No upcoming payments in scope.</div>
                  ) : null}
                  {calendar.items.slice(0, 6).map((x) => (
                    <div key={x.id} className="flex items-center justify-between gap-2">
                      <div className="min-w-0 truncate">{x.vendor_name || x.vendor_id || "Vendor"} · {x.invoice_number || x.id}</div>
                      <div className="crt-num tabular-nums text-foreground">{fmtUSD(x.amount)}</div>
                    </div>
                  ))}
                </div>
              </div>
              <div className="rounded-sm border border-zinc-200 bg-zinc-50/80 p-3 text-sm dark:border-zinc-800 dark:bg-zinc-900/40">
                <div className="crt-num text-[10px] uppercase tracking-wider text-muted-foreground">Payment prioritization</div>
                {prio.note ? <div className="crt-num mt-1 text-[10px] text-muted-foreground">{prio.note}</div> : null}
                <div className="mt-2 space-y-2">
                  {prio.items.length === 0 ? (
                    <div className="crt-num text-xs text-muted-foreground">No prioritized payments in scope.</div>
                  ) : null}
                  {prio.items.slice(0, 6).map((x) => (
                    <div key={x.id} className="flex items-center justify-between gap-2">
                      <div className="min-w-0 truncate">{x.vendor_name || x.vendor_id || "Vendor"} · {x.invoice_number || x.id}</div>
                      <div className="crt-num tabular-nums text-foreground">{fmtUSD(x.amount)}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </SectionCard>
        </div>
      </div>
    </PageShell>
  );
}

