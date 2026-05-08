import { useCallback } from "react";
import EngagementShortcutPage from "./EngagementShortcutPage";

export default function ReportingStudioShortcutPage() {
  const buildPath = useCallback(
    (eid) => `/app/audit-planning/engagements/${encodeURIComponent(eid)}/report-studio`,
    []
  );

  return (
    <EngagementShortcutPage
      kicker="AUDITOR · REPORTING"
      title="Reporting Studio"
      subtitle="Build observations, draft opinion, CARO annexure, and preview final report per engagement."
      buildPath={buildPath}
      primaryCta="Open report studio"
    />
  );
}

