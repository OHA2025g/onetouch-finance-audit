import React from "react";
import clsx from "clsx";
import { CheckCircle, Clock, Warning } from "@phosphor-icons/react";

export default function MilestoneTimeline({ milestones }) {
  const items = milestones || [];
  if (!items.length) {
    return <div className="font-mono text-xs text-[#737373]">No milestones yet.</div>;
  }
  return (
    <ol className="space-y-3" data-testid="milestone-timeline">
      {items.map((m) => (
        <li key={m.id} className="flex gap-3 items-start">
          <div className="mt-0.5 text-[#737373]">
            {m.status === "done" ? <CheckCircle size={18} weight="fill" className="text-[#30D158]" /> : m.status === "late" ? <Warning size={18} weight="fill" className="text-[#F97316]" /> : <Clock size={18} />}
          </div>
          <div className="flex-1 min-w-0 border border-[#262626] rounded-xl px-3 py-2 bg-[#0A0A0A]/50">
            <div className="text-sm text-white font-medium">{m.title}</div>
            <div className="font-mono text-[10px] text-[#737373] mt-0.5">
              Due {m.due_date?.slice(0, 10) || "—"}
              {m.owner_email ? ` · ${m.owner_email}` : ""}
            </div>
            <span className={clsx("font-mono text-[9px] uppercase mt-1 inline-block", m.status === "done" ? "text-[#30D158]" : "text-[#A3A3A3]")}>{m.status}</span>
          </div>
        </li>
      ))}
    </ol>
  );
}
