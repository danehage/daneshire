const API_BASE = import.meta.env.VITE_API_URL || "";

export async function getAlerts(status, ticker) {
  const params = new URLSearchParams();
  if (status) params.append("status", status);
  if (ticker) params.append("ticker", ticker);
  const query = params.toString() ? `?${params.toString()}` : "";
  const res = await fetch(`${API_BASE}/api/alerts${query}`);
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}

export async function getAlert(id) {
  const res = await fetch(`${API_BASE}/api/alerts/${id}`);
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}

export async function createAlert(data) {
  const res = await fetch(`${API_BASE}/api/alerts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}

export async function updateAlert(id, data) {
  const res = await fetch(`${API_BASE}/api/alerts/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}

export async function deleteAlert(id) {
  const res = await fetch(`${API_BASE}/api/alerts/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
}

export async function dismissAlert(id) {
  const res = await fetch(`${API_BASE}/api/alerts/${id}/dismiss`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}

export async function getAlertHistory(id) {
  const res = await fetch(`${API_BASE}/api/alerts/${id}/history`);
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}
