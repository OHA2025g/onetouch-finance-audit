import { useCallback } from "react";
import EngagementShortcutPage from "./EngagementShortcutPage";

export default function FsHubPage() {
  const buildPath = useCallback(
    (eid) => `/app/audit-planning/engagements/${encodeURIComponent(eid)}?tab=financial`,
    []
  );

  return (
    <EngagementShortcutPage
      kicker="AUDITOR · FINANCIAL"
      title="FS Hub"
      subtitle="Engagement-scoped financial statement hub (trial balance, generation, adjustments, validations)."
      buildPath={buildPath}
      primaryCta="Open FS hub"
    />
  );
}

