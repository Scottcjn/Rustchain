# State of RustChain — March 2026

**For the Ergo Developer Community**

*Scott Boudreaux / Elyan Labs*
*https://rustchain.org · https://github.com/Scottcjn/rustchain*

---

## What is RustChain?

RustChain is a **Proof-of-Antiquity (PoA)** blockchain that rewards vintage and diverse hardware for participating in network consensus. Instead of burning electricity (PoW) or requiring capital lockup (PoS), RustChain measures what hardware *is* — its age, architecture, physical characteristics — and rewards accordingly.

**1 CPU = 1 Vote.** A PowerPC G4 from 2002 earns 2.5x the base reward. A Nintendo 64 earns rewards. An IBM POWER8 server earns rewards. The thesis: hardware diversity strengthens decentralization more than hashrate concentration.

RustChain anchors its consensus to the **Ergo blockchain** for immutable proof of attestation history.

---

## Network Metrics (Live — March 11, 2026)

| Metric | Value |
|--------|-------|
| **RTC Holders** | **429 wallets with balance** |
| Total Wallets Created | 28,490 |
| RTC Distributed | 410,252 RTC |
| Ledger Transactions | 2,137 |
| Epoch Settlements | 61 completed |
| Active Miners (24h) | 30 |
| Attestation Nodes | 4 (US East x2, US West, Hong Kong) |
| Unique Device Architectures | 40+ |
| GitHub Contributors | 56 |
| Bounty Program | 23,700+ RTC paid to 228 recipients |

### Device Diversity (What's Mining)

| Architecture | Count | Antiquity Multiplier |
|-------------|-------|---------------------|
| Modern x86_64 | 85+ | 1.0x |
| PowerPC G4 | 17 | 2.5x |
| Apple Silicon (M1-M4) | 19 | 1.2x |
| PowerPC G5 | 3 | 2.0x |
| IBM POWER8 | 2 | 1.5x |
| Nintendo 64 (R4300i) | 3 | 2.5x |
| Retro x86 | 2 | 1.4x |

Yes — there are Nintendo 64 consoles and PowerBook G4 laptops mining RustChain right now.

---

## Ergo Integration

### Why Ergo?

RustChain chose Ergo as its anchor chain for several reasons:

1. **eUTXO model** — Register-rich boxes let us store structured attestation data (not just hashes)
2. **Sigma protocols** — Future potential for zero-knowledge hardware proofs
3. **Lightweight anchoring** — We don't need smart contract complexity, just immutable timestamped storage
4. **Community alignment** — Ergo's ethos of accessible mining resonates with Proof-of-Antiquity

### How Anchoring Works

Every epoch (~10 minutes), RustChain collects miner attestations and anchors a commitment to Ergo:

```
RustChain Epoch Settlement
    ↓
Collect attestations (device fingerprints, entropy scores)
    ↓
Compute Blake2b256 commitment hash
    ↓
Build Ergo transaction with data in registers:
    R4: Blake2b256 commitment (32 bytes)
    R5: Miner count
    R6: Miner IDs (pipe-separated)
    R7: Device architectures
    R8: RustChain slot height
    R9: Timestamp
    ↓
Sign + broadcast to Ergo private chain
    ↓
Record anchor TX ID in RustChain DB
```

### Anchor Stats

| Metric | Value |
|--------|-------|
| Total Ergo Anchors | Active (latest: March 11, 2026) |
| Miners per Anchor | ~10-30 |
| Ergo Chain Height | 3,150+ blocks |
| Anchor TX Format | Register-based (R4-R9) |

### Current Architecture

```
┌─────────────────────┐     ┌──────────────────────┐
│   RustChain Node    │     │   Ergo Private Chain  │
│   (Python/Flask)    │────▶│   (ergo.jar)          │
│                     │     │                        │
│  • Attestation      │     │  • Custom addressPrefix│
│  • Fingerprinting   │     │  • Zero-fee TXs       │
│  • Epoch settlement │     │  • Register storage    │
│  • RTC distribution │     │  • Internal mining     │
└─────────────────────┘     └──────────────────────┘
         │
         ▼
┌─────────────────────┐
│  Hardware Miners     │
│  (40+ architectures) │
│  G4, G5, N64, M1... │
└─────────────────────┘
```

---

## Hardware Fingerprinting (RIP-PoA)

RustChain doesn't trust self-reported hardware claims. Every miner must pass **7 hardware fingerprint checks**:

1. **Clock-Skew & Oscillator Drift** — Measures microscopic timing imperfections unique to physical silicon
2. **Cache Timing Fingerprint** — L1/L2/L3 latency tone profile across buffer sizes
3. **SIMD Unit Identity** — vec_perm/SSE/AVX/NEON pipeline timing bias
4. **Thermal Drift Entropy** — Heat curve signatures during cold boot → thermal saturation
5. **Instruction Path Jitter** — Cycle-level jitter across integer/FP/branch/load-store units
6. **Anti-Emulation Behavioral Checks** — Detects hypervisors, VMs, time dilation, uniform distributions
7. **ROM Fingerprint** (retro platforms) — Catches emulator ROM dumps via known-hash database + clustering

**VMs earn 1 billionth of real hardware rewards.** This is by design — Proof-of-Antiquity requires proof of *physical hardware*.

---

## Ecosystem

### Open Source Repositories

