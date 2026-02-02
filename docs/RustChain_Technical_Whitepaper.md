# RustChain: A Proof-of-Antiquity Blockchain Protocol

## Technical Whitepaper v1.0

**Authors:** RustChain Community Contributors  
**Date:** February 2026  
**Version:** 1.0  
**Protocol Version:** 2.2.1-RIP200

---

## Abstract

RustChain is a novel blockchain protocol that implements **Proof-of-Antiquity (PoA)**, a consensus mechanism that fundamentally inverts traditional cryptocurrency mining incentives. Rather than rewarding computational power or stake, RustChain rewards the preservation and operation of authentic vintage computing hardware. The protocol employs a sophisticated six-check hardware fingerprinting system to distinguish genuine vintage silicon from emulators and virtual machines, combined with time-decaying antiquity multipliers that incentivize early adoption while preventing permanent advantages. RustChain implements RIP-200, a round-robin "1 CPU = 1 Vote" consensus mechanism that ensures fair participation regardless of hardware speed. The native token RTC (RustChain Token) is distributed through epoch-based rewards anchored to the Ergo blockchain for immutability guarantees. This paper presents the complete technical specification of the RustChain protocol, including consensus mechanisms, hardware verification, token economics, and security analysis.

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Motivation: The E-Waste Problem](#2-motivation-the-e-waste-problem)
3. [System Architecture](#3-system-architecture)
4. [RIP-200: Round-Robin Consensus](#4-rip-200-round-robin-consensus)
5. [Hardware Fingerprinting](#5-hardware-fingerprinting)
6. [Antiquity Multiplier System](#6-antiquity-multiplier-system)
7. [Token Economics](#7-token-economics)
8. [Ergo Blockchain Anchoring](#8-ergo-blockchain-anchoring)
9. [Security Analysis](#9-security-analysis)
10. [Implementation Status](#10-implementation-status)
11. [Future Work](#11-future-work)
12. [Conclusion](#12-conclusion)
13. [References](#13-references)

---

## 1. Introduction

### 1.1 Overview

RustChain represents a paradigm shift in blockchain consensus design. While traditional Proof-of-Work (PoW) systems like Bitcoin reward the fastest, most energy-intensive hardware, and Proof-of-Stake (PoS) systems reward capital accumulation, RustChain's Proof-of-Antiquity rewards something fundamentally different: **the preservation of computing history**.

The core principle is elegantly simple: *older, authentic hardware receives higher mining rewards than modern hardware*. A PowerPC G4 Mac from 2001 earns significantly more RTC tokens per epoch than a modern AMD Ryzen 9. This creates economic incentives to keep vintage computing hardware operational rather than discarding it as electronic waste.

### 1.2 Key Innovations

RustChain introduces several novel concepts to blockchain technology:

1. **Proof-of-Antiquity (PoA)**: A consensus mechanism that validates hardware age and authenticity rather than computational work
2. **Six-Check Hardware Fingerprinting**: A comprehensive anti-emulation system that detects virtual machines and emulated hardware through silicon-level behavioral analysis
3. **Time-Decaying Antiquity Multipliers**: A reward system where vintage hardware bonuses decay over blockchain lifetime, preventing permanent advantages
4. **RIP-200 Round-Robin Consensus**: A "1 CPU = 1 Vote" deterministic block production system that eliminates hash power advantages
5. **Ergo Anchoring**: Periodic commitment of RustChain state to the Ergo blockchain for cryptographic immutability

### 1.3 Network Status

As of this writing, RustChain operates a live mainnet with:

- **9 active miners** across diverse hardware platforms
- **3 attestation nodes** providing consensus validation
- **Current epoch**: 62
- **Version**: 2.2.1-RIP200

The network includes authentic PowerPC G4, G5, and IBM POWER8 systems alongside modern x86_64 and Apple Silicon machines, demonstrating the protocol's cross-architecture capabilities.

---

## 2. Motivation: The E-Waste Problem

### 2.1 Planned Obsolescence in Computing

The technology industry operates on a cycle of planned obsolescence that renders perfectly functional hardware "obsolete" within 3-5 years. Software vendors drop support, operating systems refuse to install, and users are compelled to discard working machines for newer models.

This creates a massive environmental problem:

- **53.6 million metric tons** of e-waste generated globally in 2019
- **Only 17.4%** is formally recycled
- **Toxic materials** (lead, mercury, cadmium) leach into soil and water
- **Rare earth elements** are lost to landfills

### 2.2 Vintage Hardware Has Value

Vintage computing hardware represents significant engineering achievements:

- **PowerPC G4/G5**: Apple's pre-Intel processors with advanced AltiVec SIMD capabilities
- **Motorola 68K**: The processor family that powered the original Macintosh, Amiga, and Atari ST
- **DEC Alpha**: The fastest processors of the 1990s, pioneering 64-bit computing
- **Sun SPARC**: RISC workstation processors that defined enterprise computing
- **IBM POWER**: Server processors with unique vectorized instruction sets

These machines contain irreplaceable institutional knowledge about computing history. When they are discarded, that history is lost.

### 2.3 RustChain's Solution

RustChain creates **economic incentives for digital preservation**:

```
Traditional Mining: Newest/Fastest = Best → Constant hardware churn
RustChain Mining:   Oldest/Authentic = Best → Hardware preservation
```

By making vintage hardware economically productive, RustChain:

1. Reduces e-waste by extending hardware lifespan
2. Creates value for vintage computing collectors
3. Preserves computing history as a running, functional record
4. Provides a model for sustainable technology economics

---

## 3. System Architecture

### 3.1 Network Topology

RustChain employs a hybrid architecture combining elements of permissioned and permissionless systems:

```
┌─────────────────────────────────────────────────────────────────┐
│                     RustChain Network                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐       │
│  │   Miner 1   │     │   Miner 2   │     │   Miner N   │       │
│  │  (G4 Mac)   │     │  (POWER8)   │     │  (Modern)   │       │
│  └──────┬──────┘     └──────┬──────┘     └──────┬──────┘       │
│         │                   │                   │               │
│         └───────────┬───────┴───────┬───────────┘               │
│                     │               │                           │
│              ┌──────▼──────┐ ┌──────▼──────┐                   │
│              │  Primary    │ │  Secondary  │                   │
│              │  Node       │ │  Nodes      │                   │
│              │ 50.28.86.131│ │             │                   │
│              └──────┬──────┘ └──────┬──────┘                   │
│                     │               │                           │
│              ┌──────▼───────────────▼──────┐                   │
│              │     Ergo Anchor Node        │                   │
│              │      50.28.86.153           │                   │
│              └──────────────┬──────────────┘                   │
│                             │                                   │
│                      ┌──────▼──────┐                           │
│                      │    Ergo     │                           │
│                      │  Mainnet    │                           │
│                      └─────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
```

**Figure 1: RustChain Network Topology**

### 3.2 Node Types

#### 3.2.1 Miner Nodes

Miner nodes run on participant hardware and perform the following functions:

- **Hardware Attestation**: Submit periodic proofs of hardware authenticity
- **Epoch Participation**: Vote in round-robin consensus
- **Reward Collection**: Receive RTC proportional to antiquity multiplier

Miners must pass all six hardware fingerprint checks to receive full rewards.

#### 3.2.2 Attestation Nodes (Full Nodes)

Full nodes maintain the complete RustChain state:

- **State Storage**: SQLite database with all blocks, attestations, and balances
- **API Endpoints**: Serve network data via HTTPS REST API
- **Reward Settlement**: Calculate and distribute epoch rewards
- **P2P Gossip**: Propagate attestations and blocks between nodes

#### 3.2.3 Ergo Anchor Node

A specialized node that:

- Monitors RustChain epoch settlements
- Computes commitment hashes of miner data
- Creates Ergo transactions with commitments in R4 register
- Provides cryptographic proof of RustChain state at specific times

### 3.3 Data Flow

```
┌───────────────────────────────────────────────────────────────┐
│                    Miner Attestation Flow                     │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│  1. Miner starts → Collects hardware fingerprint data         │
│                    ↓                                          │
│  2. Runs 6 checks → Clock drift, cache timing, SIMD, etc.     │
│                    ↓                                          │
│  3. Signs attestation → Includes wallet ID, hardware type     │
│                    ↓                                          │
│  4. Submits to node → POST /attest endpoint                   │
│                    ↓                                          │
│  5. Node validates → Checks signature, timestamp, format      │
│                    ↓                                          │
│  6. Stores in DB → miner_attest_recent table                  │
│                    ↓                                          │
│  7. Epoch settles → Rewards distributed by multiplier         │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

**Figure 2: Miner Attestation Flow**

### 3.4 Database Schema

RustChain uses SQLite for state storage with the following core tables:

```sql
-- Miner attestations (recent, with TTL)
CREATE TABLE miner_attest_recent (
    miner TEXT PRIMARY KEY,
    device_arch TEXT,
    device_family TEXT,
    hardware_type TEXT,
    antiquity_multiplier REAL,
    ts_ok INTEGER,
    fingerprint_passed INTEGER DEFAULT 1,
    entropy_score REAL DEFAULT 0.0
);

-- Wallet balances
CREATE TABLE balances (
    miner_id TEXT PRIMARY KEY,
    amount_i64 INTEGER DEFAULT 0
);

-- Transaction ledger
CREATE TABLE ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER,
    epoch INTEGER,
    miner_id TEXT,
    delta_i64 INTEGER,
    reason TEXT
);

-- Epoch settlement state
CREATE TABLE epoch_state (
    epoch INTEGER PRIMARY KEY,
    settled INTEGER DEFAULT 0,
    settled_ts INTEGER
);

-- Ergo anchor records
CREATE TABLE ergo_anchors (
    id INTEGER PRIMARY KEY,
    tx_id TEXT,
    commitment TEXT,
    miner_count INTEGER,
    rc_slot INTEGER,
    created_at INTEGER
);
```

---

## 4. RIP-200: Round-Robin Consensus

### 4.1 Overview

RIP-200 (RustChain Improvement Proposal 200) introduces a fundamental change to consensus: replacing probabilistic lottery systems with deterministic round-robin block production.

**Core Principle**: Each unique hardware device gets exactly **1 vote** per epoch, regardless of computational power.

### 4.2 Why Not Traditional PoW?

Traditional Proof-of-Work creates perverse incentives for RustChain's goals:

| Problem | PoW Behavior | RustChain Goal |
|---------|--------------|----------------|
| Hash Rate | Faster hardware wins | Age-based rewards |
| Pooling | Miners pool resources | Individual participation |
| Energy | Maximum consumption | Minimal energy use |
| Hardware | Rapid obsolescence | Long-term preservation |

### 4.3 Round-Robin Block Production

Block producers are selected deterministically:

```python
def get_round_robin_producer(slot: int, attested_miners: List) -> str:
    """
    Deterministic rotation: slot modulo number of miners
    Each attested CPU gets exactly 1 turn per rotation cycle.
    """
    if not attested_miners:
        return None
    
    producer_index = slot % len(attested_miners)
    return attested_miners[producer_index][0]
```

**Properties**:

1. **Deterministic**: Given slot number and miner list, producer is computable
2. **Fair**: Each miner gets equal block production opportunities
3. **No Lottery**: No randomness, VRF, or hash puzzles
4. **Anti-Pool**: No advantage from combining resources

### 4.4 Epoch Structure

```
┌─────────────────────────────────────────────────────────────┐
│                      Epoch Timeline                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Epoch N                        Epoch N+1                   │
│  ├────────────────────────────┤├────────────────────────── │
│  │                            ││                            │
│  │  144 blocks (slots)        ││  144 blocks (slots)        │
│  │  10 min/block = 24 hours   ││                            │
│  │                            ││                            │
│  │  Block 0: Miner A          ││                            │
│  │  Block 1: Miner B          ││                            │
│  │  Block 2: Miner C          ││                            │
│  │  ...                       ││                            │
│  │  Block 143: Miner A        ││                            │
│  │                            ││                            │
│  │  ──────────────────────    ││                            │
│  │  Settlement: Rewards       ││                            │
│  │  distributed by multiplier ││                            │
│  └────────────────────────────┘└──────────────────────────  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Figure 3: Epoch Timeline**

**Parameters**:

- **Block Time**: 600 seconds (10 minutes)
- **Blocks per Epoch**: 144 (24 hours)
- **Attestation TTL**: 86,400 seconds (24 hours)
- **Epoch Reward Pool**: 1.5 RTC

### 4.5 Attestation Requirements

To participate in an epoch, miners must:

1. **Submit Valid Attestation**: Include hardware fingerprint data
2. **Pass Fingerprint Checks**: All 6 checks must pass for full rewards
3. **Maintain TTL**: Re-attest within 24 hours

Failed fingerprint checks result in drastically reduced rewards:

```python
if fingerprint_ok == 0:
    weight = 0.0  # No rewards for failed fingerprint (VM/emulator)
else:
    weight = get_time_aged_multiplier(device_arch, chain_age_years)
```

---

## 5. Hardware Fingerprinting

### 5.1 Overview

The hardware fingerprinting system is RustChain's primary defense against emulation and virtual machines. It exploits the fact that **real silicon has unique physical characteristics** that emulators cannot perfectly replicate.

### 5.2 The Six Checks

```
┌─────────────────────────────────────────────────────────────┐
│                    6 Hardware Checks                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Clock-Skew & Oscillator Drift                           │
│     └─ Silicon aging creates unique timing patterns         │
│                                                             │
│  2. Cache Timing Fingerprint                                │
│     └─ L1/L2/L3 latency ratios reveal cache hierarchy       │
│                                                             │
│  3. SIMD Unit Identity                                      │
│     └─ AltiVec/SSE/AVX/NEON instruction availability        │
│                                                             │
│  4. Thermal Drift Entropy                                   │
│     └─ Heat-induced timing variations are unique            │
│                                                             │
│  5. Instruction Path Jitter                                 │
│     └─ Microarchitecture-specific execution variance        │
│                                                             │
│  6. Anti-Emulation Behavioral Checks                        │
│     └─ Detect VM indicators in system files/environment     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Figure 4: Hardware Fingerprint Checks**

### 5.3 Check 1: Clock-Skew & Oscillator Drift

**Purpose**: Detect synthetic timing by measuring real silicon oscillator behavior.

**Method**:

```python
def check_clock_drift(samples: int = 200) -> Tuple[bool, Dict]:
    intervals = []
    
    for i in range(samples):
        start = time.perf_counter_ns()
        # Perform reference workload
        for _ in range(5000):
            hashlib.sha256(data).digest()
        elapsed = time.perf_counter_ns() - start
        intervals.append(elapsed)
    
    # Calculate coefficient of variation
    cv = stdev / mean
    
    # Real hardware has measurable drift
    if cv < 0.0001:  # Too perfect = synthetic
        return False, {"fail_reason": "synthetic_timing"}
```

**Why It Works**: Real crystal oscillators have manufacturing variations and age-related drift. Emulators typically provide perfectly synthetic time, revealing themselves through impossibly consistent timing.

### 5.4 Check 2: Cache Timing Fingerprint

**Purpose**: Verify cache hierarchy matches claimed architecture.

**Method**:

```python
def check_cache_timing(iterations: int = 100) -> Tuple[bool, Dict]:
    # Measure access times for different buffer sizes
    l1_size = 8 * 1024      # L1 cache size
    l2_size = 128 * 1024    # L2 cache size  
    l3_size = 4 * 1024 * 1024  # L3 cache size
    
    l1_times = [measure_access_time(l1_size) for _ in range(iterations)]
    l2_times = [measure_access_time(l2_size) for _ in range(iterations)]
    l3_times = [measure_access_time(l3_size) for _ in range(iterations)]
    
    # Cache hierarchy should show distinct latency steps
    l2_l1_ratio = l2_avg / l1_avg
    l3_l2_ratio = l3_avg / l2_avg
    
    if l2_l1_ratio < 1.01 and l3_l2_ratio < 1.01:
        return False, {"fail_reason": "no_cache_hierarchy"}
```

**Why It Works**: Real CPUs have distinct cache levels with measurable latency differences. A PowerPC G4 has different L1/L2/L3 ratios than an x86 processor. Emulators often fail to accurately simulate cache behavior.

### 5.5 Check 3: SIMD Unit Identity

**Purpose**: Verify presence of architecture-specific SIMD instructions.

**Detected Features**:

| Architecture | SIMD Unit | Detection |
|--------------|-----------|-----------|
| PowerPC | AltiVec | `/proc/cpuinfo` flags |
| x86/x86_64 | SSE/AVX | CPU flags |
| ARM | NEON | `/proc/cpuinfo` features |
| Apple Silicon | NEON | `sysctl` output |

**Why It Works**: A PowerPC G4 claiming to have AltiVec should actually have AltiVec registers and instructions available. Emulators may not perfectly expose all SIMD capabilities.

### 5.6 Check 4: Thermal Drift Entropy

**Purpose**: Detect thermal throttling behavior unique to real silicon.

**Method**:

1. Measure "cold" performance (idle CPU)
2. Run intensive workload to heat CPU
3. Measure "hot" performance (heated CPU)
4. Compare variance in both states

**Why It Works**: Real CPUs experience thermal throttling that creates measurable timing variations. The specific pattern of thermal drift is hardware-dependent and difficult to emulate accurately.

### 5.7 Check 5: Instruction Path Jitter

**Purpose**: Measure microarchitecture-specific execution variance.

**Method**:

```python
def check_instruction_jitter(samples: int = 100) -> Tuple[bool, Dict]:
    # Measure different instruction types
    int_times = [measure_int_ops() for _ in range(samples)]
    fp_times = [measure_fp_ops() for _ in range(samples)]
    branch_times = [measure_branch_ops() for _ in range(samples)]
    
    # Real hardware shows variance
    if int_stdev == 0 and fp_stdev == 0 and branch_stdev == 0:
        return False, {"fail_reason": "no_jitter"}
```

**Why It Works**: Real CPUs have branch predictors, out-of-order execution, and variable latency instructions. The "jitter" pattern is unique to each microarchitecture.

### 5.8 Check 6: Anti-Emulation Behavioral Checks

**Purpose**: Direct detection of virtual machine indicators.

**Detection Vectors**:

```python
vm_paths = [
    "/sys/class/dmi/id/product_name",  # VM product names
    "/sys/class/dmi/id/sys_vendor",     # VM vendor strings
    "/proc/scsi/scsi",                  # Virtual SCSI devices
]

vm_strings = ["vmware", "virtualbox", "kvm", "qemu", 
              "xen", "hyperv", "parallels"]

# Environment variables indicating containers
for key in ["KUBERNETES", "DOCKER", "VIRTUAL", "container"]:
    if key in os.environ:
        vm_indicators.append(f"ENV:{key}")

# CPU flags indicating hypervisor
if "hypervisor" in cpuinfo:
    vm_indicators.append("cpuinfo:hypervisor")
```

**Penalty**: Detected VMs receive **1 billionth** of normal rewards:

```
Real G4 Mac:    2.5× multiplier  = 0.30 RTC/epoch
Emulated G4:    0.0000000025×    = 0.0000000003 RTC/epoch
```

### 5.9 Validation Flow

All six checks must pass for full reward eligibility:

```python
def validate_all_checks(include_rom_check: bool = True) -> Tuple[bool, Dict]:
    checks = [
        ("clock_drift", check_clock_drift),
        ("cache_timing", check_cache_timing),
        ("simd_identity", check_simd_identity),
        ("thermal_drift", check_thermal_drift),
        ("instruction_jitter", check_instruction_jitter),
        ("anti_emulation", check_anti_emulation),
    ]
    
    all_passed = True
    for key, func in checks:
        passed, data = func()
        if not passed:
            all_passed = False
    
    return all_passed, results
```

---

## 6. Antiquity Multiplier System

### 6.1 Overview

The antiquity multiplier system assigns higher reward weights to older hardware architectures. This creates economic incentives for preserving vintage computing equipment.

### 6.2 Base Multipliers

#### 6.2.1 PowerPC Architectures (Highest Multipliers)

| Architecture | Era | Base Multiplier | Example Hardware |
|--------------|-----|-----------------|------------------|
| PowerPC G4 | 1999-2005 | **2.5×** | Power Mac G4, PowerBook G4 |
| PowerPC G5 | 2003-2006 | **2.0×** | Power Mac G5, iMac G5 |
| PowerPC G3 | 1997-2003 | **1.8×** | iMac G3, PowerBook G3 |
| IBM POWER8 | 2014 | **1.5×** | IBM Power Systems S824 |

#### 6.2.2 Vintage x86 Architectures

| Architecture | Era | Base Multiplier |
|--------------|-----|-----------------|
| Intel 386 | 1985-1994 | 3.0× |
| Intel 486 | 1989-1997 | 2.8× |
| Pentium (P5) | 1993-1999 | 2.5× |
| Pentium III | 1999-2003 | 2.0× |
| Pentium 4 | 2000-2008 | 1.5× |
| Core 2 Duo | 2006-2011 | 1.3× |

#### 6.2.3 Exotic Architectures

| Architecture | Era | Base Multiplier |
|--------------|-----|-----------------|
| Motorola 68000 | 1979-1990 | 3.0× |
| DEC Alpha 21064 | 1992-1995 | 2.7× |
| SPARC v7 | 1987-1992 | 2.9× |
| MIPS R2000 | 1985-1988 | 3.0× |
| HP PA-RISC 1.0 | 1986-1990 | 2.9× |

#### 6.2.4 Modern Architectures (Baseline)

| Architecture | Era | Base Multiplier |
|--------------|-----|-----------------|
| Apple M1 | 2020-2021 | 1.2× |
| Apple M2 | 2022-2023 | 1.15× |
| Apple M3 | 2023-2024 | 1.1× |
| Apple M4 | 2024-2025 | 1.05× |
| Modern x86_64 | Current | 0.8× |
| ARM/aarch64 | Current | 0.0005× |

### 6.3 Time-Decay Formula

Vintage hardware bonuses decay over blockchain lifetime to prevent permanent advantages:

```python
DECAY_RATE_PER_YEAR = 0.15  # 15% decay per year

def get_time_aged_multiplier(device_arch: str, chain_age_years: float) -> float:
    base_multiplier = ANTIQUITY_MULTIPLIERS.get(device_arch.lower(), 1.0)
    
    # Modern hardware doesn't decay (stays at 1.0)
    if base_multiplier <= 1.0:
        return 1.0
    
    # Calculate decayed bonus
    vintage_bonus = base_multiplier - 1.0  # e.g., G4: 2.5 - 1.0 = 1.5
    decay_factor = 1 - (DECAY_RATE_PER_YEAR * chain_age_years)
    aged_bonus = max(0, vintage_bonus * decay_factor)
    
    return 1.0 + aged_bonus
```

### 6.4 Decay Timeline

| Chain Age | G4 (2.5× base) | G5 (2.0× base) | Modern (1.0×) |
|-----------|----------------|----------------|---------------|
| Year 0 | 2.50× | 2.00× | 1.00× |
| Year 2 | 2.05× | 1.70× | 1.00× |
| Year 5 | 1.375× | 1.25× | 1.00× |
| Year 10 | 1.00× | 1.00× | 1.00× |
| Year 17 | 1.00× | 1.00× | 1.00× |

**Interpretation**: Early adopters with vintage hardware receive the highest rewards. As the chain ages, the vintage advantage gradually equalizes until all hardware earns similar rewards.

### 6.5 Loyalty Bonus (Modern Hardware)

Modern hardware (<5 years old) can earn a **loyalty bonus** for consistent uptime:

```python
if hardware_age <= 5 and loyalty_years > 0:
    loyalty_bonus = min(0.5, loyalty_years * 0.15)  # Cap at +50%
    final_multiplier = min(1.5, final_multiplier + loyalty_bonus)
```

| Uptime | Modern x86 Multiplier |
|--------|----------------------|
| 0 years | 1.0× |
| 1 year | 1.15× |
| 3 years | 1.45× |
| 5+ years | 1.5× (capped) |

### 6.6 Server Hardware Bonus

Enterprise-class CPUs receive a **+10% bonus**:

```python
if is_server:  # Xeon, EPYC, Opteron
    final_multiplier *= 1.1
```

**Example**: Intel Xeon E5-1650 v2 (Ivy Bridge, 2012)
- Base: 1.1× (Ivy Bridge era)
- Server bonus: ×1.1
- Final: **1.21×**

---

## 7. Token Economics

### 7.1 RTC Token Overview

**RTC (RustChain Token)** is the native cryptocurrency of the RustChain network.

| Property | Value |
|----------|-------|
| Token Symbol | RTC |
| Smallest Unit | µRTC (micro-RTC) |
| Unit Conversion | 1 RTC = 100,000,000 µRTC |
| Epoch Reward | 1.5 RTC |
| Block Time | 600 seconds |
| Blocks per Epoch | 144 |

### 7.2 Reward Distribution

Each epoch distributes 1.5 RTC among all attested miners, weighted by their antiquity multipliers:

```python
def calculate_epoch_rewards_time_aged(db_path, epoch, total_reward_urtc, current_slot):
    # Get all attested miners for this epoch
    epoch_miners = get_epoch_miners(db_path, epoch)
    
    # Calculate weighted shares
    total_weight = sum(get_time_aged_multiplier(m.arch, chain_age) 
                       for m in epoch_miners)
    
    rewards = {}
    for miner in epoch_miners:
        weight = get_time_aged_multiplier(miner.arch, chain_age)
        share = (weight / total_weight) * total_reward_urtc
        rewards[miner.id] = share
    
    return rewards
```

### 7.3 Example Distribution

**Scenario**: 5 miners in epoch with 1.5 RTC pool

| Miner | Hardware | Multiplier | Share | RTC |
|-------|----------|------------|-------|-----|
| A | G4 Mac | 2.5× | 38.5% | 0.577 |
| B | G5 Mac | 2.0× | 30.8% | 0.462 |
| C | Modern PC | 0.8× | 12.3% | 0.185 |
| D | Modern PC | 0.8× | 12.3% | 0.185 |
| E | Apple M1 | 1.2× | 18.5% | 0.092 |
| **Total** | | **6.5×** | **100%** | **1.5** |

### 7.4 Supply Model

RustChain does not have a hard cap but has predictable issuance:

- **Daily Issuance**: 1.5 RTC × 1 epoch/day = 1.5 RTC/day
- **Annual Issuance**: ~547.5 RTC/year
- **10-Year Issuance**: ~5,475 RTC

The slow issuance rate, combined with the difficulty of acquiring and operating vintage hardware, creates natural scarcity.

### 7.5 Fee Model

Currently, RustChain operates with **zero transaction fees**. The network is designed for participation rewards rather than transaction throughput.

Future development may introduce optional fee mechanisms for:
- Priority attestation processing
- Cross-chain bridge operations
- Smart contract execution (if implemented)

---

## 8. Ergo Blockchain Anchoring

### 8.1 Purpose

RustChain anchors its state to the **Ergo blockchain** to achieve:

1. **Immutability**: Commitments on Ergo cannot be altered
2. **Timestamping**: Cryptographic proof of when state existed
3. **Security Bootstrap**: Inherit Ergo's PoW security guarantees
4. **Auditability**: Anyone can verify RustChain history on Ergo

### 8.2 Anchoring Mechanism

```
┌─────────────────────────────────────────────────────────────┐
│                    Ergo Anchoring Flow                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  RustChain Epoch N                                          │
│       │                                                     │
│       ▼                                                     │
│  [Collect Miner Data]                                       │
│       │                                                     │
│       ▼                                                     │
│  [Compute BLAKE2b Commitment]                               │
│  commitment = blake2b(json(miners), digest_size=32)         │
│       │                                                     │
│       ▼                                                     │
│  [Create Ergo Transaction]                                  │
│  - Input: Anchor wallet UTXO                                │
│  - Output 1: Anchor box (0.001 ERG) with R4 = commitment    │
│  - Output 2: Change box                                     │
│       │                                                     │
│       ▼                                                     │
│  [Broadcast to Ergo Network]                                │
│       │                                                     │
│       ▼                                                     │
│  [Record TX ID in RustChain DB]                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Figure 5: Ergo Anchoring Flow**

### 8.3 Implementation

```python
class ErgoMinerAnchor:
    ANCHOR_VALUE = 1000000  # 0.001 ERG minimum box size
    
    def compute_commitment(self, miners):
        """Create deterministic commitment hash"""
        data = json.dumps(miners, sort_keys=True).encode()
        return blake2b(data, digest_size=32).hexdigest()
    
    def create_anchor_tx(self, miners):
        commitment = self.compute_commitment(miners)
        
        unsigned_tx = {
            "inputs": [{"boxId": input_box["boxId"]}],
            "outputs": [{
                "value": ANCHOR_VALUE,
                "ergoTree": input_box["ergoTree"],
                "additionalRegisters": {
                    "R4": "0e20" + commitment  # 32-byte commitment
                }
            }]
        }
        
        # Sign and broadcast
        signed = self.session.post("/wallet/transaction/sign", 
                                   json={"tx": unsigned_tx})
        return self.session.post("/transactions", json=signed.json())
```

### 8.4 Verification

Anyone can verify RustChain anchors:

1. Query Ergo blockchain for anchor transactions
2. Extract R4 register (commitment hash)
3. Reconstruct expected commitment from RustChain miner data
4. Compare hashes

If hashes match, the RustChain state existed at the Ergo block timestamp.

### 8.5 Anchor Frequency

Anchors are created:
- **Periodically**: After epoch settlements
- **On Demand**: Manual triggering for important events
- **Cost**: ~0.001 ERG per anchor (zero fee transactions)

---

## 9. Security Analysis

### 9.1 Threat Model

RustChain faces several potential attack vectors:

| Attack | Description | Mitigation |
|--------|-------------|------------|
| Emulation | Fake vintage hardware with VMs | 6-check fingerprinting |
| Sybil | Multiple identities per hardware | Hardware binding |
| Time Warp | Manipulate timestamps | Ergo anchoring |
| Eclipse | Isolate nodes from network | P2P gossip protocol |
| 51% | Control majority of "CPUs" | Hardware scarcity |

### 9.2 Emulation Resistance

The six hardware fingerprint checks create multiple independent detection layers:

**Defense in Depth**:
```
Emulator must fake:
✗ Crystal oscillator drift patterns
✗ Multi-level cache latency hierarchy  
✗ Architecture-specific SIMD instructions
✗ Thermal throttling behavior
✗ Microarchitecture execution jitter
✗ Absence of VM indicators

Cost of perfect emulation > Cost of real hardware
```

**Economic Disincentive**: Even if an emulator passes all checks, the cost of maintaining such sophisticated emulation likely exceeds the cost of acquiring actual vintage hardware.

### 9.3 Sybil Resistance

Hardware binding prevents multiple wallets per physical device:

```python
# Each hardware fingerprint maps to exactly one wallet
fingerprint_hash = hash(clock_drift + cache_pattern + simd_id + ...)
if fingerprint_hash in bound_wallets:
    reject("Hardware already registered")
```

### 9.4 Time Manipulation

Ergo anchoring provides tamper-evident timestamping:

- RustChain state committed to Ergo at known heights
- Ergo's PoW makes history rewriting prohibitively expensive
- Independent verification possible by any party

### 9.5 Network Attacks

**P2P Gossip Protocol**:
- Attestations propagated between multiple nodes
- No single point of failure
- Nodes can verify attestations independently

**Eclipse Attack Mitigation**:
- Multiple geographically distributed nodes
- Public API endpoints for independent verification
- Ergo anchors provide out-of-band verification

### 9.6 Known Limitations

1. **Initial Hardware Acquisition**: Must obtain real vintage hardware
2. **Physical Security**: Hardware can be stolen/destroyed
3. **Network Dependency**: Requires internet connectivity
4. **Trusted Nodes**: Current implementation has trusted attestation nodes

### 9.7 Red Team Findings

Internal security testing identified:

1. **Timing Granularity**: Very slow emulators might pass clock drift checks
   - *Mitigation*: Added thermal drift and jitter checks as additional vectors

2. **SIMD Spoofing**: Software could fake SIMD availability
   - *Mitigation*: Actual SIMD instruction execution timing measured

3. **VM Indicator Evasion**: Custom VMs might lack standard indicators
   - *Mitigation*: Multiple independent check categories

---

## 10. Implementation Status

### 10.1 Current Deployment

**Mainnet Statistics** (as of February 2026):

| Metric | Value |
|--------|-------|
| Version | 2.2.1-RIP200 |
| Active Miners | 9 |
| Attestation Nodes | 3 |
| Current Epoch | 62 |
| Network Uptime | ~28 hours since last restart |

### 10.2 Active Miners

| Miner ID | Hardware | Multiplier |
|----------|----------|------------|
| eafc6f14... | PowerPC G4 (Vintage) | 2.5× |
| power8-s824-sophia | PowerPC POWER8 | 2.0× |
| g5-selena-179 | PowerPC G5 (Vintage) | 2.0× |
| modern-sophia-Pow-* | x86-64 (Modern) | 0.8× |
| apple_silicon_c318... | Apple M2 | 0.8× |

### 10.3 Node Infrastructure

| Node | IP Address | Role |
|------|------------|------|
| Primary | 50.28.86.131 | Main node + Explorer |
| Secondary | 50.28.86.153 | Ergo Anchor |
| Community | 76.8.228.245 | External validation |

### 10.4 Repository Structure

```
Rustchain/
├── node/
│   ├── rustchain_v2_integrated_v2.2.1_rip200.py  # Full node
│   ├── rip_200_round_robin_1cpu1vote.py          # Consensus
│   ├── fingerprint_checks.py                      # 6 checks
│   ├── rewards_implementation_rip200.py           # Rewards
│   ├── ergo_miner_anchor.py                       # Ergo bridge
│   └── rustchain_p2p_gossip.py                   # P2P layer
├── miners/
│   └── rustchain_universal_miner.py              # Cross-platform
├── cpu_architecture_detection.py                  # Arch detection
├── cpu_vintage_architectures.py                   # Vintage CPUs
└── docs/
    └── RustChain_Whitepaper.pdf                  # This document
```

---

## 11. Future Work

### 11.1 Short-Term (6-12 months)

1. **DEX Listing**: List RTC on decentralized exchanges
   - Target: Spectrum DEX (Ergo ecosystem)
   - Enable RTC/ERG trading pairs

2. **Mobile Wallet**: Lightweight wallet application
   - Balance checking
   - Transaction history
   - Miner status monitoring

3. **Additional Hardware Support**:
   - SPARC Solaris systems
   - SGI IRIX workstations
   - Amiga PPC accelerator cards

### 11.2 Medium-Term (1-2 years)

1. **Cross-Chain Bridge**:
   - RTC ↔ ERG atomic swaps
   - Bridge to Ethereum L2s

2. **Enhanced Fingerprinting**:
   - ROM fingerprint database for retro platforms
   - Machine learning anomaly detection

3. **Decentralized Node Network**:
   - Remove trusted attestation nodes
   - Full peer-to-peer validation

### 11.3 Long-Term (2-5 years)

1. **PSE/POWER8 Inference**:
   - Run AI inference on POWER8 vec_perm instructions
   - "Non-bijunctive collapse" entropy source
   - Reference: github.com/Scottcjn/ram-coffers

2. **Smart Contract Layer**:
   - ErgoScript-compatible contracts
   - NFT badges for vintage hardware achievements

3. **Federated Vintage Networks**:
   - Connect isolated vintage networks
   - "Museum mode" for non-networked systems

---

## 12. Conclusion

RustChain demonstrates that blockchain consensus can serve purposes beyond pure financial speculation. By rewarding the preservation of vintage computing hardware, the protocol creates:

1. **Environmental Value**: Reduces e-waste through extended hardware lifespan
2. **Historical Value**: Preserves computing history as functional systems
3. **Technical Innovation**: Novel consensus mechanism based on hardware authenticity
4. **Community Value**: Brings together vintage computing enthusiasts

The Proof-of-Antiquity mechanism, combined with sophisticated hardware fingerprinting and Ergo blockchain anchoring, creates a secure and novel approach to distributed consensus. While challenges remain—particularly around scaling and decentralization—the live mainnet demonstrates the viability of the concept.

RustChain invites participation from:
- Vintage computing collectors
- Blockchain researchers
- Environmental technologists
- Anyone with old hardware in their closet

*"Your vintage hardware earns rewards. Make mining meaningful again."*

---

## 13. References

1. **RustChain GitHub Repository**  
   https://github.com/Scottcjn/Rustchain

2. **RustChain Bounties**  
   https://github.com/Scottcjn/rustchain-bounties

3. **Live Explorer**  
   https://50.28.86.131/explorer

4. **Ergo Platform**  
   https://ergoplatform.org

5. **Intel CPU Microarchitectures**  
   https://en.wikipedia.org/wiki/List_of_Intel_CPU_microarchitectures

6. **AMD CPU Microarchitectures**  
   https://en.wikipedia.org/wiki/List_of_AMD_CPU_microarchitectures

7. **PowerPC Architecture**  
   https://en.wikipedia.org/wiki/PowerPC

8. **Global E-Waste Monitor 2020**  
   https://globalewaste.org

---

## Appendix A: API Reference

### Health Check
```bash
curl -sk https://50.28.86.131/health
# Response: {"ok":true,"version":"2.2.1-rip200","uptime_s":100484}
```

### Active Miners
```bash
curl -sk https://50.28.86.131/api/miners
# Response: [{"miner":"...","hardware_type":"PowerPC G4",...}]
```

### Current Epoch
```bash
curl -sk https://50.28.86.131/epoch
# Response: {"epoch":62,"slot":8930,"epoch_pot":1.5}
```

### Wallet Balance
```bash
curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET"
# Response: {"miner_id":"...","amount_rtc":0.81969698}
```

---

## Appendix B: Installation

### One-Line Install
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install.sh | bash
```

### Manual Install
```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain
pip install -r requirements.txt
python3 rustchain_universal_miner.py --wallet YOUR_WALLET_NAME
```

### Supported Platforms
- Ubuntu 20.04+ (x86_64, ppc64le)
- macOS 12+ (Intel, Apple Silicon, PowerPC)
- Mac OS X Tiger/Leopard (PowerPC G4/G5)
- Windows 10/11 (x86_64)
- DOS (8086/286/386) - Experimental

---

*Document Version: 1.0*  
*Last Updated: February 2026*  
*RustChain Protocol Version: 2.2.1-RIP200*
