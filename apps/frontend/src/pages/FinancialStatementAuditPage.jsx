import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "@phosphor-icons/react";
import { PageShell } from "../components/PageShell";
import FinancialStatementAuditPanel from "../components/ca/FinancialStatementAuditPanel";

export default function FinancialStatementAuditPage() {
  const { engagementId } = useParams();
  const eid = decodeURIComponent(engagementId || "");

  return (
    <PageShell maxWidth="max-w-[1800px]">
      <Link
        to={`/app/audit-planning/engagements/${encodeURIComponent(eid)}?tab=financial`}
        className="inline-flex items-center gap-2 text-xs font-mono uppercase text-[#737373] hover:text-white mb-4"
      >
        <ArrowLeft size={14} /> Engagement hub (FS tab)
      </Link>
      <FinancialStatementAuditPanel engagementId={eid} compact={false} />
    </PageShell>
  );
}
