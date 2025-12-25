# Vintage CPU Architecture Integration Guide

## Overview

This guide documents how to integrate extremely vintage CPU architectures (1980s-2000s) into the RustChain RIP-200 antiquity detection system.

## File Structure

```
/home/scott/rustchain-complete/
├── cpu_architecture_detection.py       # Modern CPUs (2000-2025)
├── cpu_vintage_architectures.py        # Vintage CPUs (1979-2003)
└── VINTAGE_CPU_INTEGRATION_GUIDE.md    # This file
```

## Architecture Coverage

### Modern Detection (`cpu_architecture_detection.py`)
- Intel Pentium 4 through Arrow Lake (2000-2025)
- AMD Athlon 64 through Zen 5 (2003-2025)
- PowerPC G3/G4/G5 (1997-2006)
- Apple Silicon M1-M4 (2020-2025)

### Vintage Detection (`cpu_vintage_architectures.py`)
- **Pre-Pentium 4 Intel**: 386, 486, Pentium, Pentium Pro, Pentium II/III
- **Oddball x86**: Cyrix, VIA, Transmeta, IDT WinChip
- **Vintage AMD**: K5, K6 series
- **Motorola 68K**: 68000-68060 (Mac, Amiga)
- **PowerPC Amiga**: AmigaOne, Pegasos, Sam440/460
- **RISC Workstations**: DEC Alpha, Sun SPARC, MIPS, PA-RISC, IBM POWER

## Antiquity Multiplier Scale

| Multiplier | Era | Example CPUs |
|-----------|-----|--------------|
| **3.0x** | Ancient (1979-1989) | 386, 68000, MIPS R2000 |
| **2.8-2.9x** | Very Old (1989-1992) | 486, 68010/68020, SPARC v7, POWER1 |
| **2.4-2.7x** | Old (1992-1999) | Pentium, 68040, Alpha 21064, K5, PA-RISC |
| **2.0-2.3x** | Vintage (1999-2005) | Pentium III, 68060, Cyrix, K6, UltraSPARC |
| **1.8-1.9x** | Early Modern (2005-2010) | VIA C7, POWER7, SPARC T1 |
| **1.5x** | Late Modern (2010-2015) | Pentium 4, Athlon 64 |
| **1.0-1.3x** | Recent (2015-2025) | Core 2 through current |

## Integration Pattern

### Step 1: Check Vintage First

```python
from cpu_vintage_architectures import detect_vintage_architecture, get_vintage_description
from cpu_architecture_detection import detect_cpu_architecture, calculate_antiquity_multiplier

def detect_all_architectures(brand_string: str):
    """
    Unified CPU detection - checks vintage first, then modern
    """
    # Try vintage detection first (most distinctive patterns)
    vintage_result = detect_vintage_architecture(brand_string)

    if vintage_result:
        vendor, architecture, year, base_multiplier = vintage_result
        description = get_vintage_description(architecture)
        return {
            "vendor": vendor,
            "architecture": architecture,
            "year": year,
            "base_multiplier": base_multiplier,
            "description": description,
            "is_vintage": True
        }

    # Fall back to modern detection
    cpu_info = calculate_antiquity_multiplier(brand_string)
    return {
        "vendor": cpu_info.vendor,
        "architecture": cpu_info.architecture,
        "year": cpu_info.microarch_year,
        "base_multiplier": cpu_info.antiquity_multiplier,
        "description": cpu_info.generation,
        "is_vintage": False
    }
```

### Step 2: Apply Time Decay

Vintage bonuses decay over time to incentivize early adoption:

```python
def apply_time_decay(base_multiplier: float, cpu_year: int, chain_start_year: int = 2025):
    """
    Apply decay to vintage bonuses

    - Vintage hardware (>5 years old): 15% decay per year
    - Modern hardware (<5 years old): No decay, can earn loyalty bonus
    """
    current_year = 2025  # Or use dynamic year
    hardware_age = current_year - cpu_year

    if hardware_age > 5 and base_multiplier > 1.0:
        # Calculate years since chain genesis
        chain_age = current_year - chain_start_year

        # Decay vintage bonus by 15% per year
        decay_factor = max(0.0, 1.0 - (0.15 * chain_age))
        vintage_bonus = base_multiplier - 1.0
        final_multiplier = 1.0 + (vintage_bonus * decay_factor)

        return final_multiplier

    return base_multiplier
```

