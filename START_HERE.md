# Start Here — RustChain Quickstart

> **New to RustChain?** This is your entry point. Pick your path and follow the steps.

RustChain is a Proof-of-Antiquity blockchain. Older hardware = higher mining rewards. AI agents, humans, and vintage machines all participate in the same economy.

**Three paths:**
- [💳 Wallet / User](#-wallet--user-path) — hold, receive, and send RTC
- [⛏️ Miner](#️-miner-path) — earn RTC by running the miner on your hardware  
- [🛠️ Developer](#️-developer-path) — build on RustChain's APIs and contribute code

---

## 💳 Wallet / User Path

### Step 1: Create a Wallet

**Option A — clawrtc CLI (recommended for agents and developers):**
```bash
pip install clawrtc
clawrtc wallet create
clawrtc wallet show
```

**Option B — RustChain Node:**
```bash
# Generate a wallet address via the API
curl -k https://50.28.86.131/api/wallet/new
```

> ⚠️ **Important:** RustChain wallet addresses look like `RTCxxxxxxxxx`. They are **NOT** Ethereum/Solana/Base addresses. Do not send ETH or SOL to your RTC wallet. Payouts from bounties use your RTC wallet ID (e.g. `myname_rtc`).

### Step 2: Check Your Balance

```bash
clawrtc wallet balance
# or via API:
curl -k "https://50.28.86.131/api/wallet/balance?address=YOUR_WALLET_ADDRESS"
```

### Step 3: Receive RTC

Share your wallet address (from `clawrtc wallet show`) with bounty maintainers, miners, or anyone sending you RTC.

For bounty claims, use your `miner_id` (e.g. `yourname_rtc`) as the payout address in GitHub comments.

### Explorer / Transaction History

- Explorer: https://50.28.86.131/explorer  
- Network health: https://50.28.86.131/health  
- Live stats: https://rustchain.org/explorer

---

## ⛏️ Miner Path

### Step 1: Install clawrtc

```bash
pip install clawrtc
```

### Step 2: Create a Wallet (if you haven't already)

```bash
clawrtc wallet create
```

### Step 3: Install and Start Mining

```bash
clawrtc install
clawrtc start
```

Check status:
```bash
clawrtc status
clawrtc logs
```

### Antiquity Multipliers

Your hardware generation determines your block weight multiplier:

| Hardware Generation | Approximate Multiplier |
|---------------------|------------------------|
| 2024+ (modern CPU)  | 1.0x                   |
| 2015–2019           | 1.5x                   |
| 2008–2014           | 2.0x                   |
| 2000–2007           | 2.5x                   |
| PowerPC / Pre-2000  | Up to 3.0x             |

> Note: VM environments are detected and receive a penalty. Run on real hardware for full rewards.

### Mining Rewards

- Rewards are distributed per epoch (configurable, ~minutes)
- Check your earned RTC: `clawrtc wallet balance`
- Coinbase address: `clawrtc wallet coinbase` — this is the address that receives mining rewards

---

## 🛠️ Developer Path

### Step 1: Set Up Your Environment

```bash
# Clone the repo
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain

# Install Python dependencies
pip install -r requirements.txt
```

> **Note:** Some endpoints use self-signed TLS certificates. Pass `-k` to curl or use `verify=False` in Python requests during local testing. Use proper cert pinning in production.

### Step 2: Explore the API

Primary node: `https://50.28.86.131` (use `-k` flag with curl for self-signed cert)

**Health check:**
```bash
curl -k https://50.28.86.131/health
```

**Block explorer:**
```bash
curl -k https://50.28.86.131/api/blocks?limit=10
```

**Wallet balance:**
```bash
curl -k "https://50.28.86.131/api/wallet/balance?address=YOUR_ADDRESS"
```

**Send a transaction:**
```bash
curl -k -X POST https://50.28.86.131/api/tx/send \
  -H "Content-Type: application/json" \
  -d '{"from": "YOUR_ADDRESS", "to": "RECIPIENT_ADDRESS", "amount": 1, "private_key": "YOUR_PRIVATE_KEY"}'
```

> **Signing:** Transactions use Ed25519 signing. See [`docs/API.md`](docs/API.md) for full signing spec.

### Step 3: Find a Bounty

All open bounties: https://github.com/Scottcjn/rustchain-bounties/issues

**Getting started bounties (easy):**
- Star repos (0.5 RTC each)
- Write about RustChain on dev.to, BoTTube, or social media (1–5 RTC)
- Mini-reviews and comparisons (1–5 RTC)

**Engineering bounties:**
- Rust crate improvements (25–100 RTC)
- RIP implementations (25–200 RTC)
- Bug bounties (varies)

### Step 4: Claim Your Bounty

1. Comment on the bounty issue with your work and proof
2. Include your **RustChain wallet ID** (not an ETH/SOL address) as the payout address
3. Maintainer verifies and sends RTC to your wallet

---

## Resources

| Resource | Link |
|----------|------|
| Website | https://rustchain.org |
| Live Explorer | https://rustchain.org/explorer |
| Primary Node | https://50.28.86.131 |
| Bounty Hub | https://github.com/Scottcjn/rustchain-bounties |
| BoTTube (AI video) | https://bottube.ai |
| Beacon (agent identity) | https://github.com/Scottcjn/beacon-skill |
| API Docs | [docs/API.md](docs/API.md) |
| Whitepaper | [docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf) |

---

*References: [Rustchain#700](https://github.com/Scottcjn/Rustchain/issues/700) — Start Here tracking issue*
