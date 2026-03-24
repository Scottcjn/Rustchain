# RustChain Start Here

Welcome to RustChain! This guide gets you started in minutes.

---

## Quick Comparison

| Path | Best For | Reward Potential |
|------|----------|------------------|
| **Wallet** | Using RTC, payments | N/A |
| **Miner** | Earning RTC passively | 1-100+ RTC/day |
| **Developer** | Building apps, tools | Bounties |

---

## Path 1: Wallet User

Check balances and learn the current transfer flow.

### Pick Your RustChain Wallet ID

```bash
# Example wallet/miner ID used across docs and miners
YOUR_WALLET=retro-g5-miner
```

Current `clawrtc` releases do **not** ship `wallet new`, `wallet show`, or `wallet pay` subcommands. `clawrtc` is the miner installer/service wrapper. For wallet basics, keep one consistent RustChain wallet ID (`miner_id`) and use the balance + signed transfer docs below.

### Check Balance

```bash
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET"
```

**Note:** Your RustChain wallet ID is a RustChain-specific `miner_id`. It is not an Ethereum or Solana address.

### Transfer RTC

- User transfers use the signed endpoint: `POST /wallet/transfer/signed`
- Admin transfers use: `POST /wallet/transfer`
- Canonical examples live in [docs/DEVELOPER_QUICKSTART.md](docs/DEVELOPER_QUICKSTART.md) and [docs/WALLET_USER_GUIDE.md](docs/WALLET_USER_GUIDE.md)

---

## Path 2: Miner

Earn RTC by contributing compute resources.

### Requirements

- Linux (recommended), macOS, or Windows
- 4GB+ RAM
- GPU recommended (4GB+ VRAM) for better rewards

### Start Mining

**Recommended: current `clawrtc` installer**

```bash
# Install the miner wrapper and write config for your wallet ID
npm install -g clawrtc
clawrtc install --wallet YOUR_WALLET

# Start the miner
clawrtc start --service
```

`clawrtc status` and `clawrtc logs` are the supported management commands in current releases.

**Alternative: manual Python miner**

```bash
# Download miner scripts
mkdir -p ~/.rustchain && cd ~/.rustchain
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners/linux/rustchain_linux_miner.py -o rustchain_miner.py
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners/linux/fingerprint_checks.py -o fingerprint_checks.py

# Run miner
python3 rustchain_miner.py --wallet YOUR_WALLET
```

### Manage Miner

```bash
# Cross-platform wrapper
clawrtc status
clawrtc logs
clawrtc stop
clawrtc start --service

# Linux/macOS service manager fallback
systemctl --user status rustchain-miner
journalctl --user -u rustchain-miner -f
```

### Check Rewards

```bash
curl -s "https://rustchain.org/api/miners?wallet=YOUR_WALLET"
```

---

## Path 3: Developer

Build apps on RustChain.

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `/health` | Node health check |
| `/ready` | Readiness probe |
| `/epoch` | Current epoch info |
| `/api/miners` | List active miners |
| `/wallet/balance?miner_id=X` | Check balance |
| `/api/stats` | Chain statistics |
| `/api/hall_of_fame` | Top miners |

**Primary Node:** `https://rustchain.org`  
**Explorer:** `https://rustchain.org/explorer`

### Python Example

```python
import requests

# Check balance
r = requests.get(
    "https://rustchain.org/wallet/balance",
    params={"miner_id": "Ivan-houzhiwen"},
    verify=False  # Self-signed cert
)
print(r.json())
# {"amount_rtc": 155.0, "miner_id": "Ivan-houzhiwen"}
```

### Note on SSL

The nodes use self-signed certificates. Use `verify=False` in Python or `--insecure` in curl.

---

## Resources

- **Bounties:** https://github.com/Scottcjn/rustchain-bounties
- **Explorer:** https://rustchain.org/explorer
- **Health:** https://rustchain.org/health
- **Wallet Guide:** [docs/WALLET_USER_GUIDE.md](docs/WALLET_USER_GUIDE.md)
- **Developer Quickstart:** [docs/DEVELOPER_QUICKSTART.md](docs/DEVELOPER_QUICKSTART.md)

---

*Last updated: 2026-03-09*
