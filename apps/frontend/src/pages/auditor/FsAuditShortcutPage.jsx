import { useCallback } from "react";
import EngagementShortcutPage from "./EngagementShortcutPage";

export default function FsAuditShortcutPage() {
  const buildPath = useCallback(
    (eid) => `/app/audit-planning/engagements/${encodeURIComponent(eid)}/fs-audit`,
    []
  );

  return (
    <EngagementShortcutPage
      kicker="AUDITOR · FINANCIAL"
      title="FS Audit"
      subtitle="Run financial statement audit procedures and review validations per engagement."
      buildPath={buildPath}
      primaryCta="Open FS audit"
    />
  );
}

