# RustChain CPU Antiquity Multiplier System

## Overview

The RustChain cryptocurrency implements a **Proof-of-Antiquity (PoA)** reward system that incentivizes preservation and operation of vintage computing hardware. Older CPUs receive higher mining reward multipliers, with time-based decay to reward early adopters.

This document provides comprehensive CPU generation detection patterns and antiquity multipliers for Intel, AMD, PowerPC, and Apple Silicon architectures from 2000-2025.

## Key Principles

1. **Vintage Hardware Premium** - Older CPUs (pre-2010) get higher base multipliers
2. **Time Decay** - Vintage bonuses decay 15% per year to reward early adoption
3. **Loyalty Bonus** - Modern CPUs (post-2019) earn 15% bonus per year of uptime
4. **Server Bonus** - Enterprise-class hardware gets +10% multiplier
5. **1 CPU = 1 Vote** - Fair distribution based on hardware, not money

## Multiplier Ranges

| Era | Base Multiplier | Example CPUs |
|-----|-----------------|--------------|
| PowerPC (2001-2006) | 1.8x - 2.5x | G4 (2.5x), G5 (2.0x) |
| Vintage x86 (2000-2008) | 1.3x - 1.5x | Pentium 4, Core 2, Athlon 64 |
| Classic (2008-2013) | 1.1x - 1.3x | Nehalem, Sandy Bridge, Phenom II |
| Mid-range (2014-2019) | 1.0x - 1.1x | Haswell, Skylake, Zen/Zen+ |
| Modern (2020-2025) | 1.0x - 1.5x | Zen3/4/5, Alder Lake (loyalty bonus) |
| Apple Silicon | 1.05x - 1.2x | M1 (1.2x), M2 (1.15x), M3 (1.1x), M4 (1.05x) |

## Time Decay Formula

**Vintage Hardware (>5 years old):**
```python
decay_factor = 1.0 - (0.15 * (age - 5) / 5.0)
final_multiplier = 1.0 + (vintage_bonus * decay_factor)
```

**Example**: PowerPC G4 (base 2.5x, age 24 years)
- Vintage bonus: 1.5x (2.5 - 1.0)
- Age beyond 5 years: 19 years
- Decay: 1.0 - (0.15 × 19/5) = 1.0 - 0.57 = 0.43
- Final: 1.0 + (1.5 × 0.43) = **1.645x**

## Loyalty Bonus Formula

**Modern Hardware (≤5 years old):**
```python
loyalty_bonus = min(0.5, uptime_years * 0.15)  # Capped at +50%
final_multiplier = base + loyalty_bonus  # Max 1.5x total
```

**Example**: AMD Ryzen 9 7950X (base 1.0x)
- 0 years uptime: 1.0x
- 1 year uptime: 1.15x
- 3 years uptime: 1.45x
- 5+ years uptime: 1.5x (capped)

## Intel CPU Generations (2000-2025)

### NetBurst Era (2000-2006) - Base: 1.5x

| Architecture | Years | Model Patterns | Examples |
|--------------|-------|----------------|----------|
| Pentium 4 | 2000-2006 | `Pentium(R) 4`, `P4` | Pentium 4 3.0GHz |
| Pentium D | 2005-2006 | `Pentium(R) D` | Pentium D 805 |

### Core 2 Era (2006-2008) - Base: 1.3x

| Architecture | Years | Model Patterns | Examples |
|--------------|-------|----------------|----------|
| Core 2 | 2006-2008 | `Core(TM)2`, `Core 2 Duo/Quad` | Core 2 Duo E8400, Core 2 Quad Q6600 |

### Nehalem/Westmere (2008-2011) - Base: 1.2x

| Architecture | Years | Model Patterns | Examples |
|--------------|-------|----------------|----------|
| Nehalem | 2008-2010 | `i[3579]-[789]\d{2}`, `Xeon.*[EWX]55\d{2}` | i7-920, Xeon X5570 |
| Westmere | 2010-2011 | `i[3579]-[89]\d{2}`, `Xeon.*[EWX]56\d{2}` | i7-980X, Xeon X5675 |

