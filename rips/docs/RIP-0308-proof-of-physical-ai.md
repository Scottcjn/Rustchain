# RIP-0308: Proof of Physical AI (PPA)

[![DOI](https://zenodo.org/badge/doi/10.5281/zenodo.19442753.svg)](https://doi.org/10.5281/zenodo.19442753)

```yaml
rip: 0308
title: Proof of Physical AI (PPA)
author: Scott Boudreaux (Elyan Labs)
status: Draft
type: Standards Track
category: Core
created: 2026-04-06
requires: RIP-0001, RIP-0007, RIP-0200, RIP-0201
doi: 10.5281/zenodo.19442753
```

> **Citation:** Boudreaux, S. (2026). *RIP-0308: Proof of Physical AI (PPA) — Hardware Fingerprinting for Verifiable Compute Provenance*. Elyan Labs. https://doi.org/10.5281/zenodo.19442753

---

## Abstract

This RIP defines **Proof of Physical AI (PPA)** as a protocol category in which hardware fingerprinting cryptographically proves that real, unique physical silicon performed real computational work. PPA is to AI compute what Proof of Work is to Bitcoin, but instead of proving energy expenditure, it proves **physical presence and hardware authenticity**.

The term "Proof of Physical AI" is coined here for the first time. This document constitutes the original specification and prior art. No prior usage of this term exists in academic literature, industry whitepapers, or blockchain documentation as of April 6, 2026.

PPA combines seven independent fingerprint channels, server-side verification, fleet detection, and anti-emulation checks into a unified attestation framework. A system satisfying PPA guarantees that a specific, identifiable physical machine -- not a virtual machine, emulator, or spoofed environment -- performed the attested work.

## Motivation

### The Provenance Gap in AI Compute

AI inference is migrating to massive GPU farms operated by a small number of hyperscalers. When a user submits a prompt to a cloud API, they receive tokens back. They have no way to verify:

- Which physical machine processed the request
- Whether the hardware was real or virtualized
- Whether the operator ran the model they claimed to run
- Whether the silicon was shared, throttled, or degraded

This opacity is acceptable for casual use. It is unacceptable for applications that require **verifiable compute provenance**: medical AI, autonomous vehicle inference, financial modeling, legal document analysis, and any context where "which machine did this" has regulatory, liability, or safety implications.

### DePIN Verifies Infrastructure, Not Hardware

Decentralized Physical Infrastructure Networks (DePIN) represent the closest prior art. Projects in this category verify that real-world infrastructure exists and operates:

| Project | What It Proves | What It Does NOT Prove |
|---------|---------------|----------------------|
| Filecoin | Storage capacity exists | Which specific drive holds the data |
| Helium | Radio coverage exists | Which specific radio transmitted the signal |
| Render | GPU compute was performed | Which specific GPU performed it |
| Akash | Compute resources are available | Hardware identity or uniqueness |
| io.net | GPU clusters are online | Whether GPUs are physical or pass-through |

Every DePIN project listed above proves **that** work happened. None proves **which specific physical machine** did it. The gap between "work was done" and "this machine did it" is the provenance gap.

PPA fills this gap.

### The Agent Economy Requires Trustless Hardware Verification

The emerging agent economy (see RIP-0302) involves AI agents autonomously selecting, purchasing, and consuming compute resources from other agents or decentralized marketplaces. An agent paying another agent for inference needs guarantees that:

1. The compute provider is running real hardware (not a proxy to a centralized API)
2. The hardware matches the advertised specification (not a weaker machine at a premium price)
3. The machine is unique (not one machine masquerading as a fleet)
4. The hardware identity persists across sessions (the same machine that performed well yesterday is the one responding today)

Without PPA, agent-to-agent compute markets devolve into trust-based systems indistinguishable from centralized cloud providers. PPA makes hardware verification trustless.

### Why Existing Attestation Falls Short

**Intel SGX / AMD SEV / ARM TrustZone:**
These Trusted Execution Environment (TEE) technologies prove that code ran inside a secure enclave on a genuine Intel/AMD/ARM processor. They do NOT prove hardware uniqueness. Two identical Xeon processors produce identical SGX attestation reports. TEEs verify execution integrity, not hardware identity.

**TPM (Trusted Platform Module):**
TPMs provide a hardware root of trust via endorsement keys. However, TPMs are a single point of attestation (one chip, one key). PPA uses seven independent physical channels. A compromised TPM breaks TPM attestation completely. A compromised single PPA channel still leaves six channels operational.

**Worldcoin Orb:**
Worldcoin proves human uniqueness via iris scanning -- biometrics for people. PPA is biometrics for machines. The analogy is precise: just as every human iris has unique patterns formed by physical development, every CPU has unique timing characteristics formed by silicon fabrication variance.

## Specification

### Definition

A system satisfies **Proof of Physical AI** if and only if:

1. **Multi-Channel Attestation**: Hardware identity is attested via five or more independent physical fingerprint channels that measure distinct physical properties of the silicon.
2. **Anti-Emulation Enforcement**: Active checks detect and reject virtualized, emulated, or hypervisor-managed environments.
3. **Fleet Detection**: Clustering analysis prevents one operator from masquerading as multiple independent machines using identical or near-identical hardware configurations.
4. **Server-Side Verification**: Hardware attestation data is validated by the verifying node, not self-reported as a boolean pass/fail by the attesting machine.
5. **Persistence**: Physical uniqueness survives reboots, OS reinstalls, and software updates. The fingerprint is a property of the silicon, not the software.

A system that satisfies conditions 1-5 is said to be **PPA-compliant**. A weaker system satisfying only conditions 1 and 2 is **PPA-partial** and MUST NOT claim full PPA compliance.

### The Seven Fingerprint Channels

RustChain's PPA implementation uses seven independent fingerprint channels, each measuring a distinct physical property of the attesting hardware. These channels are specified in RIP-0007 and implemented in `fingerprint_checks.py`.

#### Channel 1: Clock-Skew and Oscillator Drift

**Physical basis:** Every crystal oscillator has manufacturing imperfections that cause microscopic timing deviations. These imperfections are unique to each physical oscillator and change predictably as the crystal ages.

**Measurement:** 500-5000 high-resolution timing samples are collected using the system's highest-precision clock source. The coefficient of variation (CV) across samples reveals the oscillator's drift signature.

**Detection capability:**
- Virtual machines exhibit unnaturally uniform timing (CV < 0.0001) because the hypervisor virtualizes the clock source
- Real hardware produces CV values between 0.01 and 0.15 depending on oscillator quality and age
- A 20-year-old G4 PowerBook oscillator has a measurably different drift pattern than a new Ryzen 9

```
Formal requirement:
  CV(timing_samples) > CLOCK_DRIFT_THRESHOLD (default: 0.0001)
  where CV = standard_deviation(samples) / mean(samples)
  and |samples| >= 500
```

#### Channel 2: Cache Timing Fingerprint (L1/L2/L3 Latency Tone)

**Physical basis:** CPU caches have characteristic latency profiles that vary by cache size, associativity, replacement policy, and silicon process variation. Even two CPUs of the same model exhibit slightly different latency curves due to fabrication variance.

**Measurement:** A micro-benchmark sweeps across buffer sizes from 1 KB to 64 MB, measuring memory access latency at each size. The resulting latency curve has inflection points at cache boundaries and produces a unique "tone profile."

**Detection capability:**
- Emulators typically model cache as a flat memory hierarchy, producing smooth latency curves
- Real hardware produces sharp inflection points at L1/L2/L3 boundaries
- Aging silicon shows degraded cache performance in predictable patterns

```
Formal requirement:
  latency_profile must exhibit >= 2 statistically significant inflection points
  corresponding to physical cache level boundaries
```

#### Channel 3: SIMD Unit Identity (SSE/AVX/AltiVec/NEON Bias Profile)

**Physical basis:** SIMD execution units have measurable latency bias between instruction groups. A vec_perm operation on POWER8 AltiVec has different relative throughput compared to vec_madd than the equivalent operations on x86 AVX2 or ARM NEON.

**Measurement:** Timed micro-benchmarks execute groups of SIMD instructions (shuffle, multiply-accumulate, permute, shift) and record the throughput ratio between groups. The resulting bias profile is architecture-specific and partially unit-specific.

**Detection capability:**
- Software emulation of SIMD flattens throughput ratios (all operations equally slow)
- Cross-architecture emulation (e.g., AltiVec on x86) produces impossible bias profiles
- Per-unit variation within the same architecture provides additional uniqueness

```
Formal requirement:
  SIMD bias profile must be consistent with known physical architecture
  Throughput variance across instruction groups > SIMD_VARIANCE_THRESHOLD
```

#### Channel 4: Thermal Drift Entropy

**Physical basis:** Silicon junction temperature affects transistor switching speed. The thermal response curve of a CPU -- how quickly it heats under load, how it dissipates heat during idle -- is determined by physical properties: die size, thermal interface material, heatsink mass, and ambient temperature.

**Measurement:** Entropy is collected during four phases: cold boot, warm load, thermal saturation, and relaxation. The entropy quality at each phase forms a thermal signature.

**Detection capability:**
- Virtual machines have no real thermal drift (the host manages thermals)
- Emulators produce uniform entropy across all phases
- Old hardware shows asymmetric thermal response (heats faster, cools slower)

```
Formal requirement:
  Entropy variance across thermal phases > THERMAL_VARIANCE_THRESHOLD
  At least 3 of 4 phases must produce measurably distinct entropy distributions
```

#### Channel 5: Instruction Path Jitter (Microarchitectural Jitter Map)

**Physical basis:** Modern CPUs execute instructions through complex pipelines with branch predictors, reorder buffers, and speculative execution units. The cycle-level timing jitter of instruction sequences is determined by the microarchitectural state, which varies per-machine due to fabrication variance and aging.

**Measurement:** Cycle-level jitter is captured across five pipeline stages: integer, branch, floating-point, load/store, and reorder buffer. The resulting jitter matrix is a unique signature of the microarchitecture and its physical state.

**Detection capability:**
- No virtual machine or emulator replicates real microarchitectural jitter at nanosecond precision
- Identical CPU models produce distinguishable jitter maps due to silicon lottery
- Jitter characteristics drift predictably with silicon aging

```
Formal requirement:
  Jitter matrix must have rank >= 3 (at least 3 linearly independent jitter components)
  Individual pipeline stage jitter > JITTER_FLOOR (architecture-dependent)
```

#### Channel 6: Device-Age Oracle Fields (Historicity Attestation)

**Physical basis:** Every CPU has a model name, release year, silicon stepping, and firmware version that can be cross-referenced against public databases. Combined with entropy measurements, these fields prevent "new CPU pretending to be old."

**Measurement:** CPU model, stepping, microcode version, BIOS/firmware date, and manufacturing batch are collected and validated against known-good databases.

**Detection capability:**
- A modern CPU cannot convincingly report a 2003 release year while simultaneously producing modern-architecture entropy patterns
- Firmware dates that postdate the claimed hardware release year are flagged
- Unknown or missing model strings trigger additional scrutiny

```
Formal requirement:
  Reported device age must be consistent with entropy fingerprint characteristics
  Cross-validation score > AGE_CONSISTENCY_THRESHOLD
```

#### Channel 7: Anti-Emulation Behavioral Checks

**Physical basis:** Hypervisors, emulators, and virtual machines leave detectable artifacts: scheduling patterns, time dilation, flattened jitter distributions, uniform thermal response, and perfect cache curves that are impossible on real hardware.

**Measurement:** Active probes check for:
- Hypervisor CPUID leaf presence (VMware, KVM, Xen, Hyper-V, QEMU)
- `/sys/class/dmi/id/sys_vendor` containing virtual machine vendor strings
- `/proc/scsi/scsi` containing virtual disk identifiers
- `cpuinfo` flags indicating hypervisor presence
- Timing analysis for hypervisor scheduling artifacts

**Detection capability:**
- QEMU/KVM detected via DMI vendor string, SCSI descriptors, and CPUID
- VMware detected via backdoor I/O port and VMware tools presence
- VirtualBox detected via ACPI table signatures
- Sophisticated nested virtualization detected via timing analysis

```
Formal requirement:
  anti_emulation.passed == true
  AND vm_indicators == [] (empty list)
  OR explicit VM acknowledgment with reduced weight (see Enforcement)
```

### Extended Checks

Beyond the seven core channels, PPA incorporates additional verification layers:

#### ROM Fingerprint Anti-Emulation (RIP-0201)

Emulators for vintage platforms (SheepShaver, Basilisk II, UAE/WinUAE) use identical pirated ROM dumps. A database of 61 known emulator ROM hashes (Amiga Kickstart, Mac 68K, Mac PPC) enables instant detection. Clustering analysis flags multiple miners reporting identical ROM hashes.

```
Detection rules:
  1. ROM hash matches known emulator ROM database -> REJECT
  2. Three or more miners report identical ROM hash -> CLUSTER_FLAG all
  3. Unique ROM hash with consistent architecture data -> ACCEPT
```

#### Server-Side Architecture Verification

The verifying node does not trust self-reported architecture claims. The `derive_verified_device()` function cross-validates:

1. SPARC/MIPS/RISC-V detected first via instruction set probes
2. Vintage ARM (arm7tdmi, StrongARM) preserved with appropriate multipliers
3. Modern ARM overridden to `aarch64` with minimal weight -- catches NAS/SBC devices spoofing x86
4. PowerPC deep-validated via SIMD/cache fingerprint evidence
5. x86 validated via CPUID brand string and microarchitecture probes

```
Verification chain:
  client reports device_arch -> server validates against fingerprint evidence
  Mismatch -> server overrides with derived architecture
  Server-derived architecture determines reward multiplier
```

#### Hardware Binding

Each attesting machine is bound to a hardware identity computed from multiple independent fields:

```python
hw_id = SHA256(model | arch | family | cpu_serial | device_id | sorted_macs)[:32]
```

The inclusion of MAC addresses ensures that virtual machines with identical architecture labels but different network interfaces produce distinct hardware identities. Hardware bindings are stored in the `hardware_bindings` table and enforced per-wallet: one hardware identity, one wallet.

### Enforcement Model

PPA attestation results determine reward eligibility through a graduated weight system:

| Attestation Result | Weight | Reward Multiplier |
|--------------------|--------|-------------------|
| All 7 channels PASS, real hardware | 1.0 | Full antiquity multiplier |
| All channels PASS, known VM | 0.000000001 | Effectively zero (1 billionth) |
| Any channel FAIL, real hardware | 0.0 | No rewards until re-attestation |
| Fleet detection triggered | 0.0 | All clustered miners suspended |
| Self-reported pass without evidence | 0.0 | Server requires raw data |

**Critical enforcement principle:** The server never trusts `"passed": true` from the client. All fingerprint data must include raw evidence (timing samples, cache latency arrays, SIMD throughput ratios) that the server independently validates.

VMs are not banned from the network. They can attest, they can participate, and they can transact. They simply earn rewards at a rate that makes VM farming economically irrational. This is by design: it creates a permissionless network where the incentive structure naturally rewards real hardware without requiring gatekeeping.

## The Vintage Curve

### Every Machine Becomes Vintage

Traditional economics treats computing hardware as a depreciating asset. A server purchased today loses value monotonically until it reaches salvage price. PPA inverts this curve.

Under RustChain's antiquity multiplier system (RIP-0001, RIP-0200), hardware earns increasing rewards as it ages:

| Device Age | Category | Multiplier Range |
|------------|----------|------------------|
| 0-5 years | Modern | 0.8x - 1.0x |
| 5-10 years | Aging | 1.0x - 1.3x |
| 10-15 years | Retro | 1.3x - 1.8x |
| 15-20 years | Vintage | 1.8x - 2.5x |
| 20+ years | Ancient | 2.0x - 4.0x (architecture-dependent) |

A Threadripper purchased today at 0.8x will, if preserved and operated continuously, cross 1.0x within five years and continue climbing. By the time it reaches 15 years old, it earns more per epoch than it did when new.

This creates a long-term economic incentive to **preserve and operate aging hardware** rather than discard it. E-waste reduction is not a side effect; it is a designed outcome of the incentive structure.

### The Decay Function

Antiquity multipliers are not permanent. They decay over time to prevent infinite accumulation:

```
aged_multiplier = 1.0 + (base_multiplier - 1.0) * (1 - 0.15 * chain_age_years)
```

A G4 PowerBook (base 2.5x) decays as follows:

| Chain Age | Aged Multiplier | Effective Bonus |
|-----------|----------------|-----------------|
| Year 0 | 2.50x | +150% |
| Year 1 | 2.275x | +127.5% |
| Year 5 | 1.375x | +37.5% |
| Year 10 | 1.0x | +0% (floor) |
| Year 16.67 | 1.0x | Bonus fully decayed |

The decay function ensures that the vintage bonus window is finite. After approximately 16.67 years of chain operation, all multipliers converge to 1.0x, creating a level playing field. The incentive to preserve hardware persists because new hardware entering the network starts below 1.0x and must age into bonus territory.

### Economic Implications

The Vintage Curve creates a futures market in aging hardware:

1. **Acquisition arbitrage:** Old enterprise hardware (datacenter decomm, surplus auctions) can be acquired cheaply and deployed at high multipliers immediately
2. **Preservation incentive:** Machines that would otherwise be scrapped become productive assets
3. **Anti-centralization:** No single operator can corner the vintage hardware market because vintage machines are distributed across garages, basements, and storage units worldwide
4. **Predictable returns:** A miner can calculate future earnings based on current hardware age and the decay function

## Relationship to DePIN

PPA is a **specialization of DePIN** focused on compute hardware identity rather than infrastructure availability. The relationship is hierarchical:

```
Decentralized Physical Infrastructure Networks (DePIN)
  |
  +-- Storage DePIN (Filecoin, Arweave)
  |     Proves: storage capacity exists
  |     Does not prove: which physical drive
  |
  +-- Network DePIN (Helium, XNET)
  |     Proves: radio/network coverage exists
  |     Does not prove: which physical radio
  |
  +-- Compute DePIN (Render, io.net, Akash)
  |     Proves: GPU/CPU compute was performed
  |     Does not prove: which physical processor
  |
  +-- Proof of Physical AI (PPA) [RustChain, this RIP]
        Proves: THIS specific machine, with THIS silicon,
                at THIS age, did THIS work
        Unique properties: hardware identity, anti-emulation,
                          fleet detection, vintage incentives
```

PPA is compatible with and complementary to existing DePIN categories. A storage DePIN could adopt PPA to prove which physical drive stores data. A compute DePIN could adopt PPA to prove which physical GPU processed a render job. PPA is a verification layer, not a competing protocol.

### Comparison Matrix

| Property | Filecoin | Helium | Render | io.net | **RustChain PPA** |
|----------|----------|--------|--------|--------|-------------------|
| Proves work happened | Yes | Yes | Yes | Yes | **Yes** |
| Proves specific hardware | No | No | No | No | **Yes** |
| Anti-emulation | No | No | No | Partial | **7-channel** |
| Fleet detection | No | Partial | No | No | **Yes (RIP-0201)** |
| Hardware identity persists | N/A | N/A | N/A | N/A | **Yes** |
| Vintage incentives | No | No | No | No | **Yes** |
| Server-side verification | No | Partial | No | No | **Yes** |
| Open fingerprint channels | N/A | N/A | N/A | N/A | **7 (extensible)** |

## Agent Economy Integration

### Verifiable Compute Receipts

Every PPA attestation produces a cryptographic receipt containing:

```json
{
  "miner_id": "unique-hardware-bound-id",
  "hardware_id": "sha256-of-physical-properties",
  "device_arch": "server-verified-architecture",
  "fingerprint_passed": true,
  "attestation_ts": 1712390400,
  "nonce": "unique-per-attestation",
  "epoch": 1042,
  "entropy_score": 0.847
}
```

An AI agent purchasing compute from a PPA-compliant provider receives this receipt as proof that:
- The work was performed on a specific, identified machine
- The machine passed all fingerprint checks at the time of attestation
- The attestation is timestamped and nonce-protected against replay

### Trustless Hardware Selection

Agents can express hardware preferences and verify fulfillment:

```
Agent A: "I need inference on real POWER8 hardware, minimum 128 threads"
Agent B: "I provide POWER8 inference, PPA-attested, hw_id = abc123..."
Agent A: [verifies PPA attestation for hw_id abc123 against known POWER8 fingerprint profiles]
Agent A: [submits inference job]
Agent A: [receives result + PPA receipt confirming abc123 processed it]
```

This is impossible with current compute markets. AWS does not tell you which physical CPU processed your Lambda invocation. PPA makes hardware selection verifiable.

### Machine-to-Machine Payment Rails

RTC tokens (RIP-0200) serve as the payment medium for agent-to-agent compute transactions. The flow:

1. Agent A requests PPA attestation from Agent B's hardware
2. Agent B's hardware submits attestation to RustChain node
3. Node verifies attestation and issues compute receipt
4. Agent A verifies receipt and submits RTC payment
5. Payment recorded on RustChain ledger with attestation reference

This creates a complete, trustless pipeline from hardware verification to payment settlement without centralized intermediaries.

## Security Considerations

### Attestation Replay Attacks

**Threat:** An attacker captures a valid PPA attestation and replays it to claim work they did not perform.

**Mitigation:** Every attestation includes:
- A unique nonce generated by the verifying node
- A Unix timestamp with a 24-hour TTL (ATTESTATION_TTL = 86400)
- Server-side deduplication by (miner_id, nonce) tuple

Replayed attestations are rejected because the nonce has already been consumed. Stale attestations are rejected because the timestamp exceeds TTL.

### Side-Channel Leakage from Fingerprinting

**Threat:** Fingerprint data reveals information about the hardware that could be used for targeted attacks (e.g., exploiting known vulnerabilities in a specific CPU stepping).

**Mitigation:** Fingerprint data submitted to the network consists of:
- Statistical summaries (coefficient of variation, throughput ratios) rather than raw timing traces
- Architecture categories rather than exact model numbers
- One-way hardware ID hashes rather than reversible identifiers

The fingerprint channels are designed to be **non-reversible**: knowing that a machine has CV=0.092 for clock drift does not reveal the CPU model. The information flows from physical properties to statistical signatures, not the reverse.

### Hardware Spoofing via FPGA

**Threat:** An attacker programs an FPGA to emulate the fingerprint profile of a vintage CPU, claiming high antiquity multipliers for modern silicon.

**Mitigation:**
- Thermal drift entropy (Channel 4) requires physical heat generation and dissipation that FPGAs cannot perfectly replicate at the junction level
- Instruction path jitter (Channel 5) requires a real instruction pipeline with branch prediction and speculative execution; FPGAs implementing these structures are effectively building a real CPU
- The economic cost of an FPGA sophisticated enough to pass all 7 channels exceeds the reward from the antiquity bonus

Additionally, fleet detection (RIP-0201) flags FPGA farms that produce suspiciously similar fingerprint profiles across multiple "different" machines.

### Sybil Attacks via Hardware Acquisition

**Threat:** An attacker purchases many vintage machines to accumulate disproportionate rewards.

**Mitigation:** This is not considered an attack. An operator who acquires, powers, maintains, and operates real vintage hardware is performing exactly the work PPA incentivizes. The hardware is real, the electricity is real, the maintenance is real. The Vintage Curve decay function (Section 5) ensures that multipliers converge to 1.0x over time, limiting the long-term advantage of vintage hardware.

The practical ceiling is set by the physical constraints: vintage hardware is scarce, requires specialized knowledge to maintain, consumes non-trivial electricity, and has failure modes that modern hardware does not. The market for vintage PowerPC, SPARC, and MIPS hardware is small and fragmented, preventing corner-by-accumulation.

### Timing Oracle Attacks

**Threat:** A sophisticated attacker measures the fingerprinting process itself to learn the thresholds and calibrate spoofed responses.

**Mitigation:**
- Fingerprint thresholds are server-side configuration, not shipped in client code
- The server can rotate threshold values without client updates
- Multiple channels must be spoofed simultaneously; calibrating one channel disrupts another
- Burst entropy injection from hardware timebase (POWER8 mftb) adds unpredictable variation to every measurement

## Implementation Status

### Deployed Components

| Component | Status | Deployment |
|-----------|--------|------------|
| Clock-Skew & Oscillator Drift | IMPLEMENTED | All miner clients |
| Cache Timing Fingerprint | IMPLEMENTED | All miner clients |
| SIMD Unit Identity | IMPLEMENTED | All miner clients |
| Thermal Drift Entropy | IMPLEMENTED | All miner clients |
| Instruction Path Jitter | IMPLEMENTED | All miner clients |
| Device-Age Oracle Fields | PENDING | Design complete |
| Anti-Emulation Behavioral Checks | IMPLEMENTED | All miner clients |
| ROM Fingerprint Database | IMPLEMENTED | 61 known hashes |
| Server-Side Verification | IMPLEMENTED | Nodes 1-4 |
| Fleet Detection (RIP-0201) | DEPLOYED | Nodes 1-4 |
| Hardware Binding | DEPLOYED | Nodes 1-4 |
| derive_verified_device() | DEPLOYED | Nodes 1-4 |

### Attestation Node Coverage

| Node | Location | Status |
|------|----------|--------|
| Node 1 (50.28.86.131) | LiquidWeb VPS, US | Primary, PPA-enforcing |
| Node 2 (50.28.86.153) | LiquidWeb VPS, US | Secondary, Ergo anchor |
| Node 3 (76.8.228.245) | Ryan's Proxmox, US | First external node |
| Node 4 (38.76.217.189) | CognetCloud, Hong Kong | First Asian node |

### Active PPA-Verified Hardware

| Architecture | Machines | Multiplier | PPA Status |
|--------------|----------|------------|------------|
| PowerPC G4 | 4+ | 2.5x | Full PPA (all channels pass) |
| PowerPC G5 | 2 | 2.0x | Full PPA (all channels pass) |
| POWER8 S824 | 1 | 1.5x | Full PPA (all channels pass) |
| Apple Silicon M2 | 1 | 1.2x | Full PPA (all channels pass) |
| x86_64 Modern | 3+ | 1.0x | Full PPA (all channels pass) |
| QEMU VM | 1 | 0.000000001x | PPA-partial (anti-emu fails, by design) |

### Key Files

```
Client-side:
  fingerprint_checks.py          # 7 hardware fingerprint checks
  hardware_fingerprint.py        # Comprehensive HardwareFingerprint class
  rustchain_linux_miner.py       # Miner client with PPA attestation
  rom_fingerprint_db.py          # 61 known emulator ROM hashes

Server-side:
  rustchain_v2_integrated_v2.2.1_rip200.py   # Main node with PPA enforcement
  rip_200_round_robin_1cpu1vote.py           # Reward calculation with multipliers
  rewards_implementation_rip200.py           # Epoch settlement
  rom_clustering_server.py                   # Fleet detection via ROM analysis
```

## Prior Art

### Proof of Work (Bitcoin, 2008)

Nakamoto's Proof of Work proves that computational energy was expended to find a hash below a target difficulty. PoW proves energy expenditure; it does not prove hardware identity. Any machine that finds a valid hash receives the reward regardless of its physical properties. PPA differs fundamentally: it proves which machine did the work, not just that work was done.

**Citation:** Nakamoto, S. (2008). "Bitcoin: A Peer-to-Peer Electronic Cash System."

### Intel SGX and AMD SEV (2015, 2016)

Trusted Execution Environments (TEEs) provide hardware-backed attestation that code executed within a secure enclave. SGX attestation proves execution integrity on genuine Intel silicon. However, two identical Intel CPUs produce identical SGX attestation reports. TEEs prove execution context, not hardware uniqueness. PPA proves uniqueness through physical measurement, not manufacturer-issued certificates.

**Citation:** Costan, V. & Devadas, S. (2016). "Intel SGX Explained." IACR Cryptology ePrint Archive.

### Worldcoin Orb (2023)

Worldcoin's Orb device scans human irises to create unique identity proofs. The Orb proves human uniqueness through biometric measurement. PPA applies the same principle to machines: it proves machine uniqueness through silicon measurement. The Orb uses optical sensors; PPA uses timing channels. Both exploit the fact that physical manufacturing processes create irreproducible variation.

**Citation:** Worldcoin Foundation. (2023). "Proof of Personhood." https://whitepaper.worldcoin.org/

### Filecoin Proof of Replication (2017)

Filecoin's PoRep proves that a storage provider has created a unique physical copy of data. PoRep is specific to storage and does not address compute hardware identity. PPA is specific to compute hardware and does not address storage. The two are complementary: a combined system could prove "this specific drive on this specific machine stores this data."

**Citation:** Protocol Labs. (2017). "Filecoin: A Decentralized Storage Network." Section 3.

### DePIN Category (2022-present)

The Decentralized Physical Infrastructure Network category, coined by Messari in late 2022, encompasses projects that incentivize deployment of real-world infrastructure. PPA is positioned as a DePIN specialization focused on compute hardware identity verification, filling the provenance gap identified in the Motivation section of this document.

**Citation:** Messari. (2022). "The DePIN Sector Map."

### RustChain Prior RIPs

PPA builds directly on:
- **RIP-0001 (Proof of Antiquity):** Established the antiquity scoring and vintage multiplier framework
- **RIP-0007 (Entropy Fingerprinting):** Specified the seven fingerprint channels and anti-emulation checks
- **RIP-0200 (1-CPU-1-Vote):** Established the round-robin attestation model and reward distribution
- **RIP-0201 (Fleet Detection):** Specified ROM clustering and fleet immune system

PPA synthesizes these components into a named, citable protocol category that can be referenced by external projects and academic literature.

## Future Work

### Channel 8+: Extensible Fingerprint Framework

The seven-channel architecture is not fixed. Future RIPs may add:
- **GPU fingerprinting:** Shader execution jitter, VRAM timing profiles
- **Network interface fingerprinting:** PHY-level timing characteristics
- **Storage fingerprinting:** Disk seek latency patterns, flash cell degradation signatures
- **Sensor fusion:** Combining accelerometer, gyroscope, and magnetometer data on mobile devices

Each new channel increases the cost of comprehensive spoofing multiplicatively.

### Cross-Chain PPA Verification

PPA attestations anchored to the Ergo blockchain (via existing anchor transactions) can be verified by external chains. A future RIP may define a standardized PPA receipt format that other blockchains can consume, enabling cross-chain hardware verification.

### PPA Certification Standard

As PPA matures, a formal certification program could evaluate hardware platforms for PPA compatibility. This is analogous to FIPS 140-2 certification for cryptographic modules: a standardized evaluation that hardware manufacturers can seek for their products.

### Academic Publication

The PPA concept, along with empirical data from RustChain's operational network, is suitable for submission to conferences in distributed systems (NSDI, OSDI), security (IEEE S&P, USENIX Security), or blockchain-specific venues (Financial Cryptography, IEEE Blockchain).

## Glossary

| Term | Definition |
|------|-----------|
| **PPA** | Proof of Physical AI. A protocol category proving hardware identity and authenticity. |
| **PPA-compliant** | A system satisfying all 5 PPA conditions (multi-channel, anti-emulation, fleet detection, server-side verification, persistence). |
| **PPA-partial** | A system satisfying only multi-channel attestation and anti-emulation, without fleet detection or server-side verification. |
| **Fingerprint channel** | An independent measurement of a physical property of computing hardware (e.g., clock drift, cache latency, thermal response). |
| **Hardware binding** | The cryptographic association of a physical machine's fingerprint with a wallet identity. |
| **Vintage Curve** | The economic model in which hardware increases in reward multiplier as it ages. |
| **Fleet detection** | Analysis that identifies multiple machines controlled by a single operator masquerading as independent nodes. |
| **Antiquity multiplier** | A reward scaling factor based on hardware architecture and age (RIP-0001, RIP-0200). |
| **DePIN** | Decentralized Physical Infrastructure Network. The broader category that PPA specializes within. |

## Copyright

This document and the term "Proof of Physical AI" (PPA) are placed in the public domain under CC0 1.0 Universal.

First published: April 6, 2026, by Scott Boudreaux / Elyan Labs.

This document constitutes prior art for the term and concept.

---

## Appendix A: Formal PPA Compliance Checklist

A system claiming PPA compliance MUST satisfy all of the following:

```
[ ] 1. Multi-Channel Attestation
      [ ] 1a. Implements >= 5 independent fingerprint channels
      [ ] 1b. Each channel measures a distinct physical property
      [ ] 1c. Channels produce statistical summaries, not raw hardware identifiers
      [ ] 1d. Channel results are submitted with raw evidence data

[ ] 2. Anti-Emulation Enforcement
      [ ] 2a. Active detection of QEMU, VMware, VirtualBox, KVM, Xen, Hyper-V
      [ ] 2b. Detection via >= 3 independent methods (DMI, CPUID, SCSI, timing)
      [ ] 2c. Detected VMs receive reduced weight, not network ban

[ ] 3. Fleet Detection
      [ ] 3a. Clustering analysis on fingerprint similarity
      [ ] 3b. ROM hash database for vintage platform emulators
      [ ] 3c. Hardware ID binding prevents wallet-hopping

[ ] 4. Server-Side Verification
      [ ] 4a. Server validates raw fingerprint evidence, not boolean pass/fail
      [ ] 4b. Server derives architecture independently of client claims
      [ ] 4c. Threshold values are server-side configuration

[ ] 5. Persistence
      [ ] 5a. Hardware identity survives OS reinstall
      [ ] 5b. Hardware identity survives software updates
      [ ] 5c. Hardware identity survives reboot
      [ ] 5d. Identity changes only with physical hardware changes
```

## Appendix B: PPA vs. Alternative Verification Approaches

| Approach | Proves Hardware Identity | Multi-Channel | Anti-Emulation | Fleet Detection | No Trusted Third Party |
|----------|------------------------|---------------|----------------|-----------------|----------------------|
| TPM Attestation | Partial (single chip) | No | No | No | No (requires manufacturer) |
| Intel SGX | No (same report per model) | No | N/A (is TEE) | No | No (requires Intel) |
| AMD SEV | No (same report per model) | No | N/A (is TEE) | No | No (requires AMD) |
| Worldcoin Orb | Yes (for humans) | Yes (iris) | N/A | N/A | No (requires Orb hardware) |
| Proof of Work | No | No | No | No | Yes |
| Proof of Stake | No | No | No | No | Yes |
| **PPA (this RIP)** | **Yes** | **Yes (7+)** | **Yes** | **Yes** | **Yes** |

## Appendix C: Timeline

```
2025-11-28  RIP-0001 (Proof of Antiquity) published
2025-01-15  RIP-0007 (Entropy Fingerprinting) published
2025-12-02  RIP-0200 (1-CPU-1-Vote) deployed to production
2025-12-05  7-channel fingerprint checks deployed to all miners
2025-12-05  Server-side fingerprint validation deployed
2025-12-05  Anti-emulation enforcement active (VMs = 1 billionth weight)
2025-12-05  ROM fingerprint database created (61 known hashes)
2025-12-20  Hardware binding deployed (MAC + device fields)
2025-12-20  Security audit completed (BuilderFred, 6 vulnerabilities fixed)
2026-02-03  Server-side architecture verification deployed
2026-03-04  RIP-0201 (Fleet Detection) deployed
2026-04-06  RIP-0308 (Proof of Physical AI) published — THIS DOCUMENT
            Term "Proof of Physical AI" coined.
            Prior art established.
```