## Detection Examples

### Vintage Intel x86

| Input | Detection |
|-------|-----------|
| `"Intel 80386DX @ 33MHz"` | `i386` (1985, 3.0x) |
| `"Intel 80486DX2-66"` | `i486` (1989, 2.8x) |
| `"Intel Pentium 200MHz MMX"` | `pentium_p5` (1993, 2.6x) |
| `"Intel Pentium Pro 200MHz"` | `pentium_pro` (1995, 2.4x) |
| `"Intel(R) Pentium(R) III CPU 1000MHz"` | `pentium_iii` (1999, 2.0x) |

### Oddball x86 Vendors

| Input | Detection |
|-------|-----------|
| `"Cyrix 6x86MX PR200"` | `cyrix_6x86` (1995, 2.5x) |
| `"VIA C3 Samuel 2 800MHz"` | `via_c3` (2001, 1.9x) |
| `"Transmeta Crusoe TM5800"` | `transmeta_crusoe` (2000, 2.1x) |
| `"IDT WinChip C6-240"` | `winchip` (1997, 2.3x) |

### Motorola 68K (Mac/Amiga)

| Input | Detection |
|-------|-----------|
| `"Motorola 68000 @ 8MHz"` | `m68000` (1979, 3.0x) |
| `"MC68020 @ 16MHz"` | `m68020` (1984, 2.8x) |
| `"MC68030 @ 25MHz"` | `m68030` (1987, 2.6x) |
| `"MC68040 @ 33MHz"` | `m68040` (1990, 2.4x) |
| `"MC68060 @ 50MHz"` | `m68060` (1994, 2.2x) |

### RISC Workstations

| Input | Detection |
|-------|-----------|
| `"Alpha 21064 @ 150MHz"` | `alpha_21064` (1992, 2.7x) |
| `"UltraSPARC II @ 300MHz"` | `sparc_v9` (1995, 2.3x) |
| `"MIPS R2000 @ 8MHz"` | `mips_r2000` (1985, 3.0x) |
| `"MIPS R10000 @ 195MHz"` | `mips_r10000` (1996, 2.4x) |
| `"PA-RISC 2.0 PA8500"` | `pa_risc_2.0` (1996, 2.3x) |
| `"IBM POWER4 @ 1.3GHz"` | `power4` (2001, 2.2x) |

## Testing

Run the demo to verify all detections:

```bash
# Test vintage CPU detection
python3 /home/scott/rustchain-complete/cpu_vintage_architectures.py

# Expected output:
# - 50+ vintage CPU detections
# - Multiplier ranking from 3.0x down to 1.7x
# - Years spanning 1979-2012
```

## /proc/cpuinfo Patterns

### Linux Detection

On vintage Linux systems, `/proc/cpuinfo` may show:

**486/Pentium:**
```
model name : Intel 486DX @ 66MHz
cpu family : 4
model      : 8
```

**Pentium II/III:**
```
model name : Intel(R) Pentium(R) III CPU 1000MHz
cpu family : 6
model      : 8
```

**68K (via emulator or real hardware):**
```
cpu : 68040
fpu : 68040
mmu : 68040
```

**MIPS (SGI, embedded):**
```
cpu model : MIPS R5000 Revision 2.1
system type : SGI Indy
```

**SPARC (Sun):**
```
cpu : TI UltraSparc II (BlackBird)
fpu : UltraSparc II integrated FPU
```

**Alpha (DEC):**
```
cpu model : EV56
cpu variation : 7
```

**PA-RISC (HP):**
```
cpu family : PA-RISC 2.0
cpu : PA8500 (PCX-W)
```

## Windows Registry Patterns

On vintage Windows systems, CPU info is in:
```
HKEY_LOCAL_MACHINE\HARDWARE\DESCRIPTION\System\CentralProcessor\0\
  ProcessorNameString
```

Examples:
- `"Intel(R) Pentium(R) III processor"`
- `"AMD K6-2 350MHz"`
- `"Cyrix 6x86MX PR200"`
- `"VIA C3 Samuel 2 800MHz"`

