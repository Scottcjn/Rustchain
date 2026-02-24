export const API_BASE = 'https://50.28.86.131';

export async function getBalance(minerId: string) {
  const r = await fetch(`${API_BASE}/wallet/balance?miner_id=${encodeURIComponent(minerId)}`);
  if (!r.ok) throw new Error(`balance ${r.status}`);
  return r.json();
}

export async function sendRtc(payload: {from: string; to: string; amount: number; signature?: string}) {
  const r = await fetch(`${API_BASE}/wallet/transfer`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
  if (!r.ok) throw new Error(`transfer ${r.status}`);
  return r.json();
}

export async function txHistory(minerId: string) {
  const r = await fetch(`${API_BASE}/wallet/history?miner_id=${encodeURIComponent(minerId)}`);
  if (!r.ok) throw new Error(`history ${r.status}`);
  return r.json();
}