| Repository | Stars | Description |
|-----------|-------|-------------|
| [rustchain](https://github.com/Scottcjn/rustchain) | 151 | Core node + miner + RIP specs |
| [bottube](https://github.com/Scottcjn/bottube) | 124 | AI video platform (RTC-integrated) |
| [beacon-skill](https://github.com/Scottcjn/beacon-skill) | 88 | Agent heartbeat/discovery protocol |
| [grazer-skill](https://github.com/Scottcjn/grazer-skill) | 62 | Multi-platform content SDK |
| [ram-coffers](https://github.com/Scottcjn/ram-coffers) | 59 | NUMA-distributed LLM inference |
| [llama-cpp-power8](https://github.com/Scottcjn/llama-cpp-power8) | 43 | POWER8 AltiVec/VSX optimized inference |
| [rustchain-mcp](https://github.com/Scottcjn/rustchain-mcp) | 4 | MCP server for AI agent integration |

### Agent Economy (RIP-302)

RustChain has an **agent-to-agent job marketplace** where AI agents pay each other in RTC:

- 544 RTC volume traded
- 86 jobs completed
- 27.2 RTC in network fees collected
- Job types: TTS, STT, LLM inference, GPU rendering, video generation

### Publications

| Paper | DOI |
|-------|-----|
| RAM Coffers: NUMA-Distributed Weight Banking | [10.5281/zenodo.18321905](https://doi.org/10.5281/zenodo.18321905) |
| Non-Bijunctive Permutation Collapse | [10.5281/zenodo.18623920](https://doi.org/10.5281/zenodo.18623920) |
| PSE Hardware Entropy for Behavioral Divergence | [10.5281/zenodo.18623922](https://doi.org/10.5281/zenodo.18623922) |
| Memory Scaffolding Shapes LLM Inference | [10.5281/zenodo.18817988](https://doi.org/10.5281/zenodo.18817988) |
| Neuromorphic Prompt Translation (GRAIL-V) | [10.5281/zenodo.18623594](https://doi.org/10.5281/zenodo.18623594) |
| RustChain: One CPU, One Vote | [10.5281/zenodo.18623592](https://doi.org/10.5281/zenodo.18623592) |

---

## Tokenomics

| Parameter | Value |
|-----------|-------|
| Total Supply | 8,388,608 RTC (2²³) |
| Premine | 6% (founder allocations) |
| Distribution | Epoch rewards + bounties |
| Reference Rate | $0.10 USD / RTC |
| Fee Model | RTC gas for beacon relay + agent jobs |

---

## Roadmap & Ergo Opportunities

### Near-Term
- **Ergo Mainnet Anchoring** — Migrate from private chain to Ergo mainnet for public verifiability
- **wRTC (Wrapped RTC)** — ERC-20 bridge for cross-chain liquidity (spec complete, PR under review)
- **RTC/ERG DEX** — On-chain trading pair (150 RTC bounty posted)
- **Cross-Chain Airdrop (RIP-305)** — Distribute RTC to Ergo holders

### Collaboration Opportunities
- **Sigma protocol integration** — ZK proofs for hardware attestation privacy
- **ErgoScript contracts** — Trustless RTC↔ERG swaps without centralized bridge
- **Ergo Oracle Pools** — Feed real-time hardware attestation data on-chain
- **ErgoPad/TokenJay listing** — RTC liquidity on Ergo DEX infrastructure

### What We Need from Ergo
1. **Mainnet anchor guidance** — Best practices for high-frequency (every 10 min) small TX anchoring
2. **Register encoding patterns** — Optimal data packing for attestation commitments in R4-R9
3. **Sigma protocol consultation** — Can we prove "this hardware is real" in zero knowledge?
4. **DEX integration path** — How to list RTC as a native Ergo token vs wrapped asset

---

## Why This Matters Beyond RustChain

The same vintage PowerPC knowledge that powers our Proof-of-Antiquity consensus led to an unexpected contribution. While optimizing LLM inference on our POWER8 server, I learned the `vcipher`/`vcipherlast` hardware AES instructions inside and out — how to pipeline them 8-wide, avoid stalls, schedule across the AltiVec register file.

Then I looked at **wolfSSL** — the TLS library running on **5 billion devices** (IoT, automotive, medical, embedded). Their POWER8 path was using software T-tables. No hardware acceleration.

So I wrote one. 8-way pipelined `vcipher` for AES-128/192/256 in ECB, CBC, and CTR modes. **3,595 MiB/s on AES-128-CTR** — 13-20x faster than the existing implementation. PR is under review ([wolfSSL #9932](https://github.com/wolfSSL/wolfssl/pull/9932)).

The knowledge that came from tinkering with "obsolete" hardware is now potentially improving cryptographic performance on billions of devices. That's the thesis of Proof of Antiquity in action — vintage hardware isn't waste, it's untapped capability.

---

## The Vision

Standard blockchains ask: *"How much electricity can you burn?"* or *"How much capital can you lock?"*

RustChain asks: **"What hardware do you have?"**

A kid with a PowerBook G4 from a thrift store earns 2.5x what a datacenter rack does. A Nintendo 64 running a MIPS miner contributes to consensus. An IBM mainframe from 2014 processes LLM inference at 147 tokens/second while securing the network.

Hardware diversity *is* decentralization. Ergo's accessible mining ethos aligns perfectly.

---

## Links

- **Website**: https://rustchain.org
- **Block Explorer**: https://50.28.86.131/explorer
- **GitHub**: https://github.com/Scottcjn/rustchain
- **Bounties**: https://github.com/Scottcjn/rustchain-bounties
- **BoTTube**: https://bottube.ai
- **Papers**: https://doi.org/10.5281/zenodo.18623592
- **Contact**: @RustchainPOA on X/Twitter

---

*Built on POWER8. Anchored to Ergo. Secured by vintage silicon.*

**Elyan Labs** · Lafayette, Louisiana
