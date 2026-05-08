import { useCallback } from "react";
import EngagementShortcutPage from "./EngagementShortcutPage";

export default function IfcShortcutPage() {
  const buildPath = useCallback(
    (eid) => `/app/audit-planning/engagements/${encodeURIComponent(eid)}/ifc-engine`,
    []
  );

  return (
    <EngagementShortcutPage
      kicker="AUDITOR · IFC"
      title="IFC"
      subtitle="Internal financial controls evaluation: testing, deficiencies, and sign-offs per engagement."
      buildPath={buildPath}
      primaryCta="Open IFC"
    />
  );
}