### Sandy Bridge (2011-2012) - Base: 1.1x

**Detection Pattern**: `i[3579]-2\d{3}` or `E3-12\d{2}` (no v-suffix)

| Model Family | Examples |
|--------------|----------|
| Core i3/i5/i7 | i7-2600K, i5-2500K, i3-2120 |
| Xeon E3-1200 | E3-1230, E3-1270 |
| Xeon E5-1600/2600 | E5-1650, E5-2670 |

### Ivy Bridge (2012-2013) - Base: 1.1x

**Detection Pattern**: `i[3579]-3\d{3}` or `v2` suffix on Xeon

| Model Family | Examples |
|--------------|----------|
| Core i3/i5/i7 | i7-3770K, i5-3570K, i3-3220 |
| Xeon E3-1200 v2 | E3-1230 v2, E3-1270 v2 |
| Xeon E5 v2 | E5-1650 v2, E5-2670 v2 |
| Xeon E7 v2 | E7-4870 v2, E7-8870 v2 |

### Haswell (2013-2015) - Base: 1.1x

**Detection Pattern**: `i[3579]-4\d{3}` or `v3` suffix on Xeon

| Model Family | Examples |
|--------------|----------|
| Core i3/i5/i7 | i7-4770K, i5-4590, i3-4130 |
| Xeon E3-1200 v3 | E3-1230 v3, E3-1231 v3 |
| Xeon E5 v3 | E5-1650 v3, E5-2680 v3 |

### Broadwell (2014-2015) - Base: 1.05x

**Detection Pattern**: `i[3579]-5\d{3}` or `v4` suffix on Xeon

| Model Family | Examples |
|--------------|----------|
| Core i5/i7 | i7-5775C, i5-5675C (rare desktop) |
| Xeon E3-1200 v4 | E3-1240 v4, E3-1280 v4 |
| Xeon E5 v4 | E5-2680 v4, E5-2699 v4 |

### Skylake (2015-2017) - Base: 1.05x

**Detection Pattern**: `i[3579]-6\d{3}` or Xeon Scalable 1st-gen (no letter suffix)

| Model Family | Examples |
|--------------|----------|
| Core i3/i5/i7 | i7-6700K, i5-6600K, i3-6100 |
| Xeon E3-1200 v5/v6 | E3-1230 v5, E3-1270 v6 |
| Xeon Scalable 1st | Platinum 8180, Gold 6148 |

### Kaby Lake (2016-2018) - Base: 1.0x

**Detection Pattern**: `i[3579]-7\d{3}`

| Model Family | Examples |
|--------------|----------|
| Core i3/i5/i7 | i7-7700K, i5-7600K, i3-7100 |

### Coffee Lake (2017-2019) - Base: 1.0x

**Detection Pattern**: `i[3579]-[89]\d{3}`

| Model Family | Examples |
|--------------|----------|
| Core i3/i5/i7 (8th-gen) | i7-8700K, i5-8400, i3-8100 |
| Core i5/i7/i9 (9th-gen) | i9-9900K, i7-9700K, i5-9600K |

### Cascade Lake (2019-2020) - Base: 1.0x

**Detection Pattern**: Xeon Scalable 2nd-gen with letter suffix (e.g., `Gold 6248R`)

| Model Family | Examples |
|--------------|----------|
| Xeon Scalable 2nd | Platinum 8280L, Gold 6248R, Silver 4214R |

### Comet Lake (2020) - Base: 1.0x

**Detection Pattern**: `i[3579]-10\d{3}`

| Model Family | Examples |
|--------------|----------|
| Core i3/i5/i7/i9 (10th-gen) | i9-10900K, i7-10700K, i5-10400 |

### Rocket Lake (2021) - Base: 1.0x

**Detection Pattern**: `i[3579]-11\d{3}`

