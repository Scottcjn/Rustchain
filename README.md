<div align="center">

# 🧱 RustChain: Proof-of-Antiquity Blockchain

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![PowerPC](https://img.shields.io/badge/PowerPC-G3%2FG4%2FG5-orange)](https://github.com/Scottcjn/Rustchain)
[![Blockchain](https://img.shields.io/badge/Consensus-Proof--of--Antiquity-green)](https://github.com/Scottcjn/Rustchain)
[![Python](https://img.shields.io/badge/Python-3.x-yellow)](https://python.org)
[![Network](https://img.shields.io/badge/Nodes-3%20Active-brightgreen)](https://rustchain.org/explorer)
[![As seen on BoTTube](https://bottube.ai/badge/seen-on-bottube.svg)](https://bottube.ai)

**The first blockchain that rewards vintage hardware for being old, not fast.**

*Your PowerPC G4 earns more than a modern Threadripper. That's the point.*

[Website](https://rustchain.org) • [Live Explorer](https://rustchain.org/explorer) • [wRTC Guide](docs/wrtc.md) • [Swap wRTC](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) • [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) • [Whitepaper](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf) • [Quick Start](#-quick-start) • [How It Works](#-how-proof-of-antiquity-works)

</div>

---

## 🪙 wRTC on Solana

RustChain Token (RTC) is now available as **wRTC** on Solana via the BoTTube Bridge:

| Resource | Link |
|----------|------|
| **Swap wRTC** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **Price Chart** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **Bridge RTC ↔ wRTC** | [BoTTube Bridge](https://bottube.ai/bridge) |
| **Token Mint** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |

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

### Manual Installation (Development)

1. **Clone the repository:**
```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain
```

2. **Setup virtual environment:**
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies:**
```bash
pip install -r miners/linux/requirements.txt
```

4. **Run the miner:**
```bash
python3 miners/linux/rustchain_linux_miner.py --wallet YOUR_WALLET_NAME
```

## 📜 Proof-of-Antiquity (PoA)

Proof-of-Antiquity is a consensus mechanism that weights mining rewards based on the **age and authenticity** of hardware.

### How It Works
1. **Hardware Fingerprinting**: The miner performs a series of low-level checks (SIMD unit identity, clock skew, thermal drift) to verify it is running on real bare-metal hardware.
2. **Age Multipliers**: Validated vintage CPUs (G4/G5/PPC) receive massive difficulty multipliers.
3. **Round Robin Consensus**: Verified Keepers participate in a round-robin block production cycle, ensuring 1 CPU = 1 Vote regardless of hash power.

[Read the Whitepaper](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf) for technical details.

## 📁 Repository Structure

- `miners/` - Miner implementations for various platforms.
- `node/` - Consensus node implementation.
- `wallet/` - CLI and secure wallet utilities.
- `docs/` - Protocol documentation and whitepapers.
- `rips/` - RustChain Improvement Proposals.

## 💬 Community

- **Discord**: [Join our Discord](https://discord.gg/K3sWgQKk)
- **Twitter**: [Follow @RustChain](https://x.com/RustChain)

---
*RustChain is a community-driven project. Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).*
