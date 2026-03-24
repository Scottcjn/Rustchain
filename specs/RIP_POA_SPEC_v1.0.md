# RIP-PoA: Proof of Antiquity

**RustChain Improvement Proposal -- Hardware Attestation Protocol**

| Field | Value |
|-------|-------|
| **RIP** | PoA (Proof of Antiquity) |
| **Title** | Hardware Fingerprint Attestation for 1-CPU-1-Vote Consensus |
| **Status** | Active (Deployed) |
| **Version** | 1.0 |
| **Date** | 2026-03-24 |
| **Authors** | Scott Boudreaux, Elyan Labs |
| **Depends On** | RIP-200 (Round-Robin Consensus) |
| **Reference Implementation** | `fingerprint_checks.py`, `hardware_fingerprint.py`, `rip_200_round_robin_1cpu1vote.py`, `rom_fingerprint_db.py`, `rom_clustering_server.py` |

---

## Abstract

RIP-PoA defines a hardware fingerprint attestation protocol that ensures each participant in the RustChain network corresponds to a distinct physical CPU. Miners submit cryptographic evidence of their hardware characteristics -- oscillator drift, cache hierarchy, SIMD capabilities, thermal behavior, instruction jitter, device provenance, and virtualization absence -- which the network validates server-side before granting reward eligibility. Vintage and exotic hardware receives time-decaying reward multipliers ("antiquity bonuses"), incentivizing the preservation of computing history while preventing emulator-based and VM-based Sybil attacks.

RIP-PoA is the enforcement layer for RIP-200's 1-CPU-1-Vote round-robin consensus. Without hardware attestation, any adversary could spawn unlimited virtual machines to dominate block production and reward distribution.

---

## 1. Motivation

### 1.1 The Sybil Problem in Proof-of-Work Alternatives

Traditional Proof-of-Work ties identity to energy expenditure. Proof-of-Stake ties it to capital. RustChain's 1-CPU-1-Vote model ties identity to *physical hardware* -- but only if that hardware can be proven real. Without hardware attestation:

- A single Threadripper could spawn 128 virtual machines, each claiming to be a separate miner.
- Emulators like SheepShaver or QEMU could fabricate vintage PowerPC or Amiga hardware, claiming high antiquity multipliers (up to 4.0x).
- Cloud providers (AWS, GCP, Azure) could be used to create on-demand mining farms.
- ROM packs distributed with emulators would produce identical fingerprints across hundreds of "miners."

### 1.2 Why Vintage Hardware Matters

RustChain incentivizes hardware preservation. A running PowerPC G4 from 2003, a Sun SPARCstation, or a functioning Amiga represents computing heritage that deserves recognition. The antiquity multiplier system rewards operators of vintage hardware with higher per-epoch RTC allocations -- but only when that hardware is demonstrably real.

### 1.3 Design Goals

1. **No false negatives on real hardware.** A legitimate 20-year-old G4 must always pass.
2. **Catch all known virtualization.** VMs, hypervisors, cloud instances, and emulators must be detected.
3. **Degrade gracefully.** Legacy miners (Python 2.x, old OSes) that cannot run all checks still participate, but at reduced trust levels.
4. **Resist spoofing.** Self-reported strings (CPU model, architecture) are never trusted alone. Physical measurements validate claims.
5. **Preserve privacy.** MAC addresses are hashed with epoch-scoped salts. No persistent hardware identifiers leave the miner.

---

## 2. System Overview

```
                                     RustChain Network
                                     =================

  +-----------------+     HTTPS/TLS      +-------------------+
  |  Miner Client   | ----------------> |  Attestation Node  |
  |                 |  attestation JSON  |                   |
  |  7 fingerprint  |                    |  validate_        |
  |  checks run     |                    |  fingerprint_data |
  |  locally        |  <--------------- |                   |
  |                 |  ticket + status   |  derive_verified_ |
  +-----------------+                    |  device()         |
                                         |                   |
                                         |  epoch_enroll     |
                                         |  (weight = mult)  |
                                         +-------------------+
                                                  |
                                                  v
                                         +-------------------+
                                         |  Epoch Settlement |
                                         |                   |
                                         |  1.5 RTC / epoch  |
                                         |  weighted by       |
                                         |  antiquity mult   |
                                         +-------------------+
                                                  |
                                                  v
                                         +-------------------+
                                         |  Ergo Anchor      |
                                         |                   |
                                         |  Blake2b256       |
                                         |  commitment in    |
                                         |  register R4      |
                                         +-------------------+
```

### 2.1 Attestation Flow

1. Miner client runs all applicable fingerprint checks locally.
2. Client submits attestation payload to `POST /attest/submit` on the nearest attestation node.
3. Server calls `validate_fingerprint_data()` to verify raw evidence.
4. Server calls `derive_verified_device()` to determine the canonical architecture (overriding self-reported claims when evidence contradicts them).
5. If validation passes, the miner is recorded in `miner_attest_recent` with `fingerprint_passed = 1`.
6. The miner is auto-enrolled for the current epoch with a weight equal to its time-aged antiquity multiplier.
7. Attestation is valid for 24 hours (`ATTESTATION_TTL = 86400` seconds).

### 2.2 Attestation Payload Format

```json
{
  "miner": "<wallet_address>",
  "miner_id": "<human_readable_id>",
  "nonce": "<random_hex>",
  "report": {
    "commitment": "<sha256_of_nonce_wallet_entropy>"
  },
  "device": {
    "model": "<cpu_model_string>",
    "arch": "<claimed_architecture>",
    "family": "<claimed_family>",
    "machine": "<platform.machine()>",
    "cpu_serial": "<optional_serial>",
    "device_id": "<optional_unique_id>"
  },
  "signals": {
    "macs": ["<mac1>", "<mac2>"]
  },
  "fingerprint": {
    "all_passed": true,
    "checks": {
      "clock_drift":        { "passed": true, "data": { ... } },
      "cache_timing":       { "passed": true, "data": { ... } },
      "simd_identity":      { "passed": true, "data": { ... } },
      "thermal_drift":      { "passed": true, "data": { ... } },
      "instruction_jitter": { "passed": true, "data": { ... } },
      "device_age_oracle":  { "passed": true, "data": { ... } },
      "anti_emulation":     { "passed": true, "data": { ... } },
      "rom_fingerprint":    { "passed": true, "data": { ... } }
    }
  }
}
```

---

## 3. Fingerprint Check Specifications

All checks return a tuple `(passed: bool, data: dict)`. The `data` dict contains raw measurements that the server independently validates. The server does NOT trust the client-reported `passed` field -- it re-evaluates the raw data.

