import { useCallback } from "react";
import EngagementShortcutPage from "./EngagementShortcutPage";

export default function ScheduleShortcutPage() {
  const buildPath = useCallback(
    (eid) => `/app/audit-planning/engagements/${encodeURIComponent(eid)}/schedules-audit`,
    []
  );

  return (
    <EngagementShortcutPage
      kicker="AUDITOR · SCHEDULES"
      title="Schedule"
      subtitle="Schedule audit (assets, revenue, expenses, inventory, liabilities) with exceptions and conclusions."
      buildPath={buildPath}
      primaryCta="Open schedules"
    />
  );
}

