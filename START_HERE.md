# RustChain Start Here

**Quick entry point for wallet users, miners, and developers.**

> This guide addresses [Scottcjn/Rustchain#700](https://github.com/Scottcjn/Rustchain/issues/700)

---

## Important: Wallet ID vs External Addresses

⚠️ **RustChain payout wallets use RustChain wallet IDs, NOT ETH/SOL/Base addresses.**

- ✅ Correct: `your_wallet_name` (RustChain native wallet ID)
- ❌ Wrong: `0xABC...` (Ethereum), `SolanaAddress...` (Solana), `0xABC...` (Base)

**When someone asks for your "wallet address" in RustChain, give them your RustChain wallet ID (miner_id), not an external chain address.**

---

## Choose Your Path

| Path | Who it's for | Time to first action |
|------|---------------|---------------------|
| [🪙 Wallet/User](#-wallet--user) | Want to check balance, receive RTC | 2 min |
| [⛏️ Miner](#-miner) | Want to mine RTC with vintage hardware | 10 min |
| [💻 Developer](#-developer) | Want to build on RustChain APIs | 5 min |

---

## 🪙 Wallet / User

### Check Your Balance

```bash
# Replace YOUR_WALLET_NAME with your RustChain wallet ID
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_NAME" | jq .
```

**Expected response:**
```json
{
  "amount_i64": 0,
  "amount_rtc": 0.0,
  "miner_id": "YOUR_WALLET_NAME"
}
```

> ⚠️ **Self-signed certificate note:** The `-k` flag disables TLS verification. For production, add the RustChain CA to your trust store.

### View Active Miners

```bash
curl -sk https://rustchain.org/api/miners | jq .
```

### Check Node Health

```bash
curl -sk https://rustchain.org/health | jq .
```

### Useful Links

| Resource | URL |
|----------|-----|
| Explorer | https://rustchain.org/explorer |
| Health Check | https://rustchain.org/health |
| Wallet Guide | [docs/WALLET_USER_GUIDE.md](docs/WALLET_USER_GUIDE.md) |
| Bounty Board | https://github.com/Scottcjn/rustchain-bounties/issues |

---

## ⛏️ Miner

### Quick Install (Recommended)

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

The installer:
- Auto-detects your platform (Linux/macOS, x86_64/ARM/PowerPC)
- Creates an isolated Python virtualenv
- Downloads the correct miner for your hardware
- Sets up auto-start on boot

### Manual Setup

```bash
# Clone the repository
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the miner (replace YOUR_WALLET_NAME)
python3 -m node.miner.main --miner_id YOUR_WALLET_NAME
```

### Verify Your Miner is Running

```bash
# Check if your miner appears in the active list
curl -sk https://rustchain.org/api/miners | jq '.[] | select(.miner | contains("YOUR_WALLET_NAME"))'
```

### Useful Links

| Resource | URL |
|----------|-----|
| Mining Guide | [docs/CONSOLE_MINING_SETUP.md](docs/CONSOLE_MINING_SETUP.md) |
| FAQ/Troubleshooting | [docs/FAQ_TROUBLESHOOTING.md](docs/FAQ_TROUBLESHOOTING.md) |
| Hardware Fingerprinting | [docs/hardware-fingerprinting.md](docs/hardware-fingerprinting.md) |

---

## 💻 Developer

### API Base URL

```
https://rustchain.org
```

> ⚠️ **Self-signed certificate note:** Use `-k` flag with curl, or add the CA to your trust store.

### Quick API Examples

#### Health Check

```bash
curl -sk https://rustchain.org/health | jq .
```

#### Get Current Epoch

```bash
curl -sk https://rustchain.org/epoch | jq .
```

#### List Active Miners

```bash
curl -sk https://rustchain.org/api/miners | jq .
```

#### Get Wallet Balance

```bash
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_NAME" | jq .
```

### SDK Installation

```bash
pip install rustchain-sdk
```

### Useful Links

| Resource | URL |
|----------|-----|
| Full API Reference | [docs/API.md](docs/API.md) |
| Protocol Documentation | [docs/PROTOCOL.md](docs/PROTOCOL.md) |
| Developer Guide | [docs/DEV_GUIDE.md](docs/DEV_GUIDE.md) |
| Contributing | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Bounties | https://github.com/Scottcjn/rustchain-bounties/issues |

---

## Bounties & Contributing

Every contribution earns RTC tokens!

1. Browse [open bounties](https://github.com/Scottcjn/rustchain-bounties/issues)
2. Pick a [good first issue](https://github.com/Scottcjn/Rustchain/labels/good%20first%20issue)
3. Fork, fix, PR — get paid in RTC

| Tier | Reward | Examples |
|------|--------|----------|
| Micro | 1-10 RTC | Typo fix, small docs |
| Standard | 20-50 RTC | Feature, new endpoint |
| Major | 75-100 RTC | Security fix |

---

*Last updated: 2025-03-09 | [Edit this page](https://github.com/Scottcjn/Rustchain/edit/main/START_HERE.md)*