### 3.1 Check 1: Clock-Skew and Oscillator Drift

**Purpose:** Every physical CPU oscillator has microscopic timing imperfections caused by silicon manufacturing variance, temperature, voltage fluctuation, and crystal aging. Virtual machines share the host's clock and cannot reproduce per-chip drift signatures.

**Procedure:**

1. Perform `N` iterations (default `N = 200`, range 500--5000 for higher confidence) of a fixed workload (5,000 SHA-256 hash operations per iteration).
2. Record the wall-clock duration of each iteration using `time.perf_counter_ns()`.
3. Every 50 iterations, insert a 1ms sleep to allow oscillator drift to manifest.
4. Compute:
   - `mean_ns`: Arithmetic mean of all intervals.
   - `stdev_ns`: Standard deviation of all intervals.
   - `cv` (coefficient of variation): `stdev_ns / mean_ns`.
   - `drift_stdev`: Standard deviation of consecutive-pair differences (`intervals[i] - intervals[i-1]`).

**Pass Criteria:**

| Metric | Threshold | Rationale |
|--------|-----------|-----------|
| `cv` | > 0.0001 | Real oscillators have measurable variance; synthetic timers are too stable. |
| `drift_stdev` | > 0 | Consecutive samples must show non-zero drift. |

**Fail Reasons:**
- `synthetic_timing`: CV below threshold indicates an emulated or virtualized timer.
- `no_drift`: Zero drift standard deviation indicates perfectly uniform execution, which is physically impossible on real silicon.

**Server-Side Validation:**
The server rejects `cv < 0.0001` regardless of the client's self-reported `passed` status. The server also checks that the raw `cv` and `drift_stdev` values are present in the payload.

### 3.2 Check 2: Cache Timing Fingerprint

**Purpose:** Real CPUs have a multi-level cache hierarchy (L1, L2, L3) with distinct latency characteristics. Buffer accesses that fit in L1 are faster than those spilling into L2, and so on. Emulators and VMs often present flat or uniform cache behavior because the hypervisor's memory management layer intercedes.

**Procedure:**

1. Allocate three buffers sized to approximate L1 (8 KB), L2 (128 KB), and L3 (4 MB).
2. For each buffer, perform 1,000 sequential accesses at 64-byte stride.
3. Repeat `iterations` times (default 100) and compute mean access time per access.
4. Calculate latency ratios:
   - `l2_l1_ratio`: L2 mean latency / L1 mean latency.
   - `l3_l2_ratio`: L3 mean latency / L2 mean latency.

**Extended Procedure (hardware_fingerprint.py):**

For higher fidelity, measure six buffer sizes (4 KB, 32 KB, 256 KB, 1 MB, 4 MB, 16 MB) with both sequential and random access patterns. Compute "tone ratios" -- the progression of latency increases across cache levels. Generate a `cache_hash` from the ratio vector.

**Pass Criteria:**

| Metric | Threshold | Rationale |
|--------|-----------|-----------|
| `l2_l1_ratio` | > 1.01 | L2 must be measurably slower than L1. |
| `l3_l2_ratio` | > 1.01 | L3 must be measurably slower than L2. |
| All latencies | > 0 | Zero latency is physically impossible. |

**Fail Reasons:**
- `no_cache_hierarchy`: Flat latency profile (ratio < 1.01 at both levels) indicates emulated or uniform memory.
- `zero_latency`: Zero-valued measurements indicate measurement failure or extreme emulation artifacts.
- `perfect_cache`: (Server-enforced) Suspiciously regular cache curves with no variance between runs.

### 3.3 Check 3: SIMD Unit Identity

**Purpose:** Different CPU architectures expose different SIMD instruction sets (SSE/AVX on x86, AltiVec/VMX on PowerPC, NEON on ARM). The presence or absence of these capabilities, combined with integer-vs-float pipeline timing bias, creates a microarchitectural signature that emulators cannot perfectly replicate.

**Procedure:**

1. Read `/proc/cpuinfo` flags (Linux) or `sysctl` output (macOS) to enumerate SIMD capabilities.
2. Detect the SIMD family: `sse_avx` (x86), `altivec` (PowerPC), `neon` (ARM), or `unknown`.
3. Measure integer-vs-float pipeline bias:
   - 10,000 integer multiply-accumulate operations, repeated 100 times.
   - 10,000 floating-point multiply-accumulate operations, repeated 100 times.
   - Compute `int_float_ratio = int_mean_ns / float_mean_ns`.
4. Measure vector memory copy latency (128-byte aligned block copies across 1 MB buffer).

**Pass Criteria:**

| Metric | Threshold | Rationale |
|--------|-----------|-----------|
| SIMD flags detected | At least one of SSE, AVX, AltiVec, NEON, or any CPU flag | Every real CPU since the 1990s has some SIMD or at least feature flags. |

**Server-Side Cross-Validation:**
- If a miner claims PowerPC but reports `has_sse = true` or `has_avx = true`, the server overrides the architecture to x86.
- If a miner claims x86 but shows no SSE/AVX flags and has ARM-characteristic `int_float_ratio`, the server may reclassify.
- Pipeline timing bias measurements (int vs float asymmetry) are checked for flatness -- software emulation produces unnaturally symmetric timing.

### 3.4 Check 4: Thermal Drift Entropy

**Purpose:** Real silicon changes performance characteristics as it heats up during sustained load. This thermal drift is a physical property of semiconductor junctions and cannot be faked by emulators, which maintain constant virtual timing regardless of workload.

**Procedure:**

1. **Cold Phase:** Measure 50 samples of a fixed workload (10,000 SHA-256 operations each) at ambient temperature.
2. **Heat Phase:** Perform sustained heavy computation (3x samples at 5x workload each) to raise die temperature.
3. **Hot Phase:** Measure 50 samples of the same workload as the cold phase, immediately after heating.
4. **Cooldown Phase:** Wait 100ms, then measure 50 more samples.
5. Compute:
   - `cold_avg_ns`, `hot_avg_ns`, `cooldown_mean_ns`: Mean latencies per phase.
   - `drift_ratio = hot_avg / cold_avg`: Performance change from thermal loading.
   - `cold_stdev`, `hot_stdev`: Variance within each phase.

**Pass Criteria:**

| Metric | Threshold | Rationale |
|--------|-----------|-----------|
| `cold_stdev` or `hot_stdev` | > 0 | At least one phase must show non-zero variance. |
| `thermal_drift_pct` | > 0.1% (hardware_fingerprint.py) | Measurable performance change from thermal loading. |

