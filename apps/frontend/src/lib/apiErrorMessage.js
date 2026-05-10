/**
 * Normalize FastAPI validation errors and other axios error payloads for UI/toasts.
 * @param {unknown} err - axios error or any thrown value
 * @param {string} fallback
 * @returns {string}
 */
export function errorMessageFromAxios(err, fallback = "Request failed") {
  const d = err && typeof err === "object" && "response" in err ? err.response?.data?.detail : undefined;
  if (typeof d === "string" && d.trim()) return d.trim();
  if (Array.isArray(d)) {
    const parts = d
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object" && item.msg) return String(item.msg);
        return null;
      })
      .filter(Boolean);
    if (parts.length) return parts.join("; ");
  }
  if (d && typeof d === "object" && typeof d.message === "string" && d.message.trim()) return d.message.trim();
  if (err && typeof err === "object" && "message" in err && typeof err.message === "string") {
    return err.message || fallback;
  }
  return fallback;
}

/**
 * Like `errorMessageFromAxios`, but when the request used `responseType: 'blob'`, FastAPI errors are JSON inside a Blob.
 */
export async function errorMessageFromAxiosBlob(err, fallback = "Request failed") {
  const data = err && typeof err === "object" && "response" in err ? err.response?.data : undefined;
  let parsedFromBody = null;
  if (data != null) {
    try {
      let text = null;
      if (typeof data.text === "function") {
        text = await data.text();
      } else if (typeof data.arrayBuffer === "function") {
        const buf = await data.arrayBuffer();
        text = new TextDecoder().decode(buf);
      }
      if (text) {
        const j = JSON.parse(text);
        const d = j?.detail;
        if (typeof d === "string" && d.trim()) parsedFromBody = d.trim();
        else if (Array.isArray(d)) {
          const parts = d
            .map((item) => (item && typeof item === "object" && item.msg ? String(item.msg) : null))
            .filter(Boolean);
          if (parts.length) parsedFromBody = parts.join("; ");
        }
      }
    } catch {
      /* fall through */
    }
  }
  if (parsedFromBody) return parsedFromBody;
  return errorMessageFromAxios(err, fallback);
}