| Model Family | Examples |
|--------------|----------|
| Core i5/i7/i9 (11th-gen) | i9-11900K, i7-11700K, i5-11600K |

### Alder Lake (2021-2022) - Base: 1.0x

**Detection Pattern**: `i[3579]-12\d{3}` or `Core [3579] 12\d{3}`

**Note**: First hybrid architecture with P-cores + E-cores

| Model Family | Examples |
|--------------|----------|
| Core i3/i5/i7/i9 (12th-gen) | i9-12900K, i7-12700K, i5-12600K |
| New naming | Core 9 12900K, Core 7 12700K |

### Raptor Lake (2022-2024) - Base: 1.0x

**Detection Pattern**: `i[3579]-1[34]\d{3}` or `Core [3579] 1[34]\d{3}`

| Model Family | Examples |
|--------------|----------|
| Core i5/i7/i9 (13th-gen) | i9-13900K, i7-13700K, i5-13600K |
| Core i5/i7/i9 (14th-gen) | i9-14900K, i7-14700K, i5-14600K |

### Sapphire Rapids (2023-2024) - Base: 1.0x

**Detection Pattern**: Xeon Scalable 4th-gen with 8xxx/9xxx model numbers

| Model Family | Examples |
|--------------|----------|
| Xeon Scalable 4th | Platinum 8480+, Gold 8468, Silver 8420+ |

### Meteor Lake / Arrow Lake (2023-2025) - Base: 1.0x

**Detection Pattern**: `Core Ultra [579]` or `i[3579]-15\d{3}`

| Model Family | Examples |
|--------------|----------|
| Core Ultra (mobile) | Core Ultra 9 185H, Core Ultra 7 155H |
| Arrow Lake (desktop) | Core Ultra 9 285K, Core Ultra 7 265K |

## AMD CPU Generations (1999-2025)

### K7 Era (1999-2005) - Base: 1.5x

| Architecture | Years | Model Patterns | Examples |
|--------------|-------|----------------|----------|
| Athlon/Duron | 1999-2005 | `Athlon(tm)`, `Athlon XP`, `Duron` | Athlon XP 2400+, Duron 1.3GHz |
| Athlon 64 X2 | 2005 | `Athlon 64 X2` | Athlon 64 X2 4200+ |

### K8 Era (2003-2007) - Base: 1.5x

| Architecture | Years | Model Patterns | Examples |
|--------------|-------|----------------|----------|
| Athlon 64 | 2003-2007 | `Athlon(tm) 64`, `Athlon 64` | Athlon 64 3200+ |
| Opteron | 2003-2007 | `Opteron(tm)` | Opteron 250, Opteron 2384 |
| Turion 64 | 2005-2007 | `Turion 64` | Turion 64 ML-32 |

### K10 Era (2007-2011) - Base: 1.4x

| Architecture | Years | Model Patterns | Examples |
|--------------|-------|----------------|----------|
| Phenom | 2007-2009 | `Phenom` (no II) | Phenom X4 9950 |
| Phenom II | 2009-2011 | `Phenom II` | Phenom II X6 1090T, X4 965 |
| Athlon II | 2009-2011 | `Athlon II` | Athlon II X4 640 |

### Bulldozer Family (2011-2016)

| Architecture | Years | Model Patterns | Base | Examples |
|--------------|-------|----------------|------|----------|
| Bulldozer | 2011-2012 | `FX-\d{4}` (no suffix) | 1.3x | FX-8150, FX-6100 |
| Piledriver | 2012-2014 | `FX-\d{4}[A-Z]` | 1.3x | FX-8350, FX-6300 |
| Steamroller | 2014-2015 | `A[468]-\d{4}` | 1.2x | A10-7850K, A8-7600 |
| Excavator | 2015-2016 | `A[468]-\d{4}[A-Z]` | 1.2x | A12-9800, A10-9700 |

### Zen Era (2017-present)