**Fail Reasons:**
- `no_thermal_variance`: Both phases show zero standard deviation, indicating synthetic timing.
- `uniform_thermal_response`: (Server-enforced) Cold and hot phases are statistically identical, which is physically impossible under sustained load.

### 3.5 Check 5: Instruction Path Jitter

**Purpose:** Real CPUs exhibit cycle-level jitter across different execution units (integer ALU, FPU, branch predictor, load/store unit) due to pipeline hazards, cache misses, branch mispredictions, and out-of-order execution contention. This jitter is a fingerprint of the microarchitecture. No VM or emulator replicates real jitter down to the nanosecond level.

**Procedure:**

1. **Integer pipeline:** 100 samples of 10,000 integer multiply-accumulate operations.
2. **Floating-point pipeline:** 100 samples of 10,000 FP multiply-accumulate operations.
3. **Branch predictor:** 100 samples of 10,000 alternating-branch operations.
4. **Memory load/store:** (Extended) 500 samples of mixed read/write to a 4 KB buffer.
5. For each pipeline, compute `mean`, `stdev`, `min`, `max`.

**Pass Criteria:**

| Metric | Threshold | Rationale |
|--------|-----------|-----------|
| `int_stdev`, `fp_stdev`, `branch_stdev` | Not all zero | At least one pipeline must show measurable jitter. |
| `avg_jitter_stdev` | > 100 ns (hardware_fingerprint.py) | Real hardware produces >100ns jitter variance across pipeline types. |

**Fail Reasons:**
- `no_jitter`: All three pipelines report zero standard deviation.
- `uniform_jitter_pattern`: (Server-enforced) Jitter CV < 0.01 across all pipelines -- real hardware is noisier.
- `flattened_jitter_distribution`: (Server-enforced) All pipeline jitter values are suspiciously similar, indicating a single emulated timing source.

### 3.6 Check 6: Device-Age Oracle Fields (Historicity Attestation)

**Purpose:** Collect metadata about the CPU model, release year, silicon stepping, and firmware age. Cross-validate these claims against physical measurements from other checks to catch spoofing (e.g., a modern Ryzen pretending to be a G4).

**Procedure:**

1. Read CPU model string from `/proc/cpuinfo` (Linux) or `sysctl -n machdep.cpu.brand_string` (macOS).
2. Read CPU family, model number, and stepping from `/proc/cpuinfo`.
3. Read BIOS/firmware date from `/sys/class/dmi/id/bios_date` and `/sys/class/dmi/id/bios_version`.
4. Estimate release year from CPU model string using pattern matching (Intel Core generation, AMD Ryzen series, PowerPC family, Apple Silicon generation).
5. Compute a confidence score (0.0 -- 1.0):
   - +0.4 if CPU model string is available.
   - +0.2 if release year can be estimated.
   - +0.2 if BIOS date is available.
   - -0.5 if mismatch reasons are detected.
   - Base: 0.2.

**Mismatch Detection Rules:**

| Condition | Mismatch Reason |
|-----------|----------------|
| Architecture is x86 but CPU model contains "powerpc", "g4", "g5", "sparc", "m68k" | `arch_x86_but_claims_vintage_non_x86` |
| Architecture is PPC but CPU model contains "intel", "amd", "ryzen" | `arch_ppc_but_claims_x86` |
| Architecture is ARM but CPU model contains "intel" (and not "apple") | `arch_arm_but_claims_intel` |
| CPU model claims vintage but SIMD flags include AVX/SSE (x86 only) | `vintage_claim_but_modern_simd_flags` |

**Pass Criteria:**

| Metric | Threshold | Rationale |
|--------|-----------|-----------|
| CPU model | Must be non-empty | Cannot validate a device with no identity. |
| Mismatch reasons | Must be empty | Any mismatch indicates spoofing. |

### 3.7 Check 7: Anti-Emulation Behavioral Checks

**Purpose:** Directly detect the presence of hypervisors, virtual machines, cloud instances, and container environments. This is the most critical check -- it catches the most common attack vector (spinning up VMs).

**Procedure:**

1. **DMI/SMBIOS scan:** Read files under `/sys/class/dmi/id/` (`product_name`, `sys_vendor`, `board_vendor`, `board_name`, `bios_vendor`, `chassis_vendor`, `chassis_asset_tag`) and `/proc/scsi/scsi`. Match content against known VM/cloud strings.

2. **Known VM/Cloud strings (comprehensive list):**

   | Category | Strings Matched |
   |----------|----------------|
   | Traditional hypervisors | vmware, virtualbox, kvm, qemu, xen, hyperv, hyper-v, parallels, bhyve |
   | AWS EC2 | amazon, amazon ec2, ec2, nitro |
   | Google Cloud | google, google compute engine, gce |
   | Microsoft Azure | microsoft corporation, azure |
   | DigitalOcean | digitalocean |
   | Linode/Akamai | linode, akamai |
   | Vultr | vultr |
   | Hetzner | hetzner |
   | Oracle Cloud | oracle, oraclecloud |
   | OVH | ovh, ovhcloud |
   | Alibaba Cloud | alibaba, alicloud |
   | Generic VM | bochs, innotek, seabios |

3. **Environment variable check:** Scan for `KUBERNETES`, `DOCKER`, `VIRTUAL`, `container`, `AWS_EXECUTION_ENV`, `ECS_CONTAINER_METADATA_URI`, `GOOGLE_CLOUD_PROJECT`, `AZURE_FUNCTIONS_ENVIRONMENT`, `WEBSITE_INSTANCE_ID`.

4. **CPU hypervisor flag:** Check `/proc/cpuinfo` for the `hypervisor` feature flag (set by all major hypervisors on x86).

5. **Xen hypervisor path:** Check `/sys/hypervisor/type`.

6. **Cloud metadata endpoint:** Attempt HTTP connection to `169.254.169.254` (the link-local metadata endpoint used by AWS, GCP, Azure, DigitalOcean). Also attempt AWS IMDSv2 token acquisition.

7. **systemd-detect-virt:** If available, run `systemd-detect-virt` and check for non-"none" output.

8. **Time dilation detection (hardware_fingerprint.py):** Request 20 x 1ms sleeps. Real hardware completes in ~1ms +/- 0.5ms. VMs often show >5ms actual sleep for a 1ms request due to hypervisor scheduling latency.

9. **Jitter uniformity (hardware_fingerprint.py):** Measure CV of 100 small integer operations. CV < 0.01 (< 1% variation) indicates emulated timing.

