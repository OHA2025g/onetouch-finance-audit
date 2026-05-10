import React, { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { http, API } from "../../lib/api";
import { toast } from "sonner";
import { useDashboardFilterParams } from "../../lib/useDashboardFilterParams";
import { SectionCard } from "../../components/PageShell";

const STATUSES = ["draft", "partner review", "management response", "final issued"];

export default function FinalReportPreviewPage() {
  const { engagementId } = useParams();
  const dashboardParams = useDashboardFilterParams();
  const eid = decodeURIComponent(engagementId || "");
  const [report, setReport] = useState(null);

  const load = useCallback(async () => {
    const { data } = await http.get(`/audit-engagements/${encodeURIComponent(eid)}/report`, { params: dashboardParams });
    setReport(data);
  }, [eid, dashboardParams]);

  useEffect(() => {
    load().catch(() => setReport(null));
  }, [load]);

  const gen = async () => {
    try {
      const { data } = await http.post(`/audit-engagements/${encodeURIComponent(eid)}/report/generate`, {}, { params: dashboardParams });
      setReport(data);
      toast.success("Report draft generated");
    } catch {
      toast.error("Generate failed");
    }
  };

  const setStatus = async (status) => {
    try {
      const { data } = await http.patch(`/audit-engagements/${encodeURIComponent(eid)}/report/status`, { status }, { params: dashboardParams });
      setReport(data);
      toast.success("Status updated");
    } catch {
      toast.error("Status update failed");
    }
  };

  const exportBlob = (format, filename) => {
    const token = localStorage.getItem("ota_token");
    const q = new URLSearchParams({ ...dashboardParams, format });
    const url = `${API}/audit-engagements/${encodeURIComponent(eid)}/report/export?${q}`;
    fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then((r) => {
        if (!r.ok) throw new Error();
        return r.blob();
      })
      .then((blob) => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = filename;
        a.click();
        URL.revokeObjectURL(a.href);
      })
      .catch(() => toast.error("Export failed"));
  };

  const sections = report?.sections || {};

  return (
    <div className="space-y-6">
      <SectionCard kicker="WORKFLOW" title="Approval status" bodyClassName="p-4 flex flex-wrap gap-2 items-center">
        <span className="text-xs font-mono text-[#737373] uppercase">Current: {report?.approval_status || report?.status || "—"}</span>
        {STATUSES.map((s) => (
          <button key={s} type="button" onClick={() => setStatus(s)} className="px-3 h-8 border border-[#262626] text-[10px] font-mono uppercase text-[#A3A3A3] hover:text-white">
            {s}
          </button>
        ))}
      </SectionCard>
      <SectionCard kicker="EXPORT" title="Downloads" bodyClassName="p-4 flex flex-wrap gap-2">
        <button type="button" onClick={() => exportBlob("pdf", `audit-report-${eid}.pdf`)} className="px-4 h-9 bg-white text-black font-mono text-xs uppercase">
          PDF
        </button>
        <button type="button" onClick={() => exportBlob("docx", `audit-report-${eid}.docx`)} className="px-4 h-9 border border-white text-white font-mono text-xs uppercase">
          DOCX
        </button>
        <button type="button" onClick={() => exportBlob("xlsx", `audit-report-${eid}.xlsx`)} className="px-4 h-9 border border-[#262626] text-[#A3A3A3] font-mono text-xs uppercase hover:text-white">
          Excel (sections)
        </button>
        <button
          type="button"
          onClick={() => exportBlob("observations-xlsx", `observations-${eid}.xlsx`)}
          className="px-4 h-9 border border-[#262626] text-[#A3A3A3] font-mono text-xs uppercase hover:text-white"
        >
          Excel (observations)
        </button>
      </SectionCard>
      <SectionCard kicker="DRAFT" title="Final report preview" bodyClassName="p-4 space-y-4">
        <button type="button" onClick={gen} className="px-4 h-10 bg-white text-black font-mono text-xs uppercase">
          Generate / refresh draft
        </button>
        {!report ? (
          <p className="text-sm text-[#737373]">No report yet — generate a draft.</p>
        ) : (
          <div className="space-y-6 text-sm max-h-[70vh] overflow-y-auto pr-2">
            {Object.entries(sections).map(([k, v]) => (
              <div key={k}>
                <h4 className="font-mono text-[10px] uppercase text-[#0A84FF] mb-2">{k.replace(/_/g, " ")}</h4>
                {Array.isArray(v) ? (
                  <ul className="list-disc pl-5 text-[#A3A3A3] space-y-1">
                    {v.map((item, i) => (
                      <li key={i} className="text-white">
                        {typeof item === "object" ? JSON.stringify(item) : String(item)}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="text-[#E5E5E5] whitespace-pre-wrap">{typeof v === "object" ? JSON.stringify(v, null, 2) : String(v)}</div>
                )}
              </div>
            ))}
          </div>
        )}
      </SectionCard>
    </div>
  );
}
