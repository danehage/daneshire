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

export async function commitTrade(data) {
  const res = await fetch(`${API_BASE}/api/portfolio/trades/commit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}

export async function getTrades({ accountId, ticker, since } = {}) {
  const params = new URLSearchParams();
  if (accountId) params.set("account_id", accountId);
  if (ticker) params.set("ticker", ticker);
  if (since) params.set("since", since);
  const query = params.toString() ? `?${params.toString()}` : "";
  const res = await fetch(`${API_BASE}/api/portfolio/trades${query}`);
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}
