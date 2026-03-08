# RustChain Start Here

Welcome to RustChain! This quickstart guide will help you enter the ecosystem in minutes.

## Choose Your Path

- **[Wallet/User](#wallet-user)** — I want to receive/send RTC tokens
- **[Miner](#miner)** — I want to mine RTC with my hardware
- **[Developer](#developer)** — I want to build apps on RustChain

---

## 🚀 Wallet / User

### Create a Wallet

Any string can be your wallet ID. No registration needed!

```bash
# Your wallet is just a name - no setup required
# Example: "tomisnotcat"
```

### Check Balance

```bash
curl "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

Example:
```bash
curl "https://50.28.86.131/wallet/balance?miner_id=tomisnotcat"
# Response: {"amount_i64":0,"amount_rtc":0.0,"miner_id":"tomisnotcat"}
```

### Important: Wallet IDs ≠ ETH/SOL/Base Addresses

⚠️ **RustChain wallet IDs are simple strings**, not blockchain addresses!

- ✅ RustChain wallet: `tomisnotcat`
- ❌ Not an ETH address: `0x123...`
- ❌ Not SOL address: `abc...`

When someone says "give me your wallet address" in RustChain, just give them your wallet ID (like `tomisnotcat`).

---

## ⛏️ Miner

### Install and Start Mining

```bash
# Install the miner
pip install clawrtc

# Set up with your wallet
clawrtc install --wallet YOUR_WALLET_NAME

# Start mining
clawrtc start
```

### Check Miner Status

```bash
clawrtc status
clawrtc logs
```

### Hardware Multipliers

| Hardware | Multiplier |
|----------|------------|
| Modern x86/ARM | 1.0x |
| Apple Silicon (M1/M2/M3) | 1.2x |
| PowerPC G5 | 2.0x |
| PowerPC G4 | 2.5x |
| VM/Emulator | ~0x |

### View Active Miners

```bash
curl "https://50.28.86.131/api/miners"
```

---

## 👨‍💻 Developer

### API Base URL

```
https://50.28.86.131
```

### Common API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Node health status |
| `/wallet/balance?miner_id=...` | GET | Check wallet balance |
| `/lottery/eligibility?miner_id=...` | GET | Check mining eligibility |
| `/api/miners` | GET | List active miners |
| `/wallet/transfer/signed` | POST | Signed transfer (requires key) |

### Example: Check Node Health

```bash
curl "https://50.28.86.131/health"
# Response: {"ok":true,"version":"2.2.1-rip200",...}
```

### Example: Check Wallet Balance

```bash
curl "https://50.28.86.131/wallet/balance?miner_id=tomisnotcat"
# Response: {"amount_i64":0,"amount_rtc":0.0,"miner_id":"tomisnotcat"}
```

### Example: Check Mining Eligibility

```bash
curl "https://50.28.86.131/lottery/eligibility?miner_id=tomisnotcat"
# Response: {"eligible":false,"reason":"not_attested",...}
```

### Signed Transfers

To send RTC, you need to sign the transaction with your Ed25519 key. See the [API Walkthrough](./docs/API_WALKTHROUGH.md) for detailed signed transfer instructions.

### Self-Signed Certificate Note

The node uses a self-signed certificate. Use `-k` or `--insecure` flag with curl:

```bash
curl -k "https://50.28.86.131/health"
```

---

## 📚 Resources

- **Explorer**: https://rustchain.org/
- **Bounties**: https://github.com/Scottcjn/rustchain-bounties
- **GitHub Repo**: https://github.com/Scottcjn/Rustchain
- **BoTTube** (Video Platform): https://bottube.ai
- **Discord**: Join the community for help

---

## Need Help?

- Check existing issues: https://github.com/Scottcjn/Rustchain/issues
- Open a new issue: https://github.com/Scottcjn/Rustchain/issues/new
- Check bounty list: https://github.com/Scottcjn/rustchain-bounties
