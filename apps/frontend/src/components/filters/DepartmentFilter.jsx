import React, { useEffect, useState } from "react";
import { http } from "../../lib/api";

const selectClass =
  "crt-num h-9 min-w-[180px] rounded-sm border border-zinc-300 bg-white px-3 text-xs uppercase tracking-wider text-foreground outline-none focus:border-primary focus:ring-1 focus:ring-primary dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100";

export default function DepartmentFilter({
  entityCode,
  value,
  onChange,
  id = "filter-department",
  label = "Department",
  className = "",
}) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const params = entityCode ? { entity_code: entityCode } : {};
        const { data } = await http.get("/masters/departments", { params });
        if (!cancelled) setItems(Array.isArray(data?.items) ? data.items : []);
      } catch {
        if (!cancelled) setItems([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [entityCode]);

  return (
    <label className={`flex flex-col gap-1 ${className}`}>
      <span className="crt-overline text-muted-foreground">{label}</span>
      <select
        id={id}
        className={selectClass}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={loading}
        data-testid="master-filter-department"
      >
        <option value="">{loading ? "Loading…" : "All departments"}</option>
        {items.map((d) => (
          <option key={d.id} value={d.id}>
            {d.name} ({d.code})
          </option>
        ))}
      </select>
    </label>
  );
}
