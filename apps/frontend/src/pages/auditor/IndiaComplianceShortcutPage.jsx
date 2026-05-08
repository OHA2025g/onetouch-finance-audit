import { useCallback } from "react";
import EngagementShortcutPage from "./EngagementShortcutPage";

export default function IndiaComplianceShortcutPage() {
  const buildPath = useCallback(
    (eid) => `/app/audit-planning/engagements/${encodeURIComponent(eid)}/india-compliance`,
    []
  );

  return (
    <EngagementShortcutPage
      kicker="AUDITOR · COMPLIANCE"
      title="Indian Compliance"
      subtitle="Companies Act / GST / TDS / CARO / 44AB-style checks and calendar per engagement."
      buildPath={buildPath}
      primaryCta="Open compliance"
    />
  );
}

