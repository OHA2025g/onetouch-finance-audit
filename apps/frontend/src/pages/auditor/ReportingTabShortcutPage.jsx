import { useCallback } from "react";
import EngagementShortcutPage from "./EngagementShortcutPage";

export default function ReportingTabShortcutPage() {
  const buildPath = useCallback(
    (eid) => `/app/audit-planning/engagements/${encodeURIComponent(eid)}?tab=reporting`,
    []
  );

  return (
    <EngagementShortcutPage
      kicker="AUDITOR · REPORTING"
      title="Reporting Tab"
      subtitle="Open the engagement hub on the reporting tab (status, generators, and reporting actions)."
      buildPath={buildPath}
      primaryCta="Open reporting tab"
    />
  );
}

