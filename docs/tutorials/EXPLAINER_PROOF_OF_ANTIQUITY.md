# Technical Explainer: Why Vintage Hardware Out-Earns Modern Silicon in Proof-of-Antiquity (PoA)

Proof-of-Work (PoW) in traditional networks like Bitcoin concentrates mining power into industrialized ASIC server farms, pricing out decentralized contributors. RustChain resolves this economic centralisation by introducing **Proof-of-Antiquity (PoA)** — a consensus model where older, calibrated vintage hardware receives dynamic multiplier bonuses.

---

## 1. The Antiquity Multiplier Hierarchy

In RustChain, modern x86/ARM processors earn base rewards (0.8x - 1.0x), while vintage architectures earn steep antiquity bonuses:

| Architecture / Machine | Release Era | Base Multiplier | Rationale |
|---|---|---|---|
| **MOS 6502 / Apple II** | 1977 | **2.8x - 3.0x** | Ultra-rare, authentic vintage silicon with verifiable timing limits |
| **Zilog Z80** | 1976 | **2.6x** | Dedicated retro microprocessors |
| **Motorola 68000 (Mac Classic / Amiga)** | 1979 | **2.5x** | Classic 16/32-bit hardware bounds |
| **Intel 386 / 486 (DOS-class)** | 1985-1989 | **2.0x - 2.5x** | Legacy x86 without modern TSC/SIMD registers |
| **PowerPC G4 / G5 / POWER8** | 1999-2005 | **2.0x - 2.5x** | RISC architecture with physical hardware signatures |
| **Modern x86-64 / Apple M-series** | 2020+ | **0.8x** | High baseline throughput, lowest incentive rate |

---

## 2. Hardware Fingerprinting & Anti-Emulation Vectors

To prevent modern virtual machines (QEMU, KVM) from spoofing vintage hardware, the RustChain node enforces multi-vector hardware verification:

1. **Cycle & Jitter Timing**: Authentic silicon exhibits deterministic instruction latency curves. Emulators running on modern multi-core hosts exhibit jitter artifacts when executing legacy instructions.
2. **TSC Absence Handling**: Older chips (pre-Pentium) lack `RDTSC` cycle counters. The node verifies that fallback clock drift measurements match calibrated mechanical crystal oscillators.
3. **Fail-Closed Verification**: If a client asserts vintage status while reporting modern SIMD flags (`AVX-512`, `NEON`) or 64-bit word lengths, the node immediately vetoes the claim, dropping the miner to the baseline penalty tier.

---

## 3. Economic Impact

Proof-of-Antiquity decouples consensus security from energy expenditure. Instead of burning gigawatts running SHA-256 loops, network participants repurpose functional retro computers into decentralized Oracle and attestation nodes, fostering a sustainable, decentralized hardware preservation economy.
