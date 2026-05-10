import React, { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { UploadSimple, FileCsv, CheckCircle } from "@phosphor-icons/react";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";

const SAMPLE = {
  vendors: `id,vendor_code,vendor_name,entity,bank_account_hash,status,bank_changed_at
V-CSV-001,V-CSV-001,Coastline Supply Ltd,US-HQ,HASHCSV1,active,2024-09-01T00:00:00Z
V-CSV-002,V-CSV-002,Aurora Components Pvt,IN-SVC,HASHCSV2,active,2025-12-01T00:00:00Z`,
  invoices: `invoice_number,vendor_id,vendor_name,entity,invoice_date,amount,tax_amount,status
INV-CSV-001,V-1000,Apex Logistics Ltd,US-HQ,2026-02-10T00:00:00Z,45000,8100,posted
INV-CSV-002,V-1001,Harbor Systems Ltd,UK-OPS,2026-02-11T00:00:00Z,12000,2160,paid`,
};

export default function Upload() {
  const [dataset, setDataset] = useState("invoices");
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [uploading, setUploading] = useState(false);
  const inputRef = useRef(null);

  const submit = async (e) => {
    e.preventDefault();
    if (!file) { toast.error("Pick a CSV file"); return; }
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("dataset", dataset);
      const { data } = await http.post("/ingest/csv", form);
      setResult(data);
      toast.success(`Ingested ${data.rows_ingested} rows`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Ingest failed");
    }
    setUploading(false);
  };

  const downloadSample = () => {
    const blob = new Blob([SAMPLE[dataset]], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `sample-${dataset}.csv`;
    a.click();
  };

  return (
    <PageShell maxWidth="max-w-[1100px]">
      <div data-testid="upload-page">
        <PageHeader
          kicker="DATA INGESTION"
          title="CSV upload"
          subtitle="Bring your own vendor & invoice data. Controls will re-run automatically and ingestion is audit-logged."
        />
        <p className="text-xs font-mono text-[#737373] mb-4">
          After upload, review runs and actor trails in{" "}
          <Link to="/app/admin" className="text-[#0A84FF] hover:underline">Admin &amp; Governance</Link>
          {" "}(Ingestion tab) and drill users from audit logs.
        </p>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <SectionCard className="lg:col-span-2" kicker="UPLOAD" title="Ingest dataset">
            <form onSubmit={submit} className="space-y-5" data-testid="upload-form">
              <div>
                <label className="font-mono text-[10px] uppercase tracking-[0.15em] text-[#737373] block mb-2">Dataset</label>
                <select
                  data-testid="dataset-select"
                  value={dataset}
                  onChange={e => setDataset(e.target.value)}
                  className="w-full bg-[#141414]/70 backdrop-blur border border-[#262626] px-3 h-11 text-sm text-white outline-none focus:border-white rounded-xl"
                >
                  <option value="invoices">Invoices</option>
                  <option value="vendors">Vendors</option>
                </select>
              </div>

              <div>
                <label className="font-mono text-[10px] uppercase tracking-[0.15em] text-[#737373] block mb-2">CSV file</label>
                <div
                  onClick={() => inputRef.current?.click()}
                  className="border border-dashed border-[#404040] bg-[#0A0A0A]/55 backdrop-blur p-10 text-center cursor-pointer hover:bg-[#1F1F1F]/55 transition-colors rounded-2xl"
                  data-testid="drop-zone"
                >
                  <FileCsv size={32} weight="light" className="mx-auto text-[#737373] mb-2" />
                  {file ? (
                    <>
                      <div className="text-sm text-white">{file.name}</div>
                      <div className="font-mono text-[10px] text-[#737373] mt-1">{(file.size / 1024).toFixed(1)} KB · click to change</div>
                    </>
                  ) : (
                    <>
                      <div className="text-sm text-white">Click to select a CSV</div>
                      <div className="font-mono text-[10px] text-[#737373] mt-1">Headers must match required schema</div>
                    </>
                  )}
                  <input
                    ref={inputRef}
                    type="file"
                    accept=".csv,text/csv"
                    data-testid="file-input"
                    onChange={e => setFile(e.target.files?.[0] || null)}
                    className="hidden"
                  />
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                <button
                  data-testid="upload-submit-btn"
                  type="submit"
                  disabled={uploading || !file}
                  className="flex items-center gap-2 px-6 h-11 bg-white text-black font-mono text-xs uppercase tracking-wider hover:bg-[#E5E5E5] transition-colors disabled:opacity-40 rounded-full shadow-[0_18px_55px_rgba(255,255,255,0.10)]"
                >
                  <UploadSimple size={14} /> {uploading ? "Uploading..." : "Ingest"}
                </button>
                <button
                  type="button"
                  data-testid="download-sample-btn"
                  onClick={downloadSample}
                  className="px-6 h-11 bg-[#141414]/70 backdrop-blur border border-[#404040] text-xs font-mono uppercase tracking-wider text-white hover:bg-[#1F1F1F]/70 transition-colors rounded-full"
                >
                  Download sample CSV
                </button>
              </div>
          </form>

          {result && (
            <div className="mt-6 border border-[#30D158]/40 bg-[#30D158]/5 p-4 rounded-2xl" data-testid="ingest-result">
              <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-wider text-[#30D158] mb-2">
                <CheckCircle size={14} weight="fill" /> Ingest complete
              </div>
              <div className="font-mono text-xs text-[#A3A3A3] space-y-1">
                <div>Dataset: <span className="text-white">{result.dataset}</span></div>
                <div>Rows ingested: <span className="text-white">{result.rows_ingested}</span></div>
                <div>Rows failed: <span className="text-white">{result.rows_failed}</span></div>
                <div>Lineage ID: <span className="text-white">{result.lineage_id}</span></div>
              </div>
            </div>
          )}
          </SectionCard>

          <SectionCard className="lg:col-span-1" kicker="SCHEMA" title="Required columns">
            <div className="font-mono text-xs text-[#E5E5E5] leading-relaxed">
            {dataset === "invoices" ? (
              <ul className="space-y-1">
                <li><span className="text-[#30D158]">*</span> invoice_number</li>
                <li><span className="text-[#30D158]">*</span> amount</li>
                <li>vendor_id, vendor_name, entity</li>
                <li>invoice_date, tax_amount</li>
                <li>status, approver_email, po_id</li>
              </ul>
            ) : (
              <ul className="space-y-1">
                <li><span className="text-[#30D158]">*</span> vendor_name</li>
                <li>id, vendor_code, entity, status</li>
                <li>bank_account_hash, bank_changed_at</li>
              </ul>
            )}
          </div>
          <div className="mt-4 font-mono text-[10px] uppercase tracking-wider text-[#737373]">
            All uploads are audit-logged · lineage tracked
          </div>
          </SectionCard>
      </div>
      </div>
    </PageShell>
  );
}
