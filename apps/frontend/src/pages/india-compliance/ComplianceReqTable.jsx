import React, { useState } from "react";
import { http } from "../../lib/api";
import { toast } from "sonner";
import { useDashboardFilterParams } from "../../lib/useDashboardFilterParams";
import { PenaltyRiskBadge } from "../../components/Badges";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../../components/DataTable";

const STATUSES = ["compliant", "non-compliant", "pending evidence", "not applicable"];

export default function ComplianceReqTable({ engagementId, requirements, lawCodes, onChanged }) {
  const dashboardParams = useDashboardFilterParams();
  const [busy, setBusy] = useState(null);
  const rows = (requirements || []).filter((r) => {
    if (!lawCodes?.length) return true;
    return lawCodes.includes(r.law_code);
  });

  const patch = async (reqId, status, evidence_uri, notes) => {
    setBusy(reqId);
    try {
      await http.post(
        `/audit-engagements/${encodeURIComponent(engagementId)}/compliance/result`,
        {
          requirement_id: reqId,
          status,
          evidence_uri: evidence_uri || null,
          notes: notes || null,
        },
        { params: dashboardParams },
      );
      toast.success("Requirement updated");
      onChanged?.();
    } catch {
      toast.error("Update failed");
    } finally {
      setBusy(null);
    }
  };

  return (
    <DataTable className="rounded-none border-0 max-h-[65vh]">
      <DataTableHead>
        <tr>
          <DataTableTh>Section</DataTableTh>
          <DataTableTh>Title</DataTableTh>
          <DataTableTh>Penalty</DataTableTh>
          <DataTableTh>Status</DataTableTh>
          <DataTableTh>Evidence</DataTableTh>
        </tr>
      </DataTableHead>
      <DataTableBody>
        {rows.map((r) => (
          <DataTableRow key={r.id}>
            <DataTableTd className="font-mono text-[10px] text-[#0A84FF] whitespace-nowrap">{r.section}</DataTableTd>
            <DataTableTd className="text-sm text-white max-w-md">{r.title}</DataTableTd>
            <DataTableTd>
              <PenaltyRiskBadge risk={r.penalty_risk || "medium"} />
            </DataTableTd>
            <DataTableTd>
              <select
                value={r.status || "pending evidence"}
                disabled={busy === r.id}
                onChange={(ev) => patch(r.id, ev.target.value, r.evidence_uri, r.notes)}
                className="bg-black border border-[#262626] text-xs text-white px-2 py-1 font-mono max-w-[160px]"
              >
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </DataTableTd>
            <DataTableTd className="min-w-[200px]">
              <input
                defaultValue={r.evidence_uri || ""}
                placeholder="URI / path"
                className="w-full bg-black border border-[#262626] px-2 py-1 text-[11px] text-white font-mono"
                onBlur={(ev) => {
                  const v = ev.target.value.trim();
                  if (v !== (r.evidence_uri || "")) patch(r.id, r.status, v, r.notes);
                }}
              />
            </DataTableTd>
          </DataTableRow>
        ))}
      </DataTableBody>
    </DataTable>
  );
}
