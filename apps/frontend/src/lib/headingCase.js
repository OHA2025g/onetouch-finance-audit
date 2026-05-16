/**
 * Title-case style labels for headers / kickers / overlines (removes all-caps chrome).
 * Preserves common audit & finance acronyms and codes like 44AB, 3CD.
 */

const SPECIAL = {
  "fp&a": "FP&A",
  "p&l": "P&L",
  "r&d": "R&D",
};

const ACRONYMS = new Set([
  "AI",
  "AML",
  "AP",
  "API",
  "AR",
  "BFF",
  "CA",
  "CAPEX",
  "CAR",
  "CEO",
  "CFO",
  "COO",
  "CRM",
  "CTO",
  "DQ",
  "DCF",
  "EIN",
  "ERP",
  "ESG",
  "FS",
  "FP",
  "FY",
  "GAAP",
  "GL",
  "GST",
  "GSTN",
  "HR",
  "HQ",
  "IA",
  "ICFR",
  "IFC",
  "IFRS",
  "IT",
  "JSON",
  "KAM",
  "KPI",
  "KYC",
  "LLM",
  "LLP",
  "MVP",
  "NLP",
  "O2C",
  "P2P",
  "PAN",
  "PR",
  "QA",
  "R2R",
  "RBAC",
  "ROC",
  "ROU",
  "RPT",
  "SAP",
  "SD",
  "SEBI",
  "SLA",
  "SOC",
  "SOD",
  "SQL",
  "TDS",
  "TIN",
  "UAT",
  "UK",
  "US",
  "UI",
  "URL",
  "VAT",
  "VPN",
  "WC",
  "WP",
  "XML",
  "XBRL",
  "IDS",
  "IDC",
  "KMS",
  "MOCK",
]);

function titleCaseCore(core) {
  if (!core) return core;
  const lower = core.toLowerCase();
  if (SPECIAL[lower]) return SPECIAL[lower];
  if (/^\d+$/.test(core)) return core;
  if (/^[0-9]+[A-Za-z][A-Za-z0-9]*$/i.test(core) || /^[A-Za-z]*\d{2,}[A-Za-z0-9]*$/i.test(core)) return core;
  const upper = core.toUpperCase();
  if (ACRONYMS.has(upper)) return upper;
  const phase = core.match(/^phase\s*(\d+)$/i);
  if (phase) return `Phase ${phase[1]}`;
  return core.charAt(0).toUpperCase() + core.slice(1).toLowerCase();
}

function titleCaseWord(word) {
  if (word == null || word === "") return "";
  const w = typeof word === "string" ? word : String(word);
  if (!w) return "";
  if (w.includes("-")) {
    return w.split("-").map((part) => titleCaseWord(part)).join("-");
  }
  const m = w.match(/^([^A-Za-z0-9]*)([A-Za-z0-9&]+)([^A-Za-z0-9]*)$/);
  if (!m) return w;
  const [, pre, core, post] = m;
  return `${pre}${titleCaseCore(core)}${post}`;
}

/**
 * @param {string | null | undefined} raw
 * @returns {string}
 */
export function toProperHeadingLabel(raw) {
  if (raw == null) return "";
  const base = typeof raw === "string" ? raw : String(raw);
  const trimmed = base.trim();
  if (!trimmed) return base;
  return trimmed
    .split(/(\s*[·•]\s*)/)
    .map((chunk) => {
      if (/^\s*[·•]\s*$/.test(chunk)) return chunk.trim() === "·" ? " · " : chunk;
      return chunk
        .split(/\s+/)
        .map((w, i) => (i === 0 ? titleCaseWord(w) : titleCaseWord(w)))
        .join(" ");
    })
    .join("");
}
