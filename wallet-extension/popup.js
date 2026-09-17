// RustChain Browser Extension Popup Logic
const NODE_URL = "https://50.28.86.131";
const DEFAULT_WALLET = "RTC8b1fb717791b0a7b72649342b5c7c7bd822786af";

document.addEventListener("DOMContentLoaded", () => {
  const balanceDisplay = document.getElementById("balance-display");
  const walletDisplay = document.getElementById("wallet-display");
  const sendTabBtn = document.getElementById("send-tab-btn");
  const refreshBtn = document.getElementById("refresh-btn");
  const sendView = document.getElementById("send-view");
  const submitTransferBtn = document.getElementById("submit-transfer-btn");
  const statusDisplay = document.getElementById("status-display");

  walletDisplay.textContent = DEFAULT_WALLET;

  async function fetchBalance() {
    balanceDisplay.textContent = "Loading...";
    try {
      const resp = await fetch(`${NODE_URL}/wallet/balance?miner_id=${DEFAULT_WALLET}`, {
        method: "GET",
        headers: { Accept: "application/json" }
      });
      if (resp.ok) {
        const data = await resp.json();
        const bal = data.balance_rtc !== undefined ? data.balance_rtc : data.balance;
        balanceDisplay.textContent = `${parseFloat(bal || 0).toFixed(4)} RTC`;
      } else {
        balanceDisplay.textContent = "0.0000 RTC";
      }
    } catch (e) {
      balanceDisplay.textContent = "0.0000 RTC (Offline)";
    }
  }

  sendTabBtn.addEventListener("click", () => {
    sendView.style.display = sendView.style.display === "none" ? "block" : "none";
  });

  refreshBtn.addEventListener("click", fetchBalance);

  submitTransferBtn.addEventListener("click", async () => {
    const recipient = document.getElementById("recipient-input").value.trim();
    const amount = parseFloat(document.getElementById("amount-input").value);
    const memo = document.getElementById("memo-input").value.trim();

    if (!recipient.startsWith("RTC") || recipient.length < 20) {
      statusDisplay.style.color = "#f85149";
      statusDisplay.textContent = "Invalid recipient RTC address";
      return;
    }

    if (isNaN(amount) || amount <= 0) {
      statusDisplay.style.color = "#f85149";
      statusDisplay.textContent = "Invalid amount";
      return;
    }

    statusDisplay.style.color = "#8b949e";
    statusDisplay.textContent = "Signing & transmitting transaction...";

    const payload = {
      from_address: DEFAULT_WALLET,
      to_address: recipient,
      amount_rtc: amount,
      memo: memo || "Browser extension transfer",
      nonce: Date.now()
    };

    try {
      const resp = await fetch(`${NODE_URL}/wallet/transfer/signed`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await resp.json();
      if (resp.ok && data.ok) {
        statusDisplay.style.color = "#3fb950";
        statusDisplay.textContent = `Success! TX: ${data.tx_hash || "Broadcasted"}`;
        fetchBalance();
      } else {
        statusDisplay.style.color = "#f85149";
        statusDisplay.textContent = `Error: ${data.error || "Transfer failed"}`;
      }
    } catch (e) {
      statusDisplay.style.color = "#f85149";
      statusDisplay.textContent = `Network error connecting to node`;
    }
  });

  fetchBalance();
});
