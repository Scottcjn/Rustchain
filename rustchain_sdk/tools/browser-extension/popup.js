(function () {
  "use strict";

  const NODE_URL = "https://rustchain.org";
  const NODE_IP  = "https://50.28.86.131";

  const $ = (sel) => document.querySelector(sel);

  // --- DOM refs ---
  const minerInput   = $("#miner-id");
  const btnRefresh   = $("#btn-refresh");
  const balanceCard  = $("#balance-display");
  const balanceValue = $("#balance-value");
  const balanceError = $("#balance-error");
  const netStatus    = $("#net-status");
  const netVersion   = $("#net-version");
  const netUptime    = $("#net-uptime");
  const blockEpoch   = $("#block-epoch");
  const blockSlot    = $("#block-slot");
  const blockHeight  = $("#block-height");

  // --- Helpers ---

  function formatUptime(seconds) {
    const d = Math.floor(seconds / 86400);
    const h = Math.floor((seconds % 86400) / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    if (d > 0) return d + "d " + h + "h";
    if (h > 0) return h + "h " + m + "m";
    return m + "m";
  }

  async function apiFetch(path, useIP) {
    const base = useIP ? NODE_IP : NODE_URL;
    const resp = await fetch(base + path, { cache: "no-cache" });
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    return resp.json();
  }

  // Try primary URL first, fall back to IP
  async function apiFetchWithFallback(path) {
    try {
      return await apiFetch(path, false);
    } catch (_) {
      return await apiFetch(path, true);
    }
  }

  // --- Data loaders ---

  async function loadHealth() {
    try {
      const data = await apiFetchWithFallback("/health");
      netStatus.textContent = data.ok ? "Online" : "Degraded";
      netStatus.className = "value " + (data.ok ? "status-ok" : "status-down");
      netVersion.textContent = data.version || "--";
      netUptime.textContent = data.uptime_s ? formatUptime(data.uptime_s) : "--";
    } catch (err) {
      netStatus.textContent = "Offline";
      netStatus.className = "value status-down";
      netVersion.textContent = "--";
      netUptime.textContent = "--";
    }
  }

  async function loadEpoch() {
    try {
      const data = await apiFetchWithFallback("/epoch");
      blockEpoch.textContent  = data.epoch  != null ? data.epoch  : "--";
      blockSlot.textContent   = data.slot   != null ? data.slot   : "--";
      blockHeight.textContent = data.height != null ? data.height : "--";
    } catch (_) {
      blockEpoch.textContent  = "--";
      blockSlot.textContent   = "--";
      blockHeight.textContent = "--";
    }
  }

  async function loadBalance(minerId) {
    balanceError.classList.add("hidden");
    if (!minerId) {
      balanceCard.classList.add("hidden");
      return;
    }
    balanceValue.innerHTML = '<span class="spinner"></span>';
    balanceCard.classList.remove("hidden");

    try {
      const data = await apiFetchWithFallback(
        "/wallet/balance?miner_id=" + encodeURIComponent(minerId)
      );
      if (data.amount_rtc != null) {
        balanceValue.textContent = data.amount_rtc.toLocaleString(undefined, {
          minimumFractionDigits: 2,
          maximumFractionDigits: 6
        }) + " RTC";
      } else {
        balanceValue.textContent = "0.00 RTC";
      }
    } catch (err) {
      balanceCard.classList.add("hidden");
      balanceError.textContent = "Could not fetch balance. Check your Miner ID.";
      balanceError.classList.remove("hidden");
    }
  }

  // --- Persistence ---

  function saveMiner(id) {
    if (chrome && chrome.storage && chrome.storage.local) {
      chrome.storage.local.set({ rtc_miner_id: id });
    } else {
      localStorage.setItem("rtc_miner_id", id);
    }
  }

  function restoreMiner() {
    return new Promise((resolve) => {
      if (chrome && chrome.storage && chrome.storage.local) {
        chrome.storage.local.get("rtc_miner_id", (res) => {
          resolve(res.rtc_miner_id || "");
        });
      } else {
        resolve(localStorage.getItem("rtc_miner_id") || "");
      }
    });
  }

  // --- Refresh all ---

  function refreshAll() {
    const minerId = minerInput.value.trim();
    saveMiner(minerId);
    loadHealth();
    loadEpoch();
    loadBalance(minerId);
  }

  // --- Events ---

  btnRefresh.addEventListener("click", refreshAll);

  minerInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") refreshAll();
  });

  // --- Init ---

  restoreMiner().then((id) => {
    minerInput.value = id;
    refreshAll();
  });
})();
