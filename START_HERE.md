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

Get a wallet to hold and transfer RTC.

### Create Wallet

```bash
# Install CLI
npm install -g clawrtc

# Create new wallet
clawrtc wallet new
```

**Output example:**
```
Wallet: Ivan-houzhiwen
Address: RTCa...
```

### Check Balance

```bash
# Via CLI
clawrtc wallet show

# Via API
curl -s "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET"
```

**Note:** Your RustChain wallet ID (e.g., `Ivan-houzhiwen`) is NOT an Ethereum or Solana address. It's a RustChain-specific identifier.

### Transfer RTC

```bash
clawrtc wallet pay --to RECIPIENT --amount 10
```

---

## Path 2: Miner

Earn RTC by contributing compute resources.

### Requirements

- Linux (recommended) or Windows
- 4GB+ RAM
- GPU recommended (4GB+ VRAM) for better rewards

### Start Mining

```bash
# Install
git clone https://github.com/Scottcjn/Rustchain
cd Rustchain
cargo build --release

# Run miner
./target/release/rustchain-miner --wallet YOUR_WALLET
```

### Check Rewards

```bash
curl -s "https://50.28.86.131/api/miners?wallet=YOUR_WALLET"
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

**Primary Node:** `https://50.28.86.131`  
**Explorer:** `https://50.28.86.131/explorer`

### Python Example

```python
import requests

# Check balance
r = requests.get(
    "https://50.28.86.131/wallet/balance",
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
- **Explorer:** https://50.28.86.131/explorer
- **Health:** https://50.28.86.131/health

---

*Last updated: 2026-03-09*
