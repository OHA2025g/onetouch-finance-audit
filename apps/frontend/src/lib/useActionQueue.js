import { useCallback, useState } from "react";
import { http } from "./api";

export function useActionQueue(dashboardParams) {
  const [queue, setQueue] = useState(null);
  const [dashboard, setDashboard] = useState(null);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);

  const loadDashboard = useCallback(
    async (extra = {}) => {
      setLoading(true);
      try {
        const { data } = await http.get("/cfo/action-queue/dashboard", {
          params: { ...dashboardParams, record_snapshot: true, ...extra },
        });
        setDashboard(data);
        return data;
      } finally {
        setLoading(false);
      }
    },
    [dashboardParams],
  );

  const loadList = useCallback(
    async (opts = {}) => {
      const { refresh = false, sort = "score", append = false, cursor: cursorIn, ...filters } = opts;
      if (refresh) setRefreshing(true);
      else if (append) setLoadingMore(true);
      else setLoading(true);
      try {
        const params = {
          ...dashboardParams,
          refresh,
          sort,
          limit: 50,
          ...filters,
        };
        if (append && cursorIn) {
          params.cursor = cursorIn;
          params.offset = 0;
        } else {
          params.offset = 0;
        }
        const { data } = await http.get("/cfo/action-queue", { params });
        if (append && data?.items?.length) {
          setQueue((prev) => {
            const prevItems = prev?.items || [];
            const ids = new Set(prevItems.map((i) => i.id));
            const merged = [...prevItems, ...data.items.filter((i) => !ids.has(i.id))];
            return { ...data, items: merged };
          });
        } else {
          setQueue(data);
        }
        return data;
      } finally {
        setLoading(false);
        setRefreshing(false);
        setLoadingMore(false);
      }
    },
    [dashboardParams],
  );

  const loadDetail = useCallback(async (id) => {
    const { data } = await http.get(`/cfo/action-queue/${encodeURIComponent(id)}`);
    setDetail(data);
    return data;
  }, []);

  const actOnItem = useCallback(async (actionId, kind, note = "", rejectReason = null) => {
    const path =
      kind === "approve"
        ? `/cfo/action/${actionId}/approve`
        : kind === "reject"
          ? `/cfo/action/${actionId}/reject`
          : kind === "escalate"
            ? `/cfo/action/${actionId}/escalate`
            : kind === "reopen"
              ? `/cfo/action/${actionId}/reopen`
              : `/cfo/action/${actionId}/comment`;
    const body =
      kind === "comment"
        ? { comment: note }
        : { note, ...(rejectReason ? { reject_reason: rejectReason } : {}) };
    await http.post(path, body);
  }, []);

  const bulkAct = useCallback(async (ids, action, note = "", rejectReason = null) => {
    const { data } = await http.post("/cfo/action/bulk", {
      ids,
      action,
      note,
      ...(rejectReason ? { reject_reason: rejectReason } : {}),
    });
    return data;
  }, []);

  const exportCsv = useCallback(async () => {
    const resp = await http.get("/cfo/action-queue/export", {
      params: { ...dashboardParams, format: "csv" },
      responseType: "blob",
    });
    const url = window.URL.createObjectURL(new Blob([resp.data]));
    const a = document.createElement("a");
    a.href = url;
    a.download = "cfo_action_queue.csv";
    a.click();
    window.URL.revokeObjectURL(url);
  }, [dashboardParams]);

  const exportXlsx = useCallback(async () => {
    const resp = await http.get("/cfo/action-queue/export", {
      params: { ...dashboardParams, format: "xlsx" },
      responseType: "blob",
    });
    const url = window.URL.createObjectURL(new Blob([resp.data]));
    const a = document.createElement("a");
    a.href = url;
    a.download = "cfo_action_queue.xlsx";
    a.click();
    window.URL.revokeObjectURL(url);
  }, [dashboardParams]);

  return {
    queue,
    dashboard,
    detail,
    setDetail,
    loading,
    refreshing,
    loadingMore,
    loadDashboard,
    loadList,
    loadDetail,
    actOnItem,
    bulkAct,
    exportCsv,
    exportXlsx,
  };
}
