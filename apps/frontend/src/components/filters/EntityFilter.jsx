import React, { useEffect, useState } from "react";
import { http } from "../../lib/api";

const selectBase =
  "crt-num h-9 rounded-sm border border-zinc-300 bg-white px-3 text-xs uppercase tracking-wider text-foreground outline-none focus:border-primary focus:ring-1 focus:ring-primary dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100";

const selectWidth = {
  default: "min-w-[160px]",
  strip: "min-w-0 w-full max-w-full",
};

/**
 * Legal entities from GET /api/masters/entities (Phase 2 unified model).
 */
export default function EntityFilter({
  value,
  onChange,
  id = "filter-entity",
  label = "Entity",
  className = "",
  variant = "default",
}) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const { data } = await http.get("/masters/entities");
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
  }, []);

  const selectClass = `${selectBase} ${selectWidth[variant] || selectWidth.default}`;

  return (
    <label className={`flex min-w-0 flex-col gap-1 ${className}`}>
      <span className="crt-overline text-muted-foreground">{label}</span>
      <select
        id={id}
        className={selectClass}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={loading}
        data-testid="master-filter-entity"
      >
        <option value="">{loading ? "Loading…" : "All entities"}</option>
        {items.map((e) => (
          <option key={e.code || e.id} value={e.code || ""}>
            {e.name} ({e.code})
          </option>
        ))}
      </select>
    </label>
  );
}
