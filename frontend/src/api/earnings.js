const API_BASE = import.meta.env.VITE_API_URL || '';

export async function getEarningsCalendar({ start, end } = {}) {
  const params = new URLSearchParams();
  if (start) params.set('start', start);
  if (end) params.set('end', end);
  const query = params.toString() ? `?${params}` : '';
  const res = await fetch(`${API_BASE}/api/earnings/calendar${query}`);
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}

export async function getEarningsScreen({
  start,
  end,
  minIvRank,
  minEdgeRatio,
  minVolume,
} = {}) {
  const params = new URLSearchParams();
  if (start) params.set('start', start);
  if (end) params.set('end', end);
  if (minIvRank != null && minIvRank !== '') params.set('min_iv_rank', minIvRank);
  if (minEdgeRatio != null && minEdgeRatio !== '') params.set('min_edge_ratio', minEdgeRatio);
  if (minVolume != null && minVolume !== '') params.set('min_volume', minVolume);
  const query = params.toString() ? `?${params}` : '';
  const res = await fetch(`${API_BASE}/api/earnings/screen${query}`);
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}

export async function getEarningsExpectedMove(ticker) {
  const res = await fetch(`${API_BASE}/api/earnings/${encodeURIComponent(ticker)}/expected-move`);
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Earnings trades CRUD (issue #16)
// ---------------------------------------------------------------------------

export async function getEarningsTrades({ status, ticker, start, end } = {}) {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  if (ticker) params.set('ticker', ticker);
  if (start) params.set('start', start);
  if (end) params.set('end', end);
  const query = params.toString() ? `?${params}` : '';
  const res = await fetch(`${API_BASE}/api/earnings/trades${query}`);
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}

export async function createEarningsTrade(data) {
  const res = await fetch(`${API_BASE}/api/earnings/trades`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body || res.statusText}`);
  }
  return res.json();
}

export async function updateEarningsTrade(id, patch) {
  const res = await fetch(`${API_BASE}/api/earnings/trades/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body || res.statusText}`);
  }
  return res.json();
}

export async function deleteEarningsTrade(id) {
  const res = await fetch(`${API_BASE}/api/earnings/trades/${id}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
}
