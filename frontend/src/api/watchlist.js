const API_BASE = import.meta.env.VITE_API_URL || "";

export async function getWatchlist(status) {
  const params = status ? `?status=${status}` : "";
  const res = await fetch(`${API_BASE}/api/watchlist${params}`);
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}

export async function getWatchlistItem(id) {
  const res = await fetch(`${API_BASE}/api/watchlist/${id}`);
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}

export async function createWatchlistItem(data) {
  const res = await fetch(`${API_BASE}/api/watchlist`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}

export async function updateWatchlistItem(id, data) {
  const res = await fetch(`${API_BASE}/api/watchlist/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}

export async function deleteWatchlistItem(id) {
  const res = await fetch(`${API_BASE}/api/watchlist/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
}

export async function reorderWatchlist(itemIds) {
  const res = await fetch(`${API_BASE}/api/watchlist/reorder`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ items: itemIds }),
  });
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
}
