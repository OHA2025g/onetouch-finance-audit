export const fmtUSD = (n) => {
  if (n == null || isNaN(n)) return "—";
  const abs = Math.abs(n);
  if (abs >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000) return `$${(n / 1_000).toFixed(1)}K`;
  return `$${n.toFixed(0)}`;
};

export const fmtNum = (n) => {
  if (n == null || isNaN(n)) return "—";
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(n);
};

export const fmtPct = (n) => n == null ? "—" : `${Number(n).toFixed(1)}%`;

export const fmtDate = (iso) => {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
  } catch { return iso; }
};

export const fmtDateTime = (iso) => {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
  } catch { return iso; }
};

export const daysFromNow = (iso) => {
  if (!iso) return null;
  try {
    const ms = new Date(iso).getTime() - Date.now();
    return Math.round(ms / (1000 * 60 * 60 * 24));
  } catch { return null; }
};

export const severityRank = { critical: 4, high: 3, medium: 2, low: 1 };