**Pass Criteria:**

| Metric | Threshold | Rationale |
|--------|-----------|-----------|
| `vm_indicators` | Must be empty (length 0) | Any single indicator is sufficient to flag virtualization. |
| `sleep_mean_ns` | < 5,000,000 | Time dilation beyond 5x indicates hypervisor scheduling. |
| `jitter_cv` | > 0.01 | Real hardware has > 1% timing variation. |

**Enforcement:**
Miners that fail anti-emulation receive `fingerprint_passed = 0` in the attestation record. Their epoch enrollment weight is set to `0.000000001` (one billionth), making VM mining economically worthless by design.

### 3.8 Check 8: ROM Clustering Analysis (Retro Platforms)

**Purpose:** Emulators like SheepShaver, Basilisk II, UAE/WinUAE, and FS-UAE all use the same pirated ROM dumps. If multiple "different" miners report identical ROM hashes, they are emulated. Real vintage hardware has manufacturing variants, regional differences, and unique wear patterns in its firmware.

**Applicable Platforms:** PowerPC (Mac), 68K (Mac, Amiga, Atari ST), and other retro architectures. Modern x86/ARM miners skip this check.

**Procedure (Client-Side):**

1. Detect platform architecture.
2. For PowerPC: Attempt to read ROM from `/dev/rom` or `/dev/nvram`. Hash the first 256 bytes with MD5.
3. For 68K: Check known emulator ROM directories (`~/.config/fs-uae/Kickstarts/`, `~/.basilisk_ii_prefs`, etc.).
4. Submit ROM hash in attestation payload.

**Procedure (Server-Side -- ROM Clustering Server):**

1. **Known emulator ROM database** (61+ entries):

   | Platform | Count | Hash Type | Examples |
   |----------|-------|-----------|---------|
   | Amiga Kickstart | 12 | SHA-1 | KS 1.3 A500, KS 3.1 A1200/A3000/A4000, CD32, CDTV |
   | Mac 68K (Apple checksum) | 24 | First 4 bytes | Quadra 610/650/800, LC 475, SE/30, Mac Plus |
   | Mac 68K (MD5) | 6 | MD5 | Mac 128/512, Quadra 630, 660AV/840AV |
   | Mac PPC (MD5) | 19 | MD5 | G3 Gossamer, G4 MDD/Sawtooth/Cube, G5, iBook G4, PowerBook |

   If a submitted ROM hash matches any known emulator ROM, the miner is immediately flagged.

2. **Cross-miner clustering detection:**
   - The server maintains a `miner_rom_reports` table mapping `(miner_id, rom_hash)` pairs.
   - When a new report arrives, the server checks how many other miners share the same ROM hash.
   - If `cluster_size > threshold` (default 2), all miners in the cluster are flagged.
   - Flagged miners are recorded in `miner_rom_flags` with the cluster ID.

3. **Database schema:**

   ```sql
   CREATE TABLE miner_rom_reports (
       miner_id TEXT NOT NULL,
       rom_hash TEXT NOT NULL,
       hash_type TEXT NOT NULL,
       platform TEXT,
       first_seen INTEGER NOT NULL,
       last_seen INTEGER NOT NULL,
       report_count INTEGER DEFAULT 1,
       PRIMARY KEY (miner_id, rom_hash)
   );

   CREATE TABLE rom_clusters (
       cluster_id INTEGER PRIMARY KEY AUTOINCREMENT,
       rom_hash TEXT NOT NULL,
       hash_type TEXT NOT NULL,
       miners TEXT NOT NULL,
       cluster_size INTEGER NOT NULL,
       is_known_emulator_rom INTEGER DEFAULT 0,
       first_detected INTEGER NOT NULL,
       last_updated INTEGER NOT NULL
   );

   CREATE TABLE miner_rom_flags (
       miner_id TEXT PRIMARY KEY,
       flag_reason TEXT NOT NULL,
       cluster_id INTEGER,
       flagged_at INTEGER NOT NULL,
       resolved INTEGER DEFAULT 0
   );
   ```

**Pass Criteria:**

| Metric | Threshold | Rationale |
|--------|-----------|-----------|
| ROM hash | Not in known emulator ROM database | Known dumps indicate emulation. |
| Cluster size | <= 2 miners per ROM hash | Real hardware ROMs have manufacturing variance; identical hashes across miners indicate shared emulator ROM packs. |

---

## 4. Server-Side Architecture Validation

### 4.1 `derive_verified_device()`

The server NEVER trusts self-reported architecture strings. The function `derive_verified_device()` applies a validation cascade to determine the canonical device family and architecture:

```
1. Exotic arch detection (SPARC, MIPS, RISC-V, SH, 68K, Cell, Itanium, VAX, Transputer)
   -> If matched, return exotic arch directly.

2. ARM evidence detection (runs for ALL miners)
   -> If ARM evidence found:
      a. Check if arch matches vintage ARM list (ARM2, ARM7TDMI, StrongARM, etc.)
         -> Return specific vintage ARM arch (for LEGENDARY multipliers)
      b. Otherwise, classify as modern ARM (aarch64/armv7, 0.0005x multiplier)
      c. If claimed x86 but detected ARM: OVERRIDE to ARM rate

3. PowerPC deep validation (if PowerPC claimed)
   -> Requires ALL of:
      a. Fingerprint passed
      b. CPU brand string matches PowerPC patterns
      c. SIMD evidence shows AltiVec/VMX (not SSE/AVX)
      d. Cache profile consistent with PowerPC
   -> If any fails: fall through to x86 classification

4. Default: return claimed values
```

### 4.2 ARM Spoofing Detection

Modern ARM devices (NAS boxes, SBCs, phones) claiming x86 or PowerPC architecture are overridden to the `aarch64` rate (0.0005x multiplier). The detection examines:

- `platform.machine()` field in the device payload.
- Absence of x86 SIMD flags (SSE/AVX).
- CPU brand string containing ARM-characteristic patterns.

Vintage ARM devices (ARM2 through Cortex-A9, dating from 1987--2007) retain their specific architecture identifiers and receive appropriate LEGENDARY/ANCIENT multipliers.

### 4.3 `validate_fingerprint_data()`

Server-side fingerprint validation (hardened 2026-02-02):

1. Reject empty or missing fingerprint payloads.
2. Require at minimum `anti_emulation` evidence (most critical check).
3. Re-evaluate raw data -- do NOT trust client-reported `passed` field.
4. Cross-validate device claims against SIMD evidence.
5. Handle both Python format (`{"passed": true, "data": {...}}`) and C miner format (`{"clock_drift": true}`).
6. Legacy PowerPC miners running Python 2.x may not support `time.perf_counter_ns()` -- degrade gracefully.

