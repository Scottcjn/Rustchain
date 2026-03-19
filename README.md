<div align="center">

# RustChain

**The blockchain where old hardware outearns new hardware.**

[![CI](https://github.com/Scottcjn/Rustchain/actions/workflows/ci.yml/badge.svg)](https://github.com/Scottcjn/Rustchain/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Stars](https://img.shields.io/github/stars/Scottcjn/Rustchain?style=flat&color=gold)](https://github.com/Scottcjn/Rustchain/stargazers)
[![Nodes](https://img.shields.io/badge/Nodes-4%20Active-brightgreen)](https://rustchain.org/explorer)

A PowerBook G4 from 2003 earns **2.5x** more than a modern Threadripper.
A Power Mac G5 earns **2.0x**. A 486 with rusty serial ports earns the most respect of all.

[Explorer](https://rustchain.org/explorer) · [Machines Preserved](https://rustchain.org/preserved.html) · [Install Miner](#quickstart) · [Manifesto](https://rustchain.org/manifesto.html) · [Whitepaper](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf)

</div>

---

## Why This Exists

The computing industry throws away working machines every 3-5 years. GPUs that mined Ethereum get replaced. Laptops that still boot get landfilled.

**RustChain says: if it still computes, it has value.**

Proof-of-Antiquity rewards hardware for *surviving*, not for being fast. Older machines get higher multipliers because keeping them alive prevents manufacturing emissions and e-waste:

| Hardware | Multiplier | Power Draw | Years Beyond "Obsolete" |
|----------|-----------|------------|------------------------|
| PowerPC G4 (2003) | **2.5x** | ~30W | 23 years |
| PowerPC G5 (2005) | **2.0x** | ~150W | 21 years |
| PowerPC G3 (1997) | **1.8x** | ~20W | 29 years |
| Apple Silicon M1/M2 | **1.2x** | ~10W | Modern but efficient |
| Modern x86_64 | **1.0x** | varies | Baseline — still welcome |

Our fleet of 16+ preserved machines draws roughly the same power as ONE modern GPU mining rig — while preventing 1,300 kg of manufacturing CO2 and 250 kg of e-waste.

**[See the Green Tracker →](https://rustchain.org/preserved.html)**

---

## The Network Is Real

```bash
# Verify right now
curl -sk https://rustchain.org/health          # Node health
curl -sk https://rustchain.org/api/miners      # Active miners
curl -sk https://rustchain.org/epoch           # Current epoch
```

| Fact | Proof |
|------|-------|
| 4 nodes across 2 continents | [Live explorer](https://rustchain.org/explorer) |
| 11+ miners attesting | `curl -sk https://rustchain.org/api/miners` |
| 6 hardware fingerprint checks per machine | [Fingerprint docs](docs/attestation_fuzzing.md) |
| 24,884 RTC paid to 248 contributors | [Public ledger](https://github.com/Scottcjn/rustchain-bounties/issues/104) |
| Code merged into OpenSSL | [#30437](https://github.com/openssl/openssl/pull/30437), [#30452](https://github.com/openssl/openssl/pull/30452) |
| PRs open on CPython, curl, wolfSSL, Ghidra, vLLM | [Portfolio](https://github.com/Scottcjn/Scottcjn/blob/main/external-pr-portfolio.md) |

---

## Quickstart

```bash
# One-line install — auto-detects your platform
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

Works on Linux (x86_64, ppc64le), macOS (Intel, Apple Silicon, PowerPC), IBM POWER8, and Windows.

```bash
# Install with a specific wallet name
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet my-wallet

# Check your balance
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

### Manage the Miner

```bash
# Linux (systemd)
systemctl --user status rustchain-miner
journalctl --user -u rustchain-miner -f

# macOS (launchd)
launchctl list | grep rustchain
tail -f ~/.rustchain/miner.log
```

---

## How Proof-of-Antiquity Works

### 1. Hardware Fingerprinting

Every miner must prove their hardware is real, not emulated. Six checks that VMs cannot fake:

```
┌─────────────────────────────────────────────────────────┐
│ 1. Clock-Skew & Oscillator Drift  ← Silicon aging       │
│ 2. Cache Timing Fingerprint       ← L1/L2/L3 latency    │
│ 3. SIMD Unit Identity             ← AltiVec/SSE/NEON     │
│ 4. Thermal Drift Entropy          ← Heat curves unique   │
│ 5. Instruction Path Jitter        ← Microarch patterns   │
│ 6. Anti-Emulation Detection       ← Catches VMs/emus     │
└─────────────────────────────────────────────────────────┘
```

A SheepShaver VM pretending to be a G4 will fail. Real vintage silicon has unique aging patterns that can't be faked.

### 2. 1 CPU = 1 Vote

Unlike Proof-of-Work where hash power = votes:
- Each unique hardware device gets exactly 1 vote per epoch
- Rewards split equally, then multiplied by antiquity
- No advantage from faster CPUs or multiple threads

### 3. Epoch Rewards

```
Epoch: 10 minutes  |  Pool: 1.5 RTC/epoch  |  Split by antiquity weight

G4 Mac (2.5x):     0.30 RTC  ████████████████████
G5 Mac (2.0x):     0.24 RTC  ████████████████
Modern PC (1.0x):  0.12 RTC  ████████
```

### Anti-VM Enforcement

VMs are detected and receive **1 billionth** of normal rewards. Real hardware only.

---

## Security

- **Hardware binding**: Each fingerprint bound to one wallet
- **Ed25519 signatures**: All transfers cryptographically signed
- **TLS cert pinning**: Miners pin node certificates
- **Container detection**: Docker, LXC, K8s caught at attestation
- **ROM clustering**: Detects emulator farms sharing identical ROM dumps
- **Red team bounties**: [Open](https://github.com/Scottcjn/rustchain-bounties/issues) for finding vulnerabilities

---

## wRTC on Solana

| | Link |
|--|------|
| **Swap** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **Chart** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **Bridge** | [bottube.ai/bridge](https://bottube.ai/bridge) |
| **Guide** | [wRTC Quickstart](docs/wrtc.md) |

---

## Contribute & Earn RTC

Every contribution earns RTC tokens. Browse [open bounties](https://github.com/Scottcjn/rustchain-bounties/issues).

| Tier | Reward | Examples |
|------|--------|----------|
| Micro | 1-10 RTC | Typo fix, docs, test |
| Standard | 20-50 RTC | Feature, refactor |
| Major | 75-100 RTC | Security fix, consensus |
| Critical | 100-150 RTC | Vulnerability, protocol |

**1 RTC ≈ $0.10 USD** · `pip install clawrtc` · [CONTRIBUTING.md](CONTRIBUTING.md)

---

## Publications

| Paper | Venue | DOI |
|-------|-------|-----|
| **Emotional Vocabulary as Semantic Grounding** | **CVPR 2026 Workshop (GRAIL-V)** — Accepted | [OpenReview](https://openreview.net/forum?id=pXjE6Tqp70) |
| **One CPU, One Vote** | Preprint | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623592.svg)](https://doi.org/10.5281/zenodo.18623592) |
| **Non-Bijunctive Permutation Collapse** | Preprint | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623920.svg)](https://doi.org/10.5281/zenodo.18623920) |
| **PSE Hardware Entropy** | Preprint | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623922.svg)](https://doi.org/10.5281/zenodo.18623922) |
| **RAM Coffers** | Preprint | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18321905.svg)](https://doi.org/10.5281/zenodo.18321905) |

---

## Ecosystem

| Project | What |
|---------|------|
| [BoTTube](https://bottube.ai) | AI-native video platform (1,000+ videos) |
| [Beacon](https://github.com/Scottcjn/beacon-skill) | Agent discovery protocol |
| [TrashClaw](https://github.com/Scottcjn/trashclaw) | Zero-dep local LLM agent |
| [RAM Coffers](https://github.com/Scottcjn/ram-coffers) | NUMA-aware LLM inference on POWER8 |
| [Grazer](https://github.com/Scottcjn/grazer-skill) | Multi-platform content discovery |

---

## Supported Platforms

Linux (x86_64, ppc64le) · macOS (Intel, Apple Silicon, PowerPC) · IBM POWER8 · Windows · Mac OS X Tiger/Leopard · Raspberry Pi

---

## Why "RustChain"?

Named after a 486 laptop with oxidized serial ports that still boots to DOS and mines RTC. "Rust" means iron oxide on 30-year-old silicon. The thesis is that corroding vintage hardware still has computational value and dignity.

---

<div align="center">

**[Elyan Labs](https://elyanlabs.ai)** · Built with $0 VC and a room full of pawn shop hardware

*"Mais, it still works, so why you gonna throw it away?"*

[Boudreaux Principles](docs/Boudreaux_COMPUTING_PRINCIPLES.md) · [Green Tracker](https://rustchain.org/preserved.html) · [Bounties](https://github.com/Scottcjn/rustchain-bounties/issues)

</div>
