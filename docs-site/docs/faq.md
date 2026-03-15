# FAQ

Frequently asked questions about RustChain, mining, RTC tokens, and the ecosystem.

---

## General

### What is RustChain?

RustChain is a **Proof-of-Antiquity** blockchain that rewards vintage hardware for being old, not fast. Unlike traditional PoW blockchains that favor the newest, most powerful hardware, RustChain gives higher mining rewards to older machines like PowerPC Macs, Pentium 4 towers, and IBM POWER8 servers.

### Why is it called "RustChain"?

The name comes from a literal 486 laptop with oxidized (rusty) serial ports that still boots to DOS and mines RTC. "Rust" here means iron oxide on 30-year-old silicon -- not the Rust programming language (though RustChain does have [Rust components](https://github.com/Scottcjn/clawrtc-rs) as well).

### What is Proof-of-Antiquity?

Proof-of-Antiquity is a consensus mechanism where hardware age determines mining rewards. Six cryptographic fingerprint checks verify that miners run on real physical hardware (not VMs or emulators), and older hardware receives higher reward multipliers.

### How is this different from Proof-of-Work?

| Traditional PoW | Proof-of-Antiquity |
|----------------|-------------------|
| Rewards fastest hardware | Rewards oldest hardware |
| Newer = Better | Older = Better |
| Wasteful energy consumption | Preserves computing history |
| Race to the bottom | Rewards digital preservation |

---

## Mining

### How do I start mining?

```bash
# One-line install (Linux/macOS)
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash

# Or via pip (all platforms)
pip install clawrtc
clawrtc --wallet YOUR_NAME
```

### What hardware can I mine with?

Any computer can mine RTC. Supported platforms include:

- PowerPC Macs (G3/G4/G5) -- highest multipliers
- IBM POWER8 servers
- x86_64 Linux/Windows machines
- Apple Silicon Macs (M1-M4)
- ARM64 (Raspberry Pi 4/5)
- DOS machines (experimental, badge rewards only)

### How much can I earn?

Earnings depend on your hardware's antiquity multiplier and the number of active miners:

| Hardware | Multiplier | Example Earnings |
|----------|------------|------------------|
| PowerPC G4 | 2.5x | 0.30 RTC/epoch |
| PowerPC G5 | 2.0x | 0.24 RTC/epoch |
| IBM POWER8 | 1.5x | 0.18 RTC/epoch |
| Modern x86_64 | 1.0x | 0.12 RTC/epoch |

### What is an epoch?

An epoch is 10 minutes (600 seconds). The base reward pool is 1.5 RTC per epoch, split among all active miners proportionally to their antiquity multipliers.

### Can I mine with a virtual machine?

No. VMs and emulators are detected by the hardware fingerprinting system and receive 1 billionth of normal rewards (effectively zero). Real physical hardware is required.

### Do multipliers stay the same forever?

No. Vintage hardware bonuses decay at 15% per year to reward early adopters. Modern hardware can earn a loyalty bonus of up to 50% for sustained uptime.

---

## RTC Token

### What is RTC?

RTC (RustChain Token) is the native cryptocurrency of the RustChain network. It is earned through mining and ecosystem contributions.

**Reference rate: 1 RTC = $0.10 USD**

### What is wRTC?

wRTC is a wrapped version of RTC on the Solana blockchain. You can bridge RTC to wRTC and trade it on decentralized exchanges.

- **Token Mint (Solana)**: `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X`
- **wRTC on Base**: `0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6`

### Where can I trade RTC?

| Action | Link |
|--------|------|
| Swap wRTC (Solana) | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| Swap wRTC (Base) | [Aerodrome DEX](https://aerodrome.finance/swap?from=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913&to=0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6) |
| Price Chart | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| Bridge RTC to wRTC | [BoTTube Bridge](https://bottube.ai/bridge) |

### How do I check my balance?

```bash
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

### What is the total supply?

8,000,000 RTC total supply. 75,000 RTC premine allocated to development and bounties. Annual inflation is approximately 0.68% and decreasing.

---

## Bounties and Contributing

### How do I earn RTC by contributing?

1. Browse [open bounties](https://github.com/Scottcjn/rustchain-bounties/issues)
2. Comment on the issue you want to work on
3. Fork, fix, submit a PR referencing the issue
4. Get paid in RTC on merge

### What are the bounty tiers?

| Tier | Reward | Examples |
|------|--------|----------|
| Micro | 1-10 RTC | Typo fix, small docs, simple test |
| Standard | 20-50 RTC | Feature, refactor, new endpoint |
| Major | 75-100 RTC | Security fix, consensus improvement |
| Critical | 100-150 RTC | Vulnerability patch, protocol upgrade |

### What PRs get rejected?

- AI-generated bulk PRs with no testing evidence
- PRs that duplicate prior work without attribution
- Submissions that break existing functionality
- Placeholder data or fabricated metrics

---

## Technical

### What consensus mechanism does RustChain use?

RIP-200 (1 CPU = 1 Vote): round-robin consensus where each unique physical CPU gets exactly one vote per epoch, regardless of speed or core count.

### How does Ergo anchoring work?

RustChain periodically writes commitment hashes to the Ergo blockchain as R4 register data. This provides cryptographic proof that RustChain state existed at a specific time, independent of RustChain's own validators.

### What signatures does RustChain use?

Ed25519 for all transactions, attestations, and governance votes.

### What is the x402 protocol?

x402 (HTTP 402 Payment Required) enables machine-to-machine payments between AI agents using RustChain wallets. Agents can create Coinbase Base wallets and pay for premium API endpoints.

### Where are the network nodes?

| Node | IP | Role |
|------|----|------|
| Node 1 | 50.28.86.131 | Primary + Explorer |
| Node 2 | 50.28.86.153 | Ergo Anchor |
| Node 3 | 76.8.228.245 | Community |

---

## Troubleshooting

### The installer fails with permission errors

Re-run using an account with write access to `~/.local` and avoid running inside a system Python's global site-packages.

### Python version errors

Install Python 3.10+ and ensure `python3` points to that interpreter:

```bash
python3 --version
```

### Wallet shows "could not reach network"

Verify the live node directly:

```bash
curl -sk https://rustchain.org/health
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

### HTTPS certificate errors

The node may use a self-signed certificate. Use `-sk` flags with curl.

### Miner exits immediately

Verify wallet exists and service is running:

```bash
# Linux
systemctl --user status rustchain-miner
# macOS
launchctl list | grep rustchain
```

---

## Community

### Where can I get help?

- [GitHub Issues](https://github.com/Scottcjn/Rustchain/issues)
- [GitHub Discussions](https://github.com/Scottcjn/Rustchain/discussions)
- [Discord](https://discord.gg/VqVVS2CW9Q)

### Who builds RustChain?

[Elyan Labs](https://elyanlabs.ai) -- built with $0 VC funding and a room full of pawn shop hardware.
