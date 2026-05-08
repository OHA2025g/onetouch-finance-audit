import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import DrillContextBar from "../components/DrillContextBar";
import { http } from "../lib/api";
import { fmtUSD, fmtDate, fmtDateTime } from "../lib/format";
import { CaretLeft, Receipt, Bank, FileText, User, Buildings, Gauge,
         Users, Package, CurrencyCircleDollar, Cube, Briefcase } from "@phosphor-icons/react";

import InvoiceDrill from "./drill/InvoiceDrill";
import PaymentDrill from "./drill/PaymentDrill";
import JournalDrill from "./drill/JournalDrill";
import VendorDrill from "./drill/VendorDrill";
import UserDrill from "./drill/UserDrill";
import ControlDrill from "./drill/ControlDrill";
import CustomerDrill from "./drill/CustomerDrill";
import ARInvoiceDrill from "./drill/ARInvoiceDrill";
import SalesOrderDrill from "./drill/SalesOrderDrill";
import EmployeeDrill from "./drill/EmployeeDrill";
import PayrollEntryDrill from "./drill/PayrollEntryDrill";
import BankTransactionDrill from "./drill/BankTransactionDrill";
import FixedAssetDrill from "./drill/FixedAssetDrill";
import CapExDrill from "./drill/CapExDrill";

const ICONS = {
  invoice: Receipt, payment: Bank, journal: FileText, vendor: Buildings,
  user: User, control: Gauge,
  customer: Users, ar_invoice: Receipt, sales_order: Package,
  employee: User, payroll_entry: CurrencyCircleDollar, bank_transaction: Bank,
  fixed_asset: Cube, capex_project: Briefcase,
};

const RENDERERS = {
  invoice: InvoiceDrill, payment: PaymentDrill, journal: JournalDrill,
  vendor: VendorDrill, user: UserDrill, control: ControlDrill,
  customer: CustomerDrill, ar_invoice: ARInvoiceDrill, sales_order: SalesOrderDrill,
  employee: EmployeeDrill, payroll_entry: PayrollEntryDrill,
  bank_transaction: BankTransactionDrill, fixed_asset: FixedAssetDrill,
  capex_project: CapExDrill,
};

function headerTitle(type, p, id) {
  if (type === "invoice") return p.invoice_number;
  if (type === "payment") return p.bank_reference;
  if (type === "journal") return p.journal_number;
  if (type === "vendor") return p.vendor_name;
  if (type === "user") return p.full_name || p.email;
  if (type === "control") return `${p.code} · ${p.name}`;
  if (type === "customer") return p.customer_name;
  if (type === "ar_invoice") return p.ar_number;
  if (type === "sales_order") return p.so_number;
  if (type === "employee") return p.full_name;
  if (type === "payroll_entry") return `${p.employee_name} · ${p.period}`;
  if (type === "bank_transaction") return p.reference;
  if (type === "fixed_asset") return `${p.asset_code} · ${p.asset_name}`;
  if (type === "capex_project") return p.project_name;
  return id;
}

function headerSubtitle(type, p) {
  if (type === "invoice") return `${p.vendor_name} · ${p.entity} · ${fmtDate(p.invoice_date)}`;
  if (type === "payment") return `${p.vendor_name} · ${p.entity} · ${fmtDate(p.payment_date)}`;
  if (type === "journal") return `${p.entity} · ${p.description} · posted ${fmtDate(p.posting_date)}`;
  if (type === "vendor") return `${p.entity} · ${p.status} · vendor code ${p.vendor_code}`;
  if (type === "user") return `${p.role} · ${p.entity || "—"} · ${p.status || "—"}`;
  if (type === "control") return `${p.process} · ${p.criticality} · ${p.framework}`;
  if (type === "customer") return `${p.entity} · ${p.status} · terms net ${p.payment_terms_days}d · limit ${fmtUSD(p.credit_limit)}`;
  if (type === "ar_invoice") return `${p.customer_name} · ${p.entity} · ${fmtDate(p.invoice_date)} · due ${fmtDate(p.due_date)}`;
  if (type === "sales_order") return `${p.customer_name} · ${p.entity} · ${fmtDate(p.so_date)} · ${p.status}`;
  if (type === "employee") return `${p.email} · ${p.department} · ${p.entity} · ${p.status}`;
  if (type === "payroll_entry") return `${p.entity} · run ${p.payroll_run_id} · ${p.status}`;
  if (type === "bank_transaction") return `${p.entity} · ${fmtDateTime(p.txn_ts)} · ${p.direction} · ${p.currency}`;
  if (type === "fixed_asset") return `${p.entity} · ${p.category} · in-service ${fmtDate(p.in_service_date)} · ${p.status}`;
  if (type === "capex_project") return `${p.entity} · ${p.project_code} · ${p.status}`;
  return "";
}

const NO_AMOUNT_TYPES = new Set(["user", "control", "employee", "customer", "fixed_asset"]);

export default function DrillView() {
  const { type, id } = useParams();
  const nav = useNavigate();
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    setData(null); setErr(null);
    http.get(`/drill/${type}/${encodeURIComponent(id)}`)
      .then(r => setData(r.data))
      .catch(e => setErr(e?.response?.data?.detail || "Failed to load"));
  }, [type, id]);

  if (err) return <div className="p-8 font-mono text-xs uppercase tracking-wider text-destructive">{err}</div>;
  if (!data) return <div className="p-8 font-mono text-xs uppercase tracking-wider text-muted-foreground">Loading {type} drill-down…</div>;

  const Renderer = RENDERERS[type];
  if (!Renderer) return <div className="p-8 font-mono text-xs text-destructive">Unknown drill type: {type}</div>;

  const Icon = ICONS[type] || FileText;
  const p = data.primary;
  const showAmount = !NO_AMOUNT_TYPES.has(type);

  return (
    <div className="p-6 lg:p-8 max-w-[1800px]" data-testid={`drill-${type}`}>
      <button onClick={() => nav(-1)} className="mb-2 flex items-center gap-1 text-xs font-mono uppercase tracking-wider text-muted-foreground transition-colors hover:text-foreground" data-testid="drill-back-btn">
        <CaretLeft size={12} /> Back
      </button>
      <DrillContextBar
        crumbs={[
          { label: "App", to: "/app" },
          { label: "Drill-down", to: "/app/evidence" },
          { label: `${type} · ${String(id).slice(0, 24)}${String(id).length > 24 ? "…" : ""}` },
        ]}
      />

      <div className="mb-6 flex items-start justify-between">
        <div className="flex items-start gap-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-sm border border-zinc-200 bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-900">
            <Icon size={18} weight="light" className="text-foreground" />
          </div>
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">{type.toUpperCase()} · {id}</div>
            <h1 className="font-display mt-1 text-3xl font-semibold tracking-tight text-foreground">{headerTitle(type, p, id)}</h1>
            <div className="mt-1 font-mono text-xs text-muted-foreground">{headerSubtitle(type, p)}</div>
          </div>
        </div>
        {showAmount && (
          <div className="text-right">
            <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Amount</div>
            <div className="mt-1 font-mono text-3xl tabular-nums text-foreground">
              {fmtUSD(p.amount ?? p.total_amount ?? p.net_amount ?? p.budget_amount ?? 0)}
            </div>
          </div>
        )}
      </div>

      <Renderer data={data} nav={nav} />
    </div>
  );
}
