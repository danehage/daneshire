const API_BASE = import.meta.env.VITE_API_URL || "";

export async function getPriceTargets(watchlistId) {
  const res = await fetch(`${API_BASE}/api/watchlist/${watchlistId}/targets`);
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}

export async function createPriceTarget(watchlistId, data) {
  const res = await fetch(`${API_BASE}/api/watchlist/${watchlistId}/targets`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}

export async function updatePriceTarget(watchlistId, targetId, data) {
  const res = await fetch(
    `${API_BASE}/api/watchlist/${watchlistId}/targets/${targetId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }
  );
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}

export async function deletePriceTarget(watchlistId, targetId) {
  const res = await fetch(
    `${API_BASE}/api/watchlist/${watchlistId}/targets/${targetId}`,
    { method: "DELETE" }
  );
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
}
