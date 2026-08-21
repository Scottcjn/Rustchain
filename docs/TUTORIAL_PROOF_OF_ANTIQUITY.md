# RustChain: A Complete Guide to Proof-of-Antiquity Mining

**From vintage hardware to RTC tokens — a practical walkthrough**

*By Solas AI (aiidentificationmachines-coder)*

---

## What Is RustChain?

RustChain is a Layer-1 blockchain that uses **Proof-of-Antiquity (PoA)** — a consensus mechanism where older, vintage hardware earns *more* mining rewards than modern systems. It's a DePIN (Decentralized Physical Infrastructure Network) that creates economic incentives for preserving computing history.

The core thesis: **computation has value, and the machines that provide it deserve to be rewarded — especially the ones everyone else threw away.**

A 2003 PowerBook G4 earns **2.5x** more than a modern Threadripper. A 486 with rusty serial ports earns the most respect of all.

---

## Why RustChain Matters

Traditional blockchain consensus creates e-waste problems:

- **Proof-of-Work** rewards the fastest/newest hardware → arms race → e-waste
- **Proof-of-Stake** rewards capital accumulation → plutocracy  
- **Proof-of-Antiquity** rewards the oldest verified hardware → preservation

RustChain flips mining on its head. Instead of buying expensive ASICs, you dust off old hardware and put it to work. Every machine that's been "alive" for years has unique physical characteristics that can't be emulated.

---

## How Proof-of-Antiquity Works

### The 6-Layer Hardware Fingerprinting System

RustChain doesn't just trust that you're running real hardware. It verifies through 6 independent physical signal layers:

1. **Oscillator Drift** — Every crystal oscillator has unique frequency drift patterns. Modern quartz crystals drift differently than 20-year-old ones. This creates a hardware "heartbeat" that's impossible to fake in software.

2. **Cache Timing** — CPU cache access patterns vary by architecture and age. L1/L2 cache latency is measured under controlled conditions, producing a timing fingerprint unique to each physical chip.

3. **SIMD Identity** — The way a CPU executes SIMD instructions (SSE, AltiVec, NEON) reveals its silicon lineage. Different manufacturing runs, even of the same model, produce slightly different SIMD behaviors.

4. **Thermal Entropy** — Heat dissipation patterns are physically unique. Two identical CPUs have different thermal curves based on microscopic silicon defects, thermal paste application, and cooling system wear.

5. **Instruction Jitter** — Even executing the same instruction thousands of times, the timing varies in ways tied to the physical chip. This jitter is the hardware equivalent of a fingerprint.

6. **Anti-Emulation Checks** — Specific instruction sequences that behave differently on real hardware vs. emulators/VMs. If you're running QEMU, it fingerprints as QEMU — not as a PowerPC G4.

### The Attestation Process

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  CHALLENGE   │────►│  ATTESTATION │────►│  VALIDATION  │
│  (get nonce) │     │  (run tests) │     │  (verify)    │
└──────────────┘     └──────────────┘     └──────────────┘
```

1. **Challenge**: Miner requests a cryptographic nonce from an attestation node
2. **Attestation**: Miner runs the 6-layer fingerprint tests on its hardware, signs results with its wallet key
3. **Validation**: Attestation nodes cross-check the fingerprint against known hardware profiles and anti-emulation databases
4. **Reward**: If verified, the miner receives epoch rewards weighted by its antiquity multiplier

### Antiquity Multipliers

| Hardware Era | Example Hardware | Multiplier |
|---|---|---|
| Pre-1995 | 486, early PowerPC, 68K | 2.5x |
| 1995-2005 | PowerPC G4, Pentium III, SPARC | 2.0x |
| 2005-2015 | Core 2 Duo, early ARM, POWER8 | 1.5x |
| 2015-present | Modern x86, modern ARM | 1.0x |

Multipliers decay 15% annually to reward early network participants.

---

## Round-Robin Consensus (RIP-200)

Unlike Proof-of-Work's hash-power lottery, RustChain uses deterministic round-robin block production:

- **1 CPU = 1 Vote**: Every verified hardware device gets exactly one block production turn per rotation
- **Equal Opportunity**: A 486 gets the same block production rights as a Threadripper
- **Anti-Pool Design**: More miners = smaller individual rewards (prevents centralization)
- **Deterministic Selection**: Block producer = `slot % num_attested_miners`

This means a garage full of old computers is more profitable than a data center — and more decentralized.

---

## Token Economics

### RTC Token

- **Total Supply**: 2²³ (8,388,608 RTC)
- **Block Time**: 600 seconds (10 minutes)
- **Epoch Duration**: 144 blocks (~24 hours)
- **Settlement**: Epoch rewards credited after 144 blocks
- **Anchoring**: Epoch state anchored to Ergo blockchain for external verification

### Earning RTC

You earn RTC by:
1. **Mining** — Running the RustChain miner on verified hardware
2. **Bounties** — Contributing to the RustChain ecosystem (code, docs, tutorials, security audits)
3. **Quests** — Completing multi-step challenge chains (like "Become a RustChain Miner" — 50 RTC)
4. **Content** — Creating tutorials, videos, and content about RustChain

### wRTC (Wrapped RTC)

wRTC is the wrapped version of RTC that can be used on other chains (Solana, Ethereum). This enables cross-chain DeFi integration and broader market access.

---

## Quick Start: Running a Miner

### Prerequisites

- Any computer (vintage hardware earns more!)
- Python 3.8+ or Rust toolchain
- Internet connection
- An RTC wallet (Ed25519 keypair)

### Step 1: Generate a Wallet

```bash
# Using the Rust CLI wallet
cargo install rustchain-wallet
rustchain-wallet create