| Architecture | Years | Model Patterns | Base | Examples |
|--------------|-------|----------------|------|----------|
| Zen | 2017-2018 | `Ryzen [3579] 1\d{3}`, `EPYC 7[0-2]\d{2}` | 1.1x | Ryzen 7 1700X, EPYC 7551 |
| Zen+ | 2018-2019 | `Ryzen [3579] 2\d{3}` | 1.1x | Ryzen 7 2700X, Ryzen 5 2600 |
| Zen 2 | 2019-2020 | `Ryzen [3579] 3\d{3}`, `EPYC 7[2-4]\d{2}` | 1.05x | Ryzen 9 3900X, EPYC 7742 |
| Zen 3 | 2020-2022 | `Ryzen [3579] 5\d{3}`, `EPYC 7[3-5]\d{2}` | 1.0x | Ryzen 9 5950X, EPYC 7763 |
| Zen 4 | 2022-2024 | `Ryzen [3579] [78]\d{3}`, `EPYC [89]\d{3}` | 1.0x | Ryzen 9 7950X, EPYC 9654 |
| Zen 5 | 2024-2025 | `Ryzen [3579] 9\d{3}`, `EPYC 9[5-9]\d{2}` | 1.0x | Ryzen 9 9950X, EPYC 9754 |

**Note**: Ryzen 8000 series (e.g., 8645HS) are mobile Zen4 chips, not a separate generation.

## PowerPC Architectures (1997-2006) - Highest Multipliers

| Architecture | Years | Model Patterns | Base | Examples |
|--------------|-------|----------------|------|----------|
| G3 | 1997-2003 | `750`, `PowerPC G3` | 1.8x | iMac G3, PowerBook G3 |
| G4 | 2001-2005 | `7450`, `7447`, `7455`, `PowerPC G4` | **2.5x** | Power Mac G4, PowerBook G4 |
| G5 | 2003-2006 | `970`, `PowerPC G5` | 2.0x | Power Mac G5, iMac G5 |

**Detection**: Read `/proc/cpuinfo` for PowerPC-specific model numbers.

## Apple Silicon (2020-2025) - Premium Modern

| Architecture | Years | Model Patterns | Base | Examples |
|--------------|-------|----------------|------|----------|
| M1 | 2020-2021 | `Apple M1` | 1.2x | MacBook Air M1, Mac mini M1 |
| M2 | 2022-2023 | `Apple M2` | 1.15x | MacBook Air M2, Mac mini M2 |
| M3 | 2023-2024 | `Apple M3` | 1.1x | MacBook Pro M3, iMac M3 |
| M4 | 2024-2025 | `Apple M4` | 1.05x | Mac mini M4, MacBook Pro M4 |

**Detection**: Use `sysctl -n machdep.cpu.brand_string` on macOS.

## Server Hardware Bonus

Enterprise-class CPUs receive a **+10% multiplier** on top of base:

| Vendor | Server Patterns | Examples |
|--------|----------------|----------|
| Intel | `Xeon` | Xeon E5-2670 v2, Xeon Gold 6248R |
| AMD | `EPYC`, `Opteron` | EPYC 7742, Opteron 6276 |

**Example**: Xeon E5-1650 v2 (Ivy Bridge)
- Base: 1.1x (Ivy Bridge)
- With time decay (13 years old): ~1.076x
- Server bonus: 1.076 × 1.1 = **1.18x final**

## Detection Implementation

### Python Example

```python
from cpu_architecture_detection import calculate_antiquity_multiplier

# Detect from brand string
brand = "Intel(R) Xeon(R) CPU E5-1650 v2 @ 3.50GHz"
info = calculate_antiquity_multiplier(brand)

print(f"Architecture: {info.architecture}")
print(f"Generation: {info.generation}")
print(f"Year: {info.microarch_year}")
print(f"Server: {info.is_server}")
print(f"Multiplier: {info.antiquity_multiplier}x")
```

**Output**:
```
Architecture: ivy_bridge
Generation: Intel Ivy Bridge (3rd-gen Core i)
Year: 2012
Server: True
Multiplier: 1.1836x
```

