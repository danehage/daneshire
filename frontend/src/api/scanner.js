const API_BASE = import.meta.env.VITE_API_URL || "";

export async function getUniverses() {
  const res = await fetch(`${API_BASE}/api/scan/universes`);
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}

export async function executeScan(data) {
  const res = await fetch(`${API_BASE}/api/scan/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}

export async function getScanResults(scanId) {
  const res = await fetch(`${API_BASE}/api/scan/${scanId}/results`);
  if (!res.ok) {
    if (res.status === 202) {
      throw new Error("Scan still in progress");
    }
    throw new Error(`${res.status}: ${res.statusText}`);
  }
  return res.json();
}

export async function analyzeTicker(symbol) {
  const res = await fetch(`${API_BASE}/api/scan/ticker/${symbol}`);
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}

export function createScanStream(scanId) {
  const url = `${API_BASE}/api/scan/${scanId}/stream`;
  return new EventSource(url);
}