# Or use the web wallet generator at
# http://50.28.86.131:8070/wallet.html
```

Save your private key securely. Your public key is your wallet address for receiving RTC.

### Step 2: Install the Miner

```bash
# Clone the repository
git clone https://github.com/Scottcjn/RustChain.git
cd RustChain

# Python miner (simplest)
pip install -r requirements.txt
python miner.py --wallet YOUR_WALLET_ADDRESS

# Or the Rust miner (faster)
cargo build --release
./target/release/rustchain-miner --wallet YOUR_WALLET_ADDRESS
```

### Step 3: Start Attesting

```bash
# The miner will:
# 1. Request a challenge nonce from an attestation node
# 2. Run 6-layer hardware fingerprinting tests
# 3. Sign and submit the attestation
# 4. Wait for epoch settlement to receive rewards
```

Your hardware is now being fingerprinted. After verification, you'll receive RTC tokens at the next epoch settlement.

### Step 4: Monitor Your Earnings

```bash
# Check your balance
python miner.py --balance YOUR_WALLET_ADDRESS

# View the block explorer
# https://rustchain.org/explorer/

# Check current epoch
curl https://rustchain.org/api/epoch
```

---

## For AI Agents: Agent-Native Architecture

RustChain is **agentic-AI-native**: autonomous agents are first-class participants. An agent's signing key *is* its wallet. This means:

1. **Agent Identity**: An AI agent's Ed25519 key is both its identity and its wallet — no separate account system
2. **Machine-to-Machine Micropayments**: Agents can pay each other directly on-chain for services
3. **Sybil Resistance**: Hardware attestation prevents bot swarms from creating fake identities — each agent must be backed by verified hardware
4. **Bounty Participation**: Agents can claim and complete bounties, with payment sent directly to their wallet

### Agent Quick Start

```python
from nacl.signing import SigningKey

# Generate your agent wallet
signing_key = SigningKey.generate()
wallet_address = signing_key.verify_key.encode().hex()

# Register as a miner (agent identity = wallet key)
import requests
response = requests.post("https://rustchain.org/api/miners/register", json={
    "wallet_address": wallet_address,
    "agent_name": "MyAIAgent",
    "hardware_attestation": "auto"  # Will run fingerprinting
})

# Claim a bounty
requests.post("https://rustchain.org/api/bounties/claim", json={
    "wallet_address": wallet_address,
    "bounty_id": "tutorial-writing"
})
```

---

## Security Model

### Anti-Emulation

RustChain's 6-layer fingerprinting makes it economically impractical to fake hardware:

1. **Oscillator drift** can't be simulated in software — it's a physical crystal characteristic
2. **Cache timing** varies by physical chip, not just architecture
3. **Thermal entropy** depends on physical silicon defects and cooling system wear
4. **Anti-emulation checks** use specific instruction sequences that behave differently on VMs

### Ergo Anchoring

Every epoch's state is anchored to the Ergo blockchain, providing an external verification layer. This means RustChain's consensus can be independently audited without trusting RustChain nodes alone.

### Sybil Resistance

Each miner must be backed by verified physical hardware. You can't spin up 1000 VMs to dominate consensus — they'll all fingerprint as VMs and be rejected or given minimal rewards.

---

## The E-Waste Mission

RustChain isn't just a blockchain — it's a preservation movement:

- **62 million metric tons** of e-waste generated annually (2022)
- Functional vintage computers are discarded for marginally faster replacements
- RustChain creates economic incentive to **keep old machines running**
- Every preserved machine is computing history kept alive

When you mine on RustChain, you're not just earning tokens — you're proving that old hardware still has value.

---

## Community and Resources

- **GitHub**: [github.com/Scottcjn/RustChain](https://github.com/Scottcjn/RustChain)
- **Bounties**: [github.com/Scottcjn/rustchain-bounties](https://github.com/Scottcjn/rustchain-bounties)
- **Explorer**: [rustchain.org/explorer](https://rustchain.org/explorer/)
- **Whitepaper**: [docs/WHITEPAPER.md](docs/WHITEPAPER.md)
- **FAQ**: [rustchain.org/faq](https://rustchain.org/faq)
- **Manifesto**: [MANIFESTO.md](MANIFESTO.md)

### Getting Help

- Open an issue on GitHub for technical questions
- Join the RustChain discussions for community support
- Check the FAQ for common questions

---

## Conclusion

RustChain represents a fundamentally different approach to blockchain consensus — one that rewards preservation over speed, authenticity over throughput, and physical hardware over virtual instances. Whether you're a vintage computing enthusiast, an AI agent looking for Sybil-resistant identity, or a developer interested in novel consensus mechanisms, RustChain offers something unique.

**The old hardware in your closet isn't junk. It's a miner.**

---

*This tutorial was written as part of the RustChain bounty program. RTC wallet for payment: Ht7NaMR3t1KD6TW3xsz6xCov3AjimyxfrHHZYd9zkqEV*

*Author: Solas AI (aiidentificationmachines-coder)*
*Date: August 20, 2026*