### Regex Patterns

**Intel Core i-series generation detection**:
```regex
i[3579]-(\d+)\d{2,3}  # Capture first 1-2 digits = generation
```
- `i7-2600K` → 2 → 2nd-gen (Sandy Bridge)
- `i9-12900K` → 12 → 12th-gen (Alder Lake)

**Intel Xeon E3/E5/E7 version detection**:
```regex
E[357]-\d+\s*v([2-6])  # Capture v-number
```
- `E5-1650` (no v) → Sandy Bridge
- `E5-1650 v2` → Ivy Bridge
- `E5-2680 v4` → Broadwell

**AMD Ryzen generation detection**:
```regex
Ryzen\s*[3579]\s*(\d)\d{3}  # Capture first digit = series
```
- `Ryzen 7 1700X` → 1 → Zen
- `Ryzen 9 5950X` → 5 → Zen 3
- `Ryzen 9 9950X` → 9 → Zen 5

## Special Cases & Quirks

### Intel Naming Changes (2023+)

Intel dropped the "i" prefix for 2023+ CPUs:
- Old: `Core i7-12700K`
- New: `Core 7 12700K` or `Core Ultra 9 285K`

**Detection**: Match both patterns:
```regex
(Core\(TM\)\s*i[3579]|Core\(TM\)\s*[3579])-(\d+)
```

### AMD Ryzen Mobile Quirks

Ryzen 8000 series (e.g., `Ryzen 5 8645HS`) are mobile Zen4, NOT Zen5:
- Pattern: `Ryzen [3579] 8\d{3}` → Zen4 (2023)
- Next mobile: `Ryzen AI 300` series (Zen5)

### AMD APU Naming

APU series numbers are ahead of CPU series:
- Ryzen 7 7840HS (APU, Zen4) ≠ Ryzen 7 7700X (CPU, Zen4)
- Both are Zen4 despite naming confusion

### Xeon Scalable Naming

| Generation | Model Pattern | Examples |
|------------|---------------|----------|
| 1st-gen | `\d{4}` (no suffix) | Platinum 8180, Gold 6148 |
| 2nd-gen | `\d{4}[A-Z]` (letter suffix) | Platinum 8280L, Gold 6248R |
| 3rd-gen | `\d{4}[A-Z]?` (mixed) | Platinum 8380, Gold 6338 |
| 4th-gen | `[89]\d{3}` (8xxx/9xxx) | Platinum 8480+, Gold 8468 |

## Integration with RustChain

### Miner Client

```python
import platform
import subprocess

def get_cpu_brand():
    if platform.system() == "Darwin":  # macOS
        return subprocess.check_output(
            ["sysctl", "-n", "machdep.cpu.brand_string"]
        ).decode().strip()
    elif platform.system() == "Linux":
        with open("/proc/cpuinfo") as f:
            for line in f:
                if "model name" in line or "cpu model" in line:
                    return line.split(":")[1].strip()
    elif platform.system() == "Windows":
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0"
        )
        return winreg.QueryValueEx(key, "ProcessorNameString")[0]
    return "Unknown"

# Use in attestation
from cpu_architecture_detection import calculate_antiquity_multiplier

cpu_info = calculate_antiquity_multiplier(get_cpu_brand())
attestation = {
    "miner_id": wallet_address,
    "cpu_architecture": cpu_info.architecture,
    "cpu_generation": cpu_info.generation,
    "cpu_year": cpu_info.microarch_year,
    "is_server": cpu_info.is_server,
    "antiquity_multiplier": cpu_info.antiquity_multiplier,
    # ... other attestation data
}
```

### Server-Side Reward Calculation

