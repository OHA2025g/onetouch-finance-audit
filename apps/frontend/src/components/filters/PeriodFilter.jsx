import React from "react";

const selectBase =
  "crt-num h-9 rounded-sm border border-zinc-300 bg-white px-3 text-xs uppercase tracking-wider text-foreground outline-none focus:border-primary focus:ring-1 focus:ring-primary dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100";

const selectWidth = {
  default: "min-w-[140px]",
  strip: "min-w-0 w-full max-w-full",
};

/** Reporting period as YYYY-MM (shared filter primitive). */
export default function PeriodFilter({
  value,
  onChange,
  id = "filter-period",
  label = "Period",
  className = "",
  variant = "default",
}) {
  const options = React.useMemo(() => {
    const out = [];
    const d = new Date();
    for (let i = 0; i < 18; i += 1) {
      const dt = new Date(d.getFullYear(), d.getMonth() - i, 1);
      const ym = `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}`;
      out.push(ym);
    }
    return out;
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
        data-testid="master-filter-period"
      >
        {options.map((ym) => (
          <option key={ym} value={ym}>
            {ym}
          </option>
        ))}
      </select>
    </label>
  );
}
