const API_BASE = import.meta.env.VITE_API_URL || "";

export async function getJournalEntries(watchlistId) {
  const res = await fetch(`${API_BASE}/api/watchlist/${watchlistId}/journal`);
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}

export async function createJournalEntry(watchlistId, data) {
  const res = await fetch(`${API_BASE}/api/watchlist/${watchlistId}/journal`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}

export async function updateJournalEntry(entryId, data) {
  const res = await fetch(`${API_BASE}/api/journal/${entryId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}

export async function deleteJournalEntry(entryId) {
  const res = await fetch(`${API_BASE}/api/journal/${entryId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
}

export async function searchJournal(query, entryType = null, limit = 50) {
  const params = new URLSearchParams({ q: query, limit: String(limit) });
  if (entryType) params.append("entry_type", entryType);
  const res = await fetch(`${API_BASE}/api/journal/search?${params}`);
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}
