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
