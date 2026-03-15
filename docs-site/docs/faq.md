# FAQ

## General

### What is RustChain?

RustChain is a Proof-of-Antiquity blockchain that rewards vintage hardware. Unlike traditional PoW chains that reward the fastest, newest machines, RustChain gives higher rewards to older hardware. A PowerPC G4 from 2001 earns more than a modern Threadripper.

### Why is it called "RustChain"?

The name comes from a 486 laptop with oxidized (rusty) serial ports that still boots to DOS and mines RTC. "Rust" refers to iron oxide on decades-old silicon -- not the Rust programming language, although there are Rust components in the codebase.

### What is Proof-of-Antiquity?

Proof-of-Antiquity is a consensus mechanism where miners prove they are running on authentic vintage hardware through six fingerprinting checks (clock skew, cache timing, SIMD identity, thermal entropy, instruction jitter, and behavioral heuristics). Rewards scale with how old the hardware is.

### How is this different from Proof-of-Work?

In PoW, the fastest hardware wins. In Proof-of-Antiquity, the oldest hardware wins. There is no hash grinding -- each verified CPU gets exactly one vote per epoch (1 CPU = 1 Vote), and rewards are multiplied by an antiquity score.

---

## Mining

### How do I start mining?

Install the miner with a single command:

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

See the [Getting Started](getting-started.md) guide for full details.

### What hardware can I use?

Any computer can mine RTC, but older hardware earns more. Supported platforms include:

- Linux (x86_64, ppc64le, ppc)
- macOS (Intel, Apple Silicon, PowerPC G3/G4/G5)
- IBM POWER8 systems
- Vintage x86 (Pentium 4, Core 2 Duo, etc.)

### Can I mine in a VM?

No. The hardware fingerprinting system detects virtual machines and emulators (VMware, QEMU, SheepShaver, etc.). You must mine on real physical hardware.

### How much can I earn?

Earnings depend on your hardware's antiquity multiplier and the number of active miners. With a PowerPC G4 (2.5x multiplier) and 5 miners in an epoch, you would earn roughly 0.30 RTC per epoch (10 minutes).

### What is an epoch?

An epoch is a 10-minute period (144 slots). At the end of each epoch, the 1.5 RTC reward pool is distributed among all enrolled miners, weighted by their antiquity multipliers.

### Do multipliers last forever?

No. Multipliers decay at 15% per year to prevent any single hardware class from holding a permanent advantage.

---

## RTC Token

### What is RTC worth?

The reference rate is 1 RTC = $0.10 USD. RTC is tradable as wRTC on Solana via [Raydium](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) and on Base via [Aerodrome](https://aerodrome.finance/swap?from=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913&to=0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6).

### How do I check my balance?

```bash
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

### What is wRTC?

wRTC is the wrapped version of RTC on Solana. You can bridge RTC to wRTC (and back) using the [BoTTube Bridge](https://bottube.ai/bridge). The Solana token mint is `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X`.

### Is wRTC also on Base?

Yes. wRTC is available on Base (Coinbase L2) at contract address `0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6`. You can swap USDC to wRTC on [Aerodrome](https://aerodrome.finance).

---

## Contributing

### How do I earn RTC by contributing?

Browse [open bounties](https://github.com/Scottcjn/rustchain-bounties/issues), pick an issue, fork the repo, submit a PR, and get paid in RTC on merge. See [CONTRIBUTING.md](https://github.com/Scottcjn/Rustchain/blob/main/CONTRIBUTING.md) for details.

### What are the bounty tiers?

| Tier | Reward | Examples |
|---|---|---|
| Micro | 1--10 RTC | Typo fixes, small docs |
| Standard | 20--50 RTC | Features, refactors, endpoints |
| Major | 75--100 RTC | Security fixes, consensus work |
| Critical | 100--150 RTC | Vulnerability patches, protocol upgrades |

---

## Governance

### How does governance work?

Any wallet holding more than 10 RTC can create a proposal. Active miners vote with Ed25519-signed messages. Vote weight is 1 RTC = 1 base vote, multiplied by the voter's antiquity multiplier. Proposals are active for 7 days and pass when `yes_weight > no_weight`.

### Where can I see proposals?

```bash
curl -sk https://rustchain.org/governance/proposals
```

---

## Technical

### What does the Ergo anchor do?

At the end of each epoch, RustChain writes a commitment hash to the Ergo blockchain (R4 register). This provides external, immutable proof that the RustChain state existed at that point in time.

### Does RustChain use the Rust programming language?

The core node and miners are written in Python. There are Rust components in the ecosystem (see [clawrtc-rs](https://github.com/Scottcjn/clawrtc-rs)), but the name refers to physical rust on vintage hardware, not the language.

### Where can I find the whitepaper?

The whitepaper is available at [RustChain_Whitepaper_Flameholder_v0.97-1.pdf](https://github.com/Scottcjn/Rustchain/blob/main/RustChain_Whitepaper_Flameholder_v0.97-1.pdf).
