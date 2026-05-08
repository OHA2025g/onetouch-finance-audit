/** Query keys for Phase 3 URL–synced finance master filter context (namespaced to avoid clashes). */
export const MF_ENTITY = "m_entity";
export const MF_PERIOD = "m_period";
export const MF_DEPT = "m_dept";
export const MF_CC = "m_cc";

export const MF_KEYS = [MF_ENTITY, MF_PERIOD, MF_DEPT, MF_CC];

export function defaultMasterPeriodYm() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}
