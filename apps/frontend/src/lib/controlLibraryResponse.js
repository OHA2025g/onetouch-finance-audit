/** Normalizes GET /control-library body (legacy array or Phase 40 `{ entity_code, items }`). */
export function controlLibraryItemsFromResponse(data) {
  if (Array.isArray(data)) return data;
  const items = data?.items;
  return Array.isArray(items) ? items : [];
}
