import React, { createContext, useCallback, useContext, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import {
  MF_CC,
  MF_DEPT,
  MF_ENTITY,
  MF_KEYS,
  MF_PERIOD,
  defaultMasterPeriodYm,
} from "./mastersFilterKeys";

const MastersFilterContext = createContext(null);

export function MastersFilterProvider({ children }) {
  const [searchParams, setSearchParams] = useSearchParams();

  const entityCode = searchParams.get(MF_ENTITY) || "";
  const periodExplicit = searchParams.has(MF_PERIOD);
  const periodYm = searchParams.get(MF_PERIOD) || defaultMasterPeriodYm();
  const departmentId = searchParams.get(MF_DEPT) || "";
  const costCenterId = searchParams.get(MF_CC) || "";

  const setEntityCode = useCallback(
    (v) => {
      setSearchParams(
        (prev) => {
          const n = new URLSearchParams(prev);
          if (v) n.set(MF_ENTITY, v);
          else n.delete(MF_ENTITY);
          n.delete(MF_DEPT);
          n.delete(MF_CC);
          return n;
        },
        { replace: true }
      );
    },
    [setSearchParams]
  );

  const setPeriodYm = useCallback(
    (v) => {
      const def = defaultMasterPeriodYm();
      setSearchParams(
        (prev) => {
          const n = new URLSearchParams(prev);
          if (!v || v === def) n.delete(MF_PERIOD);
          else n.set(MF_PERIOD, v);
          return n;
        },
        { replace: true }
      );
    },
    [setSearchParams]
  );

  const setDepartmentId = useCallback(
    (v) => {
      setSearchParams(
        (prev) => {
          const n = new URLSearchParams(prev);
          if (v) n.set(MF_DEPT, v);
          else n.delete(MF_DEPT);
          return n;
        },
        { replace: true }
      );
    },
    [setSearchParams]
  );

  const setCostCenterId = useCallback(
    (v) => {
      setSearchParams(
        (prev) => {
          const n = new URLSearchParams(prev);
          if (v) n.set(MF_CC, v);
          else n.delete(MF_CC);
          return n;
        },
        { replace: true }
      );
    },
    [setSearchParams]
  );

  const clearAll = useCallback(() => {
    setSearchParams(
      (prev) => {
        const n = new URLSearchParams(prev);
        MF_KEYS.forEach((k) => n.delete(k));
        return n;
      },
      { replace: true }
    );
  }, [setSearchParams]);

  /** Append current master params to an app path (for deep links from module hubs). */
  const hrefWithMasterParams = useCallback(
    (pathname) => {
      const hashIdx = pathname.indexOf("#");
      const pathAndSearch = hashIdx >= 0 ? pathname.slice(0, hashIdx) : pathname;
      const hash = hashIdx >= 0 ? pathname.slice(hashIdx) : "";
      const qIdx = pathAndSearch.indexOf("?");
      const path = qIdx >= 0 ? pathAndSearch.slice(0, qIdx) : pathAndSearch;
      const existingQs = qIdx >= 0 ? pathAndSearch.slice(qIdx + 1) : "";
      const n = new URLSearchParams(existingQs);
      MF_KEYS.forEach((k) => {
        const v = searchParams.get(k);
        if (v) n.set(k, v);
      });
      const qs = n.toString();
      return qs ? `${path}?${qs}${hash}` : `${path}${hash}`;
    },
    [searchParams]
  );

  const value = useMemo(
    () => ({
      entityCode,
      periodYm,
      periodExplicit,
      departmentId,
      costCenterId,
      setEntityCode,
      setPeriodYm,
      setDepartmentId,
      setCostCenterId,
      clearAll,
      hrefWithMasterParams,
    }),
    [
      entityCode,
      periodYm,
      periodExplicit,
      departmentId,
      costCenterId,
      setEntityCode,
      setPeriodYm,
      setDepartmentId,
      setCostCenterId,
      clearAll,
      hrefWithMasterParams,
    ]
  );

  return <MastersFilterContext.Provider value={value}>{children}</MastersFilterContext.Provider>;
}

export function useMastersFilters() {
  const ctx = useContext(MastersFilterContext);
  if (!ctx) {
    throw new Error("useMastersFilters must be used within MastersFilterProvider");
  }
  return ctx;
}
