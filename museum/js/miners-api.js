/**
 * Vintage Hardware Museum - Live Miner Data
 * Fetches from https://50.28.86.131/api/miners
 */

const MINERS_API_URL = 'https://50.28.86.131/api/miners';
const POLL_INTERVAL_MS = 30000; // 30 seconds

class MinersAPI {
  constructor() {
    this.data = null;
    this.lastFetch = 0;
    this.listeners = []; // (data) => void
    this._pollTimer = null;
    this._activeMinerKeys = new Set();
  }

  async fetch() {
    try {
      const resp = await fetch(MINERS_API_URL, {
        method: 'GET',
        headers: { 'Accept': 'application/json' },
        // Allow self-signed cert in newer fetch implementations
        mode: 'cors',
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      this.data = await resp.json();
      this.lastFetch = Date.now();
      this._activeMinerKeys = this._extractActiveKeys(this.data);
      this.listeners.forEach(fn => fn(this.data));
      return this.data;
    } catch (err) {
      console.warn('[MinersAPI] Fetch failed:', err.message);
      return null;
    }
  }

  _extractActiveKeys(data) {
    const active = new Set();
    if (!data) return active;

    // Handle various API shapes
    const miners = Array.isArray(data) ? data :
                   Array.isArray(data.miners) ? data.miners :
                   Array.isArray(data.data) ? data.data : [];

    miners.forEach(m => {
      if (m && (m.active || m.status === 'active' || m.hashrate > 0 || m.mining)) {
        const key = (m.id || m.name || m.hostname || '').toLowerCase();
        active.add(key);
      }
    });
    return active;
  }

  isActive(minerKey) {
    if (!this.data) return false;
    const mk = minerKey.toLowerCase();
    // Check by key
    if (this._activeMinerKeys.has(mk)) return true;
    // Fuzzy match: does any active miner key contain our key or vice versa?
    for (const k of this._activeMinerKeys) {
      if (k.includes(mk) || mk.includes(k)) return true;
    }
    return false;
  }

  getMinerData(minerKey) {
    if (!this.data) return null;
    const miners = Array.isArray(this.data) ? this.data :
                   Array.isArray(this.data.miners) ? this.data.miners :
                   Array.isArray(this.data.data) ? this.data.data : [];

    const mk = minerKey.toLowerCase();
    return miners.find(m => {
      const k = (m.id || m.name || m.hostname || '').toLowerCase();
      return k === mk || k.includes(mk) || mk.includes(k);
    }) || null;
  }

  getGlobalStats() {
    if (!this.data) return null;
    const miners = Array.isArray(this.data) ? this.data :
                   Array.isArray(this.data.miners) ? this.data.miners :
                   Array.isArray(this.data.data) ? this.data.data : [];

    let totalHashrate = 0;
    let activeCount = 0;
    let totalMiners = miners.length;

    miners.forEach(m => {
      if (m.hashrate) totalHashrate += Number(m.hashrate) || 0;
      if (m.active || m.status === 'active' || m.hashrate > 0 || m.mining) activeCount++;
    });

    return {
      totalMiners,
      activeCount,
      totalHashrate,
      // top-level fields
      ...(this.data.total_hashrate && { totalHashrate: this.data.total_hashrate }),
      ...(this.data.active_miners !== undefined && { activeCount: this.data.active_miners }),
      ...(this.data.pool_hashrate && { totalHashrate: this.data.pool_hashrate }),
    };
  }

  startPolling() {
    this.fetch();
    this._pollTimer = setInterval(() => this.fetch(), POLL_INTERVAL_MS);
  }

  stopPolling() {
    if (this._pollTimer) clearInterval(this._pollTimer);
  }

  onUpdate(fn) {
    this.listeners.push(fn);
  }

  formatHashrate(hr) {
    if (!hr) return 'N/A';
    hr = Number(hr);
    if (hr >= 1e12) return (hr / 1e12).toFixed(2) + ' TH/s';
    if (hr >= 1e9)  return (hr / 1e9).toFixed(2) + ' GH/s';
    if (hr >= 1e6)  return (hr / 1e6).toFixed(2) + ' MH/s';
    if (hr >= 1e3)  return (hr / 1e3).toFixed(2) + ' KH/s';
    return hr.toFixed(2) + ' H/s';
  }
}