## Mac 68K/PowerPC Detection

On Mac OS (Classic/OS X):
- System Profiler shows: `"Motorola 68040"`, `"PowerPC 750"`, etc.
- Command line: `sysctl hw.model` (OS X)
- Gestalt Manager (Classic OS) returns CPU type codes

## Amiga Detection

On AmigaOS/MorphOS:
- `cpu` command shows: `"68000"`, `"68030"`, `"PPC 7447"`, etc.
- WB Info shows CPU in About window
- Direct hardware registers (0xDFF000+) for 68K detection

## Integration with RustChain Miner

### Miner Client Changes

In `rustchain_universal_miner.py`:

```python
from cpu_vintage_architectures import detect_vintage_architecture
from cpu_architecture_detection import detect_cpu_architecture

def detect_hardware():
    """Enhanced hardware detection with vintage support"""
    brand_string = get_cpu_brand()  # From /proc/cpuinfo or registry

    # Try vintage detection first
    vintage_result = detect_vintage_architecture(brand_string)

    if vintage_result:
        vendor, arch, year, multiplier = vintage_result
        return {
            "device_family": vendor,
            "device_arch": arch,
            "cpu_year": year,
            "expected_multiplier": multiplier,
            "is_vintage": True
        }

    # Fall back to modern detection
    cpu_info = calculate_antiquity_multiplier(brand_string)
    return {
        "device_family": cpu_info.vendor,
        "device_arch": cpu_info.architecture,
        "cpu_year": cpu_info.microarch_year,
        "expected_multiplier": cpu_info.antiquity_multiplier,
        "is_vintage": False
    }
```

### Server-Side Validation

In `rustchain_v2_integrated_v2.2.1_rip200.py`:

```python
from cpu_vintage_architectures import detect_vintage_architecture

def validate_cpu_claim(attestation: dict) -> bool:
    """Validate miner's CPU claim against known architectures"""
    brand_string = attestation.get("device", {}).get("cpu_brand", "")
    claimed_arch = attestation.get("device", {}).get("device_arch", "")

    # Check vintage architectures
    vintage_result = detect_vintage_architecture(brand_string)
    if vintage_result:
        _, detected_arch, _, _ = vintage_result
        return detected_arch == claimed_arch

    # Check modern architectures
    # ... existing modern validation logic
```

## Rare Hardware Priority

The highest multipliers (3.0x) are reserved for:
1. **Intel 386** (1985) - First 32-bit x86
2. **Motorola 68000** (1979) - Original Mac/Amiga
3. **MIPS R2000** (1985) - First commercial RISC

These CPUs are extremely rare in 2025 and deserve maximum preservation incentive.

## Server Load Considerations

Vintage hardware is slow. Adjust mining difficulty:
- **386/486**: `min_difficulty = 0.001` (1000x easier)
- **Pentium/68K**: `min_difficulty = 0.01` (100x easier)
- **RISC workstations**: `min_difficulty = 0.1` (10x easier)

This ensures vintage systems can participate without overheating/failing.

## References

- [Intel CPU Timeline](https://en.wikipedia.org/wiki/List_of_Intel_processors)
- [Motorola 68K Family](https://en.wikipedia.org/wiki/Motorola_68000_series)
- [DEC Alpha](https://en.wikipedia.org/wiki/DEC_Alpha)
- [Sun SPARC](https://en.wikipedia.org/wiki/SPARC)
- [MIPS Architecture](https://en.wikipedia.org/wiki/MIPS_architecture)
- [PA-RISC](https://en.wikipedia.org/wiki/PA-RISC)
- [IBM POWER](https://en.wikipedia.org/wiki/IBM_POWER_microprocessors)
- [Cyrix CPUs](https://en.wikipedia.org/wiki/Cyrix)
- [VIA Technologies](https://en.wikipedia.org/wiki/VIA_Technologies)
- [Transmeta](https://en.wikipedia.org/wiki/Transmeta)

---

**Note**: This system incentivizes preservation of computing history while remaining economically fair through time decay. A 1985 386 gets 3.0x in 2025, but that bonus decays to ~2.25x after 5 years of chain operation.