---

## 5. Device Architecture Multipliers

### 5.1 Complete Multiplier Table

The antiquity multiplier determines a miner's share of per-epoch rewards. Higher multipliers mean more RTC per epoch. The full table is maintained in `rip_200_round_robin_1cpu1vote.py` in the `ANTIQUITY_MULTIPLIERS` dictionary.

#### Ultra-Vintage (1977--1995): 2.5x -- 3.5x

| Architecture | Aliases | Base Multiplier | Era |
|-------------|---------|-----------------|-----|
| DEC VAX | vax, vax_780 | 3.5 | 1977 |
| Inmos Transputer | transputer, t800, t414 | 3.5 | 1984 |
| Fairchild Clipper | clipper | 3.5 | 1986 |
| NS32032 | ns32k | 3.5 | 1984 |
| IBM ROMP | romp | 3.5 | 1986 |
| Intel 386 | 386, i386, 386dx, 386sx | 3.0 | 1985 |
| Motorola 68000 | 68000, mc68000 | 3.0 | 1979 |
| MIPS R2000 | mips_r2000 | 3.0 | 1985 |
| Intel i860/i960 | i860, i960 | 3.0 | 1988--1989 |
| Motorola 88000 | 88k, mc88100 | 3.0 | 1988 |
| AMD 29000 | am29k | 3.0 | 1987 |
| Intel 486 | 486, i486, 486dx, 486dx2 | 2.8--2.9 | 1989 |
| SPARC v7/v8 | sparc_v7, sparc_v8 | 2.7--2.9 | 1987 |
| DEC Alpha | alpha_21064/21164/21264 | 2.3--2.7 | 1992 |
| HP PA-RISC | pa_risc_1_0/1_1/2_0 | 2.3--2.9 | 1986 |
| Motorola 68020--68060 | 68020, 68030, 68040, 68060 | 2.2--2.7 | 1984--1994 |
| MIPS R3000--R12000 | mips_r3000 through mips_r12000 | 2.3--2.9 | 1988--2000 |

#### Vintage ARM (1987--2007): 1.5x -- 4.0x (MYTHIC/LEGENDARY)

| Architecture | Aliases | Base Multiplier | Tier |
|-------------|---------|-----------------|------|
| ARM2 | arm2 | 4.0 | MYTHIC |
| ARM3 | arm3 | 3.8 | MYTHIC |
| ARM6 | arm6 | 3.5 | LEGENDARY |
| ARM7 / ARM7TDMI | arm7, arm7tdmi | 3.0 | LEGENDARY |
| StrongARM | strongarm, sa1100, sa1110 | 2.7--2.8 | LEGENDARY |
| XScale / ARM9 | xscale, arm9, arm926ej | 2.3--2.5 | ANCIENT |
| ARM11 | arm11, arm1176 | 2.0 | ANCIENT |
| Cortex-A8 | cortex_a8 | 1.8 | Early Smartphone |
| Cortex-A9 | cortex_a9 | 1.5 | Early Smartphone |

#### Retro Game Consoles (1983--2006): 1.8x -- 2.8x (RIP-304)

| Architecture | Console | Base Multiplier | Year |
|-------------|---------|-----------------|------|
| 6502 / nes_6502 | NES/Famicom, Apple II, C64 | 2.8 | 1983 |
| ps1_mips | PlayStation 1 | 2.8 | 1994 |
| 65c816 / snes_65c816 | SNES | 2.7 | 1990 |
| z80 / gameboy_z80 | Game Boy, SMS, Spectrum | 2.6 | 1989 |
| saturn_sh2 | Sega Saturn | 2.6 | 1994 |
| genesis_68000 | Sega Genesis | 2.5 | 1988 |
| n64_mips | Nintendo 64 | 2.5 | 1996 |
| itanium / ia64 | Intel Itanium | 2.3--2.5 | 2001 |
| s390 / s390x | IBM Mainframe | 2.3--2.5 | 1990+ |
| gba_arm7 / nds_arm7_arm9 | GBA, Nintendo DS | 2.3 | 2001--2004 |
| sh4 / dreamcast_sh4 | Sega Dreamcast | 2.3 | 1998 |
| ps2_ee / emotion_engine | PlayStation 2 | 2.2 | 2000 |
| ps3_cell / cell_be | PlayStation 3 | 2.2 | 2006 |
| gamecube_gekko | GameCube | 2.1 | 2001 |
| psp_allegrex | PlayStation Portable | 2.0 | 2004 |
| xbox360_xenon / wii_broadway | Xbox 360, Wii | 2.0 | 2005--2006 |
| xbox_celeron | Original Xbox | 1.8 | 2001 |

#### PowerPC Mac (1994--2006): 1.8x -- 2.5x

| Architecture | Aliases | Base Multiplier |
|-------------|---------|-----------------|
| G4 | g4, powerpc, powerpc g4, power macintosh | 2.5 |
| G3 | g3, powerpc g3, powerpc g3 (750) | 1.8 |
| G5 | g5, powerpc g5, powerpc g5 (970) | 2.0 |
| PowerPC Amiga | amigaone_g3/g4, pegasos_g3/g4, sam440/460 | 1.9--2.2 |

#### Vintage x86 (1993--2006): 1.5x -- 2.5x

| Architecture | Aliases | Base Multiplier |
|-------------|---------|-----------------|
| Pentium | pentium, pentium_mmx | 2.4--2.5 |
| Pentium Pro/II/III | pentium_pro/ii/iii | 2.0--2.3 |
| AMD K5/K6 | k5, k6, k6_2, k6_3 | 2.1--2.4 |
| Cyrix 6x86/MII | cyrix_6x86, cyrix_mii | 2.3--2.5 |
| Transmeta | transmeta_crusoe, transmeta_efficeon | 1.9--2.1 |
| VIA C3/C7/Nano | via_c3, via_c7, via_nano | 1.7--2.0 |
| IDT WinChip | winchip, winchip_c6 | 2.3 |
| Pentium 4 | pentium4, pentium_d | 1.5 |

#### IBM POWER (1990--present): 1.5x -- 2.8x

| Architecture | Base Multiplier |
|-------------|-----------------|
| POWER1 | 2.8 |
| POWER2 | 2.6 |
| POWER3 | 2.4 |
| POWER4 | 2.2 |
| POWER5 | 2.0 |
| POWER6 | 1.9 |
| POWER7 | 1.8 |
| POWER8 | 1.5 |
| POWER9 | 1.8 |

