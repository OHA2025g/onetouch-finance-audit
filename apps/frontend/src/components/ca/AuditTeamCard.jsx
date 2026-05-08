import React from "react";
import { User } from "@phosphor-icons/react";

export default function AuditTeamCard({ members }) {
  const list = members || [];
  if (!list.length) {
    return <div className="font-mono text-xs text-[#737373]">No team members assigned.</div>;
  }
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3" data-testid="audit-team-card">
      {list.map((m) => (
        <div key={m.id} className="flex items-center gap-3 border border-[#262626] rounded-xl p-3 bg-[#0A0A0A]/50">
          <div className="w-9 h-9 bg-white text-black flex items-center justify-center">
            <User size={18} weight="bold" />
          </div>
          <div className="min-w-0">
            <div className="text-sm text-white truncate">{m.user_email}</div>
            <div className="font-mono text-[10px] text-[#737373] uppercase tracking-wider">{m.role} · {m.allocation_pct ?? 100}%</div>
          </div>
        </div>
      ))}
    </div>
  );
}
