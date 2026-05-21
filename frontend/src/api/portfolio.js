const API_BASE = import.meta.env.VITE_API_URL || "";

export async function getAccounts() {
  const res = await fetch(`${API_BASE}/api/portfolio/accounts`);
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}

export async function getPortfolio(accountId) {
  const params = accountId ? `?account_id=${accountId}` : "";
  const res = await fetch(`${API_BASE}/api/portfolio${params}`);
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}

export async function commitSnapshot(data) {
  const res = await fetch(`${API_BASE}/api/portfolio/snapshots/commit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}