#### Modern (2006--present): 0.8x -- 1.3x

| Architecture | Aliases | Base Multiplier |
|-------------|---------|-----------------|
| Core 2 | core2, core2duo | 1.3 |
| Nehalem / Westmere | nehalem, westmere | 1.2 |
| Sandy/Ivy Bridge | sandybridge, ivybridge | 1.1--1.15 |
| Haswell | haswell | 1.1 |
| Broadwell / Skylake | broadwell, skylake | 1.05 |
| Kaby Lake and later | kaby_lake through arrow_lake | 1.0 |
| Apple M1 | m1 | 1.2 |
| Apple M2 | m2 | 1.15 |
| Apple M3 | m3 | 1.1 |
| Apple M4 | m4 | 1.05 |
| RISC-V | riscv, riscv64, riscv32 | 1.4--1.5 |
| Modern Intel/AMD (generic) | modern_intel, modern_amd | 0.8 |
| Modern x86 (default) | modern, x86_64, default, unknown | 0.8 |
| Apple Silicon (generic) | apple_silicon | 0.8 |

#### Penalty Tier

| Architecture | Aliases | Base Multiplier | Rationale |
|-------------|---------|-----------------|-----------|
| Modern ARM | aarch64, arm, armv7, armv7l | 0.0005 | NAS/SBC/phone spam prevention |

### 5.2 Time-Aged Decay Formula

Vintage hardware bonuses decay linearly over the lifetime of the blockchain, converging all architectures toward equal weight over approximately 16.67 years.

**Formula:**

```
aged_multiplier = 1.0 + max(0, (base_multiplier - 1.0) * (1 - DECAY_RATE * chain_age_years))
```

**Constants:**

| Parameter | Value |
|-----------|-------|
| `DECAY_RATE_PER_YEAR` | 0.15 (15% per year) |
| `GENESIS_TIMESTAMP` | 1764706927 (December 2, 2025 -- production chain launch) |

**Behavior:**

- **Year 0:** Full multiplier. G4 = 2.5x, G5 = 2.0x, VAX = 3.5x.
- **Year ~6.67:** All vintage bonuses halved. G4 = 1.75x, G5 = 1.5x.
- **Year ~16.67:** All vintage bonuses fully decayed. Every architecture earns equally.
- **Modern hardware (base <= 1.0):** Never decays. Returns 1.0 always.

**Chain age calculation:**

```python
def get_chain_age_years(current_slot: int) -> float:
    chain_age_seconds = current_slot * BLOCK_TIME  # BLOCK_TIME = 600s
    return chain_age_seconds / (365.25 * 24 * 3600)
```

**Example decay progression (G4 at 2.5x base):**

| Chain Age (years) | Aged Multiplier | Reward Share vs Modern |
|-------------------|-----------------|----------------------|
| 0 | 2.500x | 3.13x |
| 1 | 2.275x | 2.84x |
| 5 | 1.375x | 1.72x |
| 10 | 1.000x | 1.00x (equal) |
| 16.67 | 1.000x | 1.00x (floor) |

---

## 6. Consensus: 1 CPU = 1 Vote (RIP-200)

### 6.1 Round-Robin Block Production

Block producer selection is deterministic, not probabilistic:

1. All miners with valid attestation (`ts_ok` within `ATTESTATION_TTL = 86400s`) are sorted alphabetically by miner ID.
2. The designated producer for slot `S` is `attested_miners[S % len(attested_miners)]`.
3. Each miner gets exactly one turn per rotation cycle.
4. No lottery, no VRF, no randomness in producer selection.

```python
def get_round_robin_producer(slot: int, attested_miners: list) -> str:
    if not attested_miners:
        return None
    producer_index = slot % len(attested_miners)
    return attested_miners[producer_index][0]
```

### 6.2 Epoch Settlement

An epoch consists of 144 consecutive slots (144 x 600s = 86,400s = 24 hours).

**Per-epoch reward:** 1.5 RTC (`PER_EPOCH_URTC = 1,500,000 uRTC`; `UNIT = 1,000,000 uRTC per RTC`).

**Distribution algorithm:**

1. Query all miners with valid attestation during the epoch window.
2. For each miner, compute the time-aged multiplier based on their verified `device_arch`.
3. Miners with `fingerprint_passed = 0` receive weight `0.0` (zero rewards).
4. Sum all weights to get `total_weight`.
5. Each miner receives `(weight / total_weight) * PER_EPOCH_URTC` in uRTC.
6. The last miner in the list receives the remainder to prevent rounding errors.
7. Rewards are credited to `balances` and logged in `epoch_rewards`.

```python
def calculate_epoch_rewards_time_aged(db_path, epoch, total_reward_urtc, current_slot):
    chain_age_years = get_chain_age_years(current_slot)
    # ... query epoch miners ...
    for miner_id, device_arch, fingerprint_ok in epoch_miners:
        if fingerprint_ok == 0:
            weight = 0.0  # STRICT: No rewards for failed fingerprint
        else:
            weight = get_time_aged_multiplier(device_arch, chain_age_years)
        weighted_miners.append((miner_id, weight))
        total_weight += weight
    # ... distribute proportionally ...
```

### 6.3 Enrollment

Miners are auto-enrolled for the current epoch upon successful attestation. The enrollment weight equals their time-aged multiplier (or `0.000000001` for VM-detected miners).

**Enrollment requirements:**
- Valid attestation within `ENROLL_TICKET_TTL_S` (default 600s).
- At least one MAC address recorded.
- MAC address churn below `MAC_MAX_UNIQUE_PER_DAY` (default 3).
- OUI (MAC vendor prefix) not on the VM denylist.

---

## 7. Ergo Anchor Integration

### 7.1 Purpose

Periodically, the RustChain network anchors its attestation state to the Ergo blockchain, creating an immutable record that can be independently verified.

### 7.2 Anchor Transaction Format

Each anchor transaction uses Ergo box registers to store:

| Register | Content | Type |
|----------|---------|------|
| R4 | Blake2b256 commitment hash of miner attestation data | 32 bytes |
| R5 | Miner count | Integer |
| R6 | Miner IDs (pipe-separated) | String |
| R7 | Device architectures | String |
| R8 | RustChain slot height | Integer |
| R9 | Timestamp | Integer |

### 7.3 Commitment Computation

```python
def compute_commitment(miners):
    data = json.dumps(miners, sort_keys=True).encode()
    return blake2b(data, digest_size=32).hexdigest()
```

