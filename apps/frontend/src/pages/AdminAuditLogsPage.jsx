import React, { useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import AdminConsole from "./AdminConsole";

export default function AdminAuditLogsPage() {
  const [sp, setSp] = useSearchParams();

  useEffect(() => {
    // Force AdminConsole to open the logs tab, without breaking existing behavior.
    if (sp.get("tab") === "logs") return;
    setSp(
      (prev) => {
        const n = new URLSearchParams(prev);
        n.set("tab", "logs");
        return n;
      },
      { replace: true },
    );
  }, [sp, setSp]);

  return <AdminConsole />;
}

