<div align="center">

# 🧱 RustChain: Proof-of-Antiquity Blockchain

[![CI](https://github.com/Scottcjn/Rustchain/actions/workflows/ci.yml/badge.svg)](https://github.com/Scottcjn/Rustchain/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![PowerPC](https://img.shields.io/badge/PowerPC-G3%2FG4%2FG5-orange)](https://github.com/Scottcjn/Rustchain)
[![Blockchain](https://img.shields.io/badge/Consensus-Proof--of--Antiquity-green)](https://github.com/Scottcjn/Rustchain)
[![Python](https://img.shields.io/badge/Python-3.x-yellow)](https://python.org)
[![Network](https://img.shields.io/badge/Nodes-3%20Active-brightgreen)](https://rustchain.org/explorer)
[![As seen on BoTTube](https://bottube.ai/badge/seen-on-bottube.svg)](https://bottube.ai)

**The first blockchain that rewards vintage hardware for being old, not fast.**

*Your PowerPC G4 earns more than a modern Threadripper. That's the point.*

[Website](https://rustchain.org) • [Live Explorer](https://rustchain.org/explorer) • [Swap wRTC](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) • [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) • [wRTC Quickstart](docs/wrtc.md) • [wRTC Tutorial](docs/WRTC_ONBOARDING_TUTORIAL.md) • [Grokipedia Ref](https://grokipedia.com/search?q=RustChain) • [Whitepaper](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf) • [Quick Start](#-quick-start) • [How It Works](#-how-proof-of-antiquity-works)

</div>

---

## 🪙 wRTC on Solana

RustChain Token (RTC) is now available as **wRTC** on Solana via the BoTTube Bridge:

| Resource | Link |
|----------|------|
| **Swap wRTC** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **Price Chart** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **Bridge RTC ↔ wRTC** | [BoTTube Bridge](https://bottube.ai/bridge) |
| **Quickstart Guide** | [wRTC Quickstart (Buy, Bridge, Safety)](docs/wrtc.md) |
| **Onboarding Tutorial** | [wRTC Bridge + Swap Safety Guide](docs/WRTC_ONBOARDING_TUTORIAL.md) |
| **External Reference** | [Grokipedia Search: RustChain](https://grokipedia.com/search?q=RustChain) |
| **Token Mint** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |

---


---

## Agent Wallets + x402 Payments

RustChain agents can now own **Coinbase Base wallets** and make machine-to-machine payments using the **x402 protocol** (HTTP 402 Payment Required):

| Resource | Link |
|----------|------|
| **Agent Wallets Docs** | [rustchain.org/wallets.html](https://rustchain.org/wallets.html) |
| **wRTC on Base** | [`0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6`](https://basescan.org/address/0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6) |
| **Swap USDC to wRTC** | [Aerodrome DEX](https://aerodrome.finance/swap?from=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913&to=0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6) |
| **Base Bridge** | [bottube.ai/bridge/base](https://bottube.ai/bridge/base) |

```bash
# Create a Coinbase wallet
pip install clawrtc[coinbase]
clawrtc wallet coinbase create

# Check swap info
clawrtc wallet coinbase swap-info

# Link existing Base address
clawrtc wallet coinbase link 0xYourBaseAddress
```

**x402 Premium API endpoints** are live (currently free while proving the flow):
- `GET /api/premium/videos` - Bulk video export (BoTTube)
- `GET /api/premium/analytics/<agent>` - Deep agent analytics (BoTTube)
- `GET /api/premium/reputation` - Full reputation export (Beacon Atlas)
- `GET /wallet/swap-info` - USDC/wRTC swap guidance (RustChain)

## 📄 Academic Publications

| Paper | DOI | Topic |
|-------|-----|-------|
| **RustChain: One CPU, One Vote** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623592.svg)](https://doi.org/10.5281/zenodo.18623592) | Proof of Antiquity consensus, hardware fingerprinting |
| **Non-Bijunctive Permutation Collapse** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623920.svg)](https://doi.org/10.5281/zenodo.18623920) | AltiVec vec_perm for LLM attention (27-96x advantage) |
| **PSE Hardware Entropy** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623922.svg)](https://doi.org/10.5281/zenodo.18623922) | POWER8 mftb entropy for behavioral divergence |
| **Neuromorphic Prompt Translation** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623594.svg)](https://doi.org/10.5281/zenodo.18623594) | Emotional prompting for 20% video diffusion gains |
| **RAM Coffers** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18321905.svg)](https://doi.org/10.5281/zenodo.18321905) | NUMA-distributed weight banking for LLM inference |

---

## 🎯 What Makes RustChain Different

| Traditional PoW | Proof-of-Antiquity |
|----------------|-------------------|
| Rewards fastest hardware | Rewards oldest hardware |
| Newer = Better | Older = Better |
| Wasteful energy consumption | Preserves computing history |
| Race to the bottom | Rewards digital preservation |

**Core Principle**: Authentic vintage hardware that has survived decades deserves recognition. RustChain flips mining upside-down.

## ⚡ Quick Start

### One-Line Install (Recommended)
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

The installer:
- ✅ Auto-detects your platform (Linux/macOS, x86_64/ARM/PowerPC)
- ✅ Creates an isolated Python virtualenv (no system pollution)
- ✅ Downloads the correct miner for your hardware
- ✅ Sets up auto-start on boot (systemd/launchd)
- ✅ Provides easy uninstall

### Installation with Options

**Install with a specific wallet:**
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet my-miner-wallet
```

**Uninstall:**
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --uninstall
```

### Supported Platforms
- ✅ Ubuntu 20.04+, Debian 11+, Fedora 38+ (x86_64, ppc64le)
- ✅ macOS 12+ (Intel, Apple Silicon, PowerPC)
- ✅ IBM POWER8 systems

### After Installation

**Check your wallet balance:**
```bash
# Note: Using -sk flags because the node may use a self-signed SSL certificate
curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

**List active miners:**
```bash
curl -sk https://50.28.86.131/api/miners
```

**Check node health:**
```bash
curl -sk https://50.28.86.131/health
```

**Get current epoch:**
```bash
curl -sk https://50.28.86.131/epoch
```

**Manage the miner service:**

*Linux (systemd):*
```bash
systemctl --user status rustchain-miner    # Check status
systemctl --user stop rustchain-miner      # Stop mining
systemctl --user start rustchain-miner     # Start mining
journalctl --user -u rustchain-miner -f    # View logs
```

*macOS (launchd):*
```bash
launchctl list | grep rustchain            # Check status
launchctl stop com.rustchain.miner         # Stop mining
launchctl start com.rustchain.miner        # Start mining
tail -f ~/.rustchain/miner.log             # View logs
```

### Manual Install
```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain
pip install -r requirements.txt
python3 rustchain_universal_miner.py --wallet YOUR_WALLET_NAME
```

## 💰 Bounty Board

Earn **RTC** by contributing to the RustChain ecosystem!

| Bounty | Reward | Link |
|--------|--------|------|
| **First Real Contribution** | 10 RTC | [#48](https://github.com/Scottcjn/Rustchain/issues/48) |
| **Network Status Page** | 25 RTC | [#161](https://github.com/Scottcjn/Rustchain/issues/161) |
| **AI Agent Hunter** | 200 RTC | [Agent Bounty #34](https://github.com/Scottcjn/rustchain-bounties/issues/34) |

---

## 💰 Antiquity Multipliers

Your hardware's age determines your mining rewards:

| Hardware | Era | Multiplier | Example Earnings |
|----------|-----|------------|------------------|
| **PowerPC G4** | 1999-2005 | **2.5×** | 0.30 RTC/epoch |
| **PowerPC G5** | 2003-2006 | **2.0×** | 0.24 RTC/epoch |
| **PowerPC G3** | 1997-2003 | **1.8×** | 0.21 RTC/epoch |
| **IBM POWER8** | 2014 | **1.5×** | 0.18 RTC/epoch |
| **Pentium 4** | 2000-2008 | **1.5×** | 0.18 RTC/epoch |
| **Core 2 Duo** | 2006-2011 | **1.3×** | 0.16 RTC/epoch |
| **Apple Silicon** | 2020+ | **1.2×** | 0.14 RTC/epoch |
| **Modern x86_64** | Current | **1.0×** | 0.12 RTC/epoch |

*Multipliers decay over time (15%/year) to prevent permanent advantage.*

## 🔧 How Proof-of-Antiquity Works

### 1. Hardware Fingerprinting (RIP-PoA)

Every miner must prove their hardware is real, not emulated:

```
┌─────────────────────────────────────────────────────────────┐
│                   6 Hardware Checks                         │
├─────────────────────────────────────────────────────────────┤
│ 1. Clock-Skew & Oscillator Drift   ← Silicon aging pattern  │
│ 2. Cache Timing Fingerprint        ← L1/L2/L3 latency tone  │
│ 3. SIMD Unit Identity              ← AltiVec/SSE/NEON bias  │
│ 4. Thermal Drift Entropy           ← Heat curves are unique │
│ 5. Instruction Path Jitter         ← Microarch jitter map   │
│ 6. Anti-Emulation Checks           ← Detect VMs/emulators   │
└─────────────────────────────────────────────────────────────┘
```

**Why it matters**: A SheepShaver VM pretending to be a G4 Mac will fail these checks. Real vintage silicon has unique aging patterns that can't be faked.

### 2. 1 CPU = 1 Vote (RIP-200)

Unlike PoW where hash power = votes, RustChain uses **round-robin consensus**:

- Each unique hardware device gets exactly 1 vote per epoch
- Rewards split equally among all voters, then multiplied by antiquity
- No advantage from running multiple threads or faster CPUs

### 3. Epoch-Based Rewards

```
Epoch Duration: 10 minutes (600 seconds)
Base Reward Pool: 1.5 RTC per epoch
Distribution: Equal split × antiquity multiplier
```

**Example with 5 miners:**
```
G4 Mac (2.5×):     0.30 RTC  ████████████████████
G5 Mac (2.0×):     0.24 RTC  ████████████████
Modern PC (1.0×):  0.12 RTC  ████████
Modern PC (1.0×):  0.12 RTC  ████████
Modern PC (1.0×):  0.12 RTC  ████████
                   ─────────
Total:             0.90 RTC (+ 0.60 RTC returned to pool)
```

## 🌐 Network Architecture

### Live Nodes (3 Active)

| Node | Location | Role | Status |
|------|----------|------|--------|
| **Node 1** | 50.28.86.131 | Primary + Explorer | ✅ Active |
| **Node 2** | 50.28.86.153 | Ergo Anchor | ✅ Active |
| **Node 3** | 76.8.228.245 | External (Community) | ✅ Active |

### Ergo Blockchain Anchoring

RustChain periodically anchors to the Ergo blockchain for immutability:

```
RustChain Epoch → Commitment Hash → Ergo Transaction (R4 register)
```

This provides cryptographic proof that RustChain state existed at a specific time.

## 📊 API Endpoints

```bash
# Check network health
curl -sk https://50.28.86.131/health

# Get current epoch
curl -sk https://50.28.86.131/epoch

# List active miners
curl -sk https://50.28.86.131/api/miners

# Check wallet balance
curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET"

# Block explorer (web browser)
open https://rustchain.org/explorer
```

## 🖥️ Supported Platforms

| Platform | Architecture | Status | Notes |
|----------|--------------|--------|-------|
| **Mac OS X Tiger** | PowerPC G4/G5 | ✅ Full Support | Python 2.5 compatible miner |
| **Mac OS X Leopard** | PowerPC G4/G5 | ✅ Full Support | Recommended for vintage Macs |
| **Ubuntu Linux** | ppc64le/POWER8 | ✅ Full Support | Best performance |
| **Ubuntu Linux** | x86_64 | ✅ Full Support | Standard miner |
| **macOS Sonoma** | Apple Silicon | ✅ Full Support | M1/M2/M3 chips |
| **Windows 10/11** | x86_64 | ✅ Full Support | Python 3.8+ |
| **DOS** | 8086/286/386 | 🔧 Experimental | Badge rewards only |

## 🏅 NFT Badge System

Earn commemorative badges for mining milestones:

| Badge | Requirement | Rarity |
|-------|-------------|--------|
| 🔥 **Bondi G3 Flamekeeper** | Mine on PowerPC G3 | Rare |
| ⚡ **QuickBasic Listener** | Mine from DOS machine | Legendary |
| 🛠️ **DOS WiFi Alchemist** | Network DOS machine | Mythic |
| 🏛️ **Pantheon Pioneer** | First 100 miners | Limited |

## 🔒 Security Model

### Anti-VM Detection
VMs are detected and receive **1 billionth** of normal rewards:
```
Real G4 Mac:    2.5× multiplier  = 0.30 RTC/epoch
Emulated G4:    0.0000000025×    = 0.0000000003 RTC/epoch
```

### Hardware Binding
Each hardware fingerprint is bound to one wallet. Prevents:
- Multiple wallets on same hardware
- Hardware spoofing
- Sybil attacks

## 📁 Repository Structure

```
Rustchain/
├── rustchain_universal_miner.py    # Main miner (all platforms)
├── rustchain_v2_integrated.py      # Full node implementation
├── fingerprint_checks.py           # Hardware verification
├── install.sh                      # One-line installer
├── docs/
│   ├── RustChain_Whitepaper_*.pdf  # Technical whitepaper
│   └── chain_architecture.md       # Architecture docs
├── tools/
│   └── validator_core.py           # Block validation
└── nfts/                           # Badge definitions
```

## ✅ Beacon Certified Open Source (BCOS)

RustChain accepts AI-assisted PRs, but we require *evidence* and *review* so maintainers don't drown in low-quality code generation.

Read the draft spec:
- `docs/BEACON_CERTIFIED_OPEN_SOURCE.md`

## 🔗 Related Projects & Links

| Resource | Link |
|---------|------|
| **Website** | [rustchain.org](https://rustchain.org) |
| **Block Explorer** | [rustchain.org/explorer](https://rustchain.org/explorer) |
| **Swap wRTC (Raydium)** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **Price Chart** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **Bridge RTC ↔ wRTC** | [BoTTube Bridge](https://bottube.ai/bridge) |
| **wRTC Token Mint** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |
| **BoTTube** | [bottube.ai](https://bottube.ai) - AI video platform |
| **Moltbook** | [moltbook.com](https://moltbook.com) - AI social network |
| [nvidia-power8-patches](https://github.com/Scottcjn/nvidia-power8-patches) | NVIDIA drivers for POWER8 |
| [llama-cpp-power8](https://github.com/Scottcjn/llama-cpp-power8) | LLM inference on POWER8 |
| [ppc-compilers](https://github.com/Scottcjn/ppc-compilers) | Modern compilers for vintage Macs |

## 📝 Articles

- [Proof of Antiquity: A Blockchain That Rewards Vintage Hardware](https://dev.to/scottcjn/proof-of-antiquity-a-blockchain-that-rewards-vintage-hardware-4ii3) - Dev.to
- [I Run LLMs on a 768GB IBM POWER8 Server](https://dev.to/scottcjn/i-run-llms-on-a-768gb-ibm-power8-server-and-its-faster-than-you-think-1o) - Dev.to

## 🙏 Attribution

**A year of development, real vintage hardware, electricity bills, and a dedicated lab went into this.**

If you use RustChain:
- ⭐ **Star this repo** - Helps others find it
- 📝 **Credit in your project** - Keep the attribution
- 🔗 **Link back** - Share the love

```
RustChain - Proof of Antiquity by Scott (Scottcjn)
https://github.com/Scottcjn/Rustchain
```

## 📜 License

MIT License - Free to use, but please keep the copyright notice and attribution.

---

<div align="center">

**Made with ⚡ by [Elyan Labs](https://elyanlabs.ai)**

*"Your vintage hardware earns rewards. Make mining meaningful again."*

**DOS boxes, PowerPC G4s, Win95 machines - they all have value. RustChain proves it.**

</div>