### 7.4 Transaction Parameters

| Parameter | Value |
|-----------|-------|
| Fee | 0 ERG (zero-fee enabled on private chain via `minimalFeeAmount = 0`) |
| Box value | 0.001 ERG minimum |
| Network | Custom private Ergo chain (addressPrefix=32) |
| Signing | Via Ergo wallet API `/wallet/transaction/sign` with `inputsRaw` |

### 7.5 Anchor Database Record

```sql
CREATE TABLE ergo_anchors (
    id INTEGER PRIMARY KEY,
    tx_id TEXT NOT NULL,
    commitment TEXT NOT NULL,
    miner_count INTEGER,
    created_at INTEGER NOT NULL
);
```

---

## 8. Database Schema

### 8.1 Core Attestation Tables

```sql
-- Current attestation state (one row per miner)
CREATE TABLE miner_attest_recent (
    miner TEXT PRIMARY KEY,
    ts_ok INTEGER NOT NULL,
    device_family TEXT,
    device_arch TEXT,
    entropy_score REAL DEFAULT 0.0,
    fingerprint_passed INTEGER DEFAULT 0,
    source_ip TEXT
);

-- Epoch enrollment (one row per miner per epoch)
CREATE TABLE epoch_enroll (
    epoch INTEGER,
    miner_pk TEXT,
    weight REAL,
    PRIMARY KEY (epoch, miner_pk)
);

-- Epoch settlement records
CREATE TABLE epoch_state (
    epoch INTEGER PRIMARY KEY,
    settled INTEGER DEFAULT 0
);

-- Per-miner rewards per epoch
CREATE TABLE epoch_rewards (
    epoch INTEGER,
    miner_pk TEXT,
    reward_urtc INTEGER,
    PRIMARY KEY (epoch, miner_pk)
);

-- RTC balances
CREATE TABLE balances (
    miner_pk TEXT PRIMARY KEY,
    balance_rtc INTEGER DEFAULT 0
);

-- Full transaction ledger
CREATE TABLE ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    epoch INTEGER,
    miner_pk TEXT,
    amount_urtc INTEGER,
    ts INTEGER
);

-- Hardware bindings (prevent wallet hopping)
CREATE TABLE hardware_bindings (
    hardware_id TEXT PRIMARY KEY,
    miner TEXT NOT NULL,
    bound_at INTEGER NOT NULL
);

-- Fingerprint temporal history (drift detection)
CREATE TABLE miner_fingerprint_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    miner TEXT NOT NULL,
    ts INTEGER NOT NULL,
    profile_json TEXT NOT NULL
);
```

### 8.2 Temporal Drift Bands

The server tracks fingerprint history over time and flags anomalies when a miner's measurements drift outside expected bands:

| Metric | Low Bound | High Bound |
|--------|-----------|------------|
| `clock_drift_cv` | 0.0005 | 0.35 |
| `thermal_variance` | 0.05 | 25.0 |
| `jitter_cv` | 0.0001 | 0.50 |
| `cache_hierarchy_ratio` | 1.10 | 20.0 |

---

## 9. Security Considerations

### 9.1 Threat Model

| Threat | Mitigation |
|--------|-----------|
| **VM farming:** Attacker runs N virtual machines, each claiming to be a separate miner. | Anti-emulation check (3.7) detects all major hypervisors and cloud providers. VM miners receive 0.000000001x weight. |
| **Emulator spoofing:** Attacker runs SheepShaver/QEMU claiming PowerPC G4 for 2.5x multiplier. | ROM clustering (3.8) detects shared ROM dumps. SIMD cross-validation catches SSE/AVX on claimed PowerPC. derive_verified_device() overrides architecture. |
| **Cloud mining:** Attacker spins up AWS/GCP/Azure instances. | Cloud metadata endpoint detection. DMI string matching for all major cloud providers. |
| **Architecture inflation:** Attacker claims exotic architecture (VAX 3.5x) on modern hardware. | Device-age oracle (3.6) cross-validates CPU model vs claimed arch. SIMD evidence must match. |
| **Timing replay:** Attacker records and replays a real machine's fingerprint data. | Temporal drift tracking detects static fingerprints. Real hardware shows natural drift over time. MAC hash uses epoch-scoped salt. |
| **Wallet hopping:** Attacker registers multiple wallets from one machine. | Hardware binding table maps hardware_id to wallet. MAC-based unique counting limits 3 unique MACs per 24 hours. |
| **Container evasion:** Attacker uses Docker/LXC to isolate miners. | Environment variable checks for DOCKER/KUBERNETES/container. Cgroup and root overlay detection. |
| **Self-reported trust:** Client says all checks passed but submits fake data. | Server re-validates all raw data. Client `passed` field is ignored. Missing raw evidence = automatic failure. |

### 9.2 Known Limitations

1. **Python timing resolution:** Python's `time.perf_counter_ns()` has limited precision on some platforms. Extremely old Python versions (< 3.7) lack this function entirely. The server degrades gracefully for legacy miners.

2. **Bare-metal hypervisors:** Type-1 hypervisors with custom firmware and no DMI strings could theoretically evade detection. Jitter uniformity and time dilation checks provide secondary defense.

3. **FPGA/ASIC spoofing:** A purpose-built FPGA could theoretically reproduce real hardware jitter patterns. This attack is uneconomical at RustChain's scale (1.5 RTC per epoch).

4. **ROM check coverage:** The known emulator ROM database covers Amiga, Mac 68K, and Mac PPC. Other retro platforms (Atari ST, C64, MSX) have placeholder entries. Community contributions expand coverage.

### 9.3 Fail-Closed Design

- Missing fingerprint data = validation failure.
- Missing ROM check module for retro platforms = `sys.exit(1)` (fail-closed, not silently pass).
- Unknown device architecture = `default` multiplier (0.8x), not maximum.
- Server errors during validation = rejection, not acceptance.

---

## 10. Pico Serial Bridge Attestation (RIP-304 Extension)

For retro game consoles (NES, SNES, Genesis, Game Boy, PlayStation, etc.) that cannot run the standard miner client, RIP-304 defines a Raspberry Pi Pico-based serial bridge that reads hardware signals directly from the console's controller port and data bus.

**Bridge Checks:**

| Check | Threshold | Rationale |
|-------|-----------|-----------|
| Controller port timing CV | > 0.0001 | Real controllers have measurable jitter. |
| ROM execution timing | 100ms -- 10s | Too fast = modern CPU; too slow = error. |
| Bus jitter stdev | >= 100 ns | Real hardware buses have measurable noise. |
| Emulator indicators | Empty | No emulator markers in serial stream. |

