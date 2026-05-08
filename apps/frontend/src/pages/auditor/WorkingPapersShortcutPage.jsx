import { useCallback } from "react";
import EngagementShortcutPage from "./EngagementShortcutPage";

export default function WorkingPapersShortcutPage() {
  const buildPath = useCallback(
    (eid) => `/app/audit-planning/engagements/${encodeURIComponent(eid)}/working-papers`,
    []
  );

  return (
    <EngagementShortcutPage
      kicker="AUDITOR · WORKING PAPERS"
      title="Working Papers"
      subtitle="Folders, working papers, sampling, vouching, review notes and sign-offs per engagement."
      buildPath={buildPath}
      primaryCta="Open working papers"
    />
  );
}