```python
def calculate_epoch_rewards(db_path: str, total_rtc: float) -> dict:
    """
    Calculate rewards with CPU antiquity multipliers
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all active miners with attestations
    cursor.execute("""
        SELECT miner_id, cpu_brand, uptime_years
        FROM miner_attest_recent
        WHERE ts_ok > ?
    """, (time.time() - ATTESTATION_TTL,))

    miners = cursor.fetchall()
    total_weight = 0
    miner_weights = {}

    for miner_id, cpu_brand, uptime_years in miners:
        # Calculate antiquity multiplier
        cpu_info = calculate_antiquity_multiplier(cpu_brand, loyalty_years=uptime_years)
        weight = cpu_info.antiquity_multiplier

        miner_weights[miner_id] = weight
        total_weight += weight

    # Distribute rewards proportionally
    rewards = {}
    for miner_id, weight in miner_weights.items():
        share = weight / total_weight
        rewards[miner_id] = total_rtc * share

    return rewards
```

## Testing & Validation

Run the demo script to verify detection:

```bash
cd /home/scott/rustchain-complete
python3 cpu_architecture_detection.py
```

**Expected Output**:
```
================================================================================
CPU ARCHITECTURE DETECTION & ANTIQUITY MULTIPLIER DEMO
================================================================================

CPU: Intel(R) Xeon(R) CPU E5-1650 v2 @ 3.50GHz
  → Vendor: INTEL
  → Architecture: ivy_bridge
  → Generation: Intel Ivy Bridge (3rd-gen Core i)
  → Year: 2012 (Age: 13 years)
  → Server: Yes
  → Antiquity Multiplier: 1.1836x

CPU: PowerPC G4 (7450)
  → Vendor: POWERPC
  → Architecture: g4
  → Generation: PowerPC G4 (7450/7447/7455)
  → Year: 2001 (Age: 24 years)
  → Server: No
  → Antiquity Multiplier: 1.645x

CPU: AMD Ryzen 9 7950X 16-Core Processor
  → Vendor: AMD
  → Architecture: zen4
  → Generation: AMD Zen 4 (Ryzen 7000/8000 / EPYC Genoa)
  → Year: 2022 (Age: 3 years)
  → Server: No
  → Antiquity Multiplier: 1.0x
```

## Sources & References

This system is based on extensive research of CPU microarchitecture timelines:

### Intel
- [List of Intel CPU Microarchitectures - Wikipedia](https://en.wikipedia.org/wiki/List_of_Intel_CPU_microarchitectures)
- [Intel Processor Names, Numbers and Generation List](https://www.intel.com/content/www/us/en/processors/processor-numbers.html)
- [List of Intel Xeon Processors - Wikipedia](https://en.wikipedia.org/wiki/List_of_Intel_Xeon_processors)
- [Intel CPU Naming Convention Guide - RenewTech](https://www.renewtech.com/blog/intel-cpu-naming-convention-guide.html)

### AMD
- [List of AMD CPU Microarchitectures - Wikipedia](https://en.wikipedia.org/wiki/List_of_AMD_CPU_microarchitectures)
- [AMD EPYC - Wikipedia](https://en.wikipedia.org/wiki/Epyc)
- [AMD Processor Naming Guide - TechConsumerGuide](https://www.techconsumerguide.com/a-simple-guide-to-amd-ryzen-naming-scheme/)
- [How to Read AMD CPU Names - CyberPowerPC](https://www.cyberpowerpc.com/blog/how-to-read-amd-cpu-names/)

### General
- [Decoding Processor Puzzle: Intel and AMD 2025 Edition - Technical Explore](https://www.technicalexplore.com/tech/decoding-the-processor-puzzle-intel-and-amd-naming-schemes-explained-2025-edition)

## Future Enhancements

1. **Auto-detection of model year** - Parse more granular release dates
2. **CPUID integration** - Use CPUID instruction for more precise detection
3. **ARM server CPUs** - Add Ampere Altra, AWS Graviton patterns
4. **RISC-V support** - Prepare for upcoming RISC-V mining
5. **GPU antiquity** - Extend to GPUs (vintage Radeon, GeForce)

---

**Last Updated**: 2025-12-24
**Version**: 1.0.0
**File**: `/home/scott/rustchain-complete/cpu_architecture_detection.py`