Console miners that pass Pico bridge attestation are enrolled with the appropriate retro console multiplier (2.0x -- 2.8x depending on the console).

---

## 11. Reference Implementation

| Component | File | Location |
|-----------|------|----------|
| Client fingerprint checks (7+1 checks) | `fingerprint_checks.py` | `Rustchain/node/`, `Rustchain/miners/linux/` |
| Extended hardware fingerprinting class | `hardware_fingerprint.py` | `Rustchain/node/` |
| RIP-200 multipliers and epoch rewards | `rip_200_round_robin_1cpu1vote.py` | `Rustchain/node/` |
| Known emulator ROM database | `rom_fingerprint_db.py` | `Rustchain/node/` |
| Server-side ROM clustering | `rom_clustering_server.py` | `Rustchain/node/` |
| Main attestation node | `rustchain_v2_integrated_v2.2.1_rip200.py` | `Rustchain/node/` |
| Epoch settlement | `rewards_implementation_rip200.py` | `Rustchain/node/` |
| Ergo anchor | `ergo_miner_anchor.py` | `Rustchain/node/` |
| Linux miner client | `rustchain_linux_miner.py` | `Rustchain/miners/linux/` |

### Running Fingerprint Checks Standalone

```bash
python3 fingerprint_checks.py
```

Output:

```
Running 8 Hardware Fingerprint Checks...
==================================================

[1/8] Clock-Skew & Oscillator Drift...
  Result: PASS
[2/8] Cache Timing Fingerprint...
  Result: PASS
[3/8] SIMD Unit Identity...
  Result: PASS
[4/8] Thermal Drift Entropy...
  Result: PASS
[5/8] Instruction Path Jitter...
  Result: PASS
[6/8] Device-Age Oracle Fields...
  Result: PASS
[7/8] Anti-Emulation Checks...
  Result: PASS
[8/8] ROM Fingerprint (Retro)...
  Result: PASS (or skipped for modern hardware)

==================================================
OVERALL RESULT: ALL CHECKS PASSED
```

---

## 12. Protocol Constants Summary

| Constant | Value | Description |
|----------|-------|-------------|
| `BLOCK_TIME` | 600 seconds (10 min) | Slot duration |
| `BLOCKS_PER_EPOCH` | 144 | Slots per epoch (= 24 hours) |
| `PER_EPOCH_URTC` | 1,500,000 | Micro-RTC distributed per epoch (= 1.5 RTC) |
| `UNIT` | 1,000,000 | Micro-RTC per 1 RTC |
| `ATTESTATION_TTL` | 86,400 seconds (24h) | How long an attestation remains valid |
| `GENESIS_TIMESTAMP` | 1764706927 | Unix timestamp of production chain launch (Dec 2, 2025) |
| `DECAY_RATE_PER_YEAR` | 0.15 | Annual antiquity bonus decay rate |
| `ENROLL_TICKET_TTL_S` | 600 seconds (10 min) | Freshness requirement for enrollment |
| `MAC_MAX_UNIQUE_PER_DAY` | 3 | Maximum unique MAC addresses per miner per day |
| `ROM_CLUSTER_THRESHOLD` | 2 | Miners sharing a ROM hash before flagging |
| `CV_MIN_THRESHOLD` | 0.0001 | Minimum coefficient of variation for clock drift |
| `JITTER_CV_MIN` | 0.01 | Minimum jitter CV for anti-emulation |
| `SLEEP_DILATION_MAX_NS` | 5,000,000 | Maximum acceptable 1ms sleep actual duration |
| `CACHE_RATIO_MIN` | 1.01 | Minimum L2/L1 and L3/L2 latency ratio |
| `PICO_BRIDGE_CV_MIN` | 0.0001 | Minimum controller port timing CV |
| `PICO_ROM_TIME_RANGE` | 100,000 -- 10,000,000 us | Valid ROM hash execution time window |
| `PICO_JITTER_STDEV_MIN` | 100 ns | Minimum bus jitter standard deviation |

---

## Appendix A: Changelog

| Date | Change |
|------|--------|
| 2025-12-02 | Initial implementation of checks 1--5 and anti-emulation. |
| 2025-12-03 | GENESIS_TIMESTAMP corrected to production chain launch. |
| 2025-12-05 | RIP-PoA Phase 2: Server-side validation, strict enforcement (weight=0 for failed fingerprint). |
| 2025-12-05 | ROM fingerprint database created (61 known emulator ROMs). |
| 2025-12-06 | Device-Age Oracle (check 6) added. Health endpoint fix. |
| 2025-12-20 | Hardware ID collision fix. Wallet transfer security. |
| 2026-02-02 | Hardened validate_fingerprint_data: requires raw evidence, rejects client-reported pass/fail. |
| 2026-02-21 | Cloud provider detection added to anti-emulation (AWS, GCP, Azure, etc.). |
| 2026-03-04 | Admin key rotation. Ed25519 miner signatures. |
| 2026-03-08 | Security audit v3.0: Container detection, SIMD hardening, TLS cert pinning. |
| 2026-03-19 | Expanded multiplier table: 150+ architectures including retro consoles and exotic CPUs. |
| 2026-03-24 | This specification document (v1.0). |

---

## Appendix B: Glossary

| Term | Definition |
|------|-----------|
| **Antiquity multiplier** | Reward weight factor based on hardware age. Ranges from 0.0005x (modern ARM) to 4.0x (ARM2). |
| **Attestation** | The process of proving hardware identity to the network. |
| **CV (Coefficient of Variation)** | Standard deviation divided by mean. Measures relative variability. |
| **Epoch** | 144 consecutive slots (24 hours). The settlement period for reward distribution. |
| **Fingerprint** | A set of hardware measurements that uniquely identify a physical CPU. |
| **ROM clustering** | Detection of multiple miners reporting identical firmware hashes, indicating shared emulator ROM packs. |
| **RTC** | RustChain Token. The native reward currency. 1 RTC = 1,000,000 uRTC. |
| **Slot** | A 600-second (10-minute) time window in which one miner produces a block. |
| **Time-aged decay** | The linear reduction of vintage hardware bonuses over the blockchain's lifetime. |
| **uRTC** | Micro-RTC. The smallest unit of RTC (one millionth). |

---

*This document is part of the RustChain protocol specification. The reference implementation is MIT-licensed and maintained at https://github.com/Scottcjn/Rustchain.*
