# Vintage CPU Architecture Detection for RustChain

## Overview

This package provides comprehensive vintage CPU architecture detection for the RustChain RIP-200 antiquity reward system. It covers **50+ CPU architectures** from 1979-2012, incentivizing preservation of computing history.

## Files in this Package

| File | Purpose |
|------|---------|
| `cpu_vintage_architectures.py` | Core detection module with regex patterns |
| `cpu_architecture_detection.py` | Modern CPU detection (2000-2025) |
| `vintage_cpu_integration_example.py` | Complete integration example |
| `VINTAGE_CPU_INTEGRATION_GUIDE.md` | Detailed integration instructions |
| `VINTAGE_CPU_RESEARCH_SUMMARY.md` | Comprehensive research documentation |
| `VINTAGE_CPU_QUICK_REFERENCE.md` | Quick lookup chart |
| `README_VINTAGE_CPUS.md` | This file |

## Supported Architectures

### Coverage by Era

```
1979-1989  (3.0x)  - Computing Pioneers: 386, 68000, MIPS R2000
1982-1992  (2.8x)  - Early Innovations: 486, 68020, SPARC v7, POWER1
1987-1995  (2.6x)  - Vintage Era: 68030, Pentium, Alpha 21064
1990-2002  (2.4x)  - Late Vintage: 68040, Pentium Pro, AmigaOne
1994-2004  (2.2x)  - Retro Era: Pentium II, K6, Alpha 21264
1999-2007  (2.0x)  - Early Modern: Pentium III, Transmeta, POWER5
2001-2010  (1.8x)  - Late Retro: VIA, UltraSPARC T1, POWER7
```

### Coverage by Platform

- **Intel x86**: 386, 486, Pentium, Pentium Pro, Pentium II/III (1985-2003)
- **AMD x86**: K5, K6 series (1996-1999)
- **Motorola 68K**: 68000-68060 (Mac, Amiga) (1979-2000)
- **PowerPC Amiga**: AmigaOne, Pegasos, Sam440/460 (2002-2012)
- **DEC Alpha**: 21064/21164/21264 (1992-2004)
- **Sun SPARC**: v7/v8/v9, UltraSPARC (1987-2017)
- **MIPS**: R2000-R16000 (SGI workstations) (1985-2004)
- **HP PA-RISC**: 1.0/1.1/2.0 (1986-2008)
- **IBM POWER**: POWER1-POWER7 (pre-POWER8) (1990-2013)
- **Oddball x86**: Cyrix, VIA, Transmeta, IDT WinChip (1992-2011)

## Quick Start

### 1. Basic Detection

```python
from cpu_vintage_architectures import detect_vintage_architecture

# Detect a vintage CPU
result = detect_vintage_architecture("Intel 80386DX @ 33MHz")
if result:
    vendor, architecture, year, multiplier = result
    print(f"{architecture} from {year} → {multiplier}x")
    # Output: i386 from 1985 → 3.0x
```

### 2. Unified Detection (Vintage + Modern)

```python
from vintage_cpu_integration_example import detect_all_cpu_architectures

# Works for both vintage and modern CPUs
cpu_info = detect_all_cpu_architectures("AMD Ryzen 9 7950X")
print(f"{cpu_info['architecture']} → {cpu_info['base_multiplier']}x")
# Output: zen4 → 1.0x
```

### 3. Miner Client Integration

```python
from vintage_cpu_integration_example import detect_hardware_for_miner

# Detect local hardware
hardware = detect_hardware_for_miner()
print(f"CPU: {hardware['cpu_brand']}")
print(f"Architecture: {hardware['device_arch']}")
print(f"Multiplier: {hardware['expected_multiplier']}x")
print(f"Vintage: {hardware['is_vintage']}")
```

### 4. Server-Side Validation

```python
from vintage_cpu_integration_example import validate_cpu_claim

# Validate miner's CPU claim
attestation = {
    "device": {
        "cpu_brand": "Intel 80386DX @ 33MHz",
        "device_arch": "i386",
        "expected_multiplier": 3.0
    }
}

is_valid, reason, arch, mult = validate_cpu_claim(attestation)
print(f"Valid: {is_valid} ({reason})")
# Output: Valid: True (valid)
```

## Multiplier Examples

| CPU | Year | Multiplier | Description |
|-----|------|------------|-------------|
| Intel 386 | 1985 | **3.0x** | Ancient x86, first 32-bit |
| Motorola 68000 | 1979 | **3.0x** | Original Mac/Amiga |
| MIPS R2000 | 1985 | **3.0x** | First commercial RISC |
| Intel 486 | 1989 | **2.8x** | Early pipelined x86 |
| Pentium | 1993 | **2.6x** | Superscalar x86 |
| DEC Alpha 21064 | 1992 | **2.7x** | Fastest CPU of 1990s |
| Cyrix 6x86 | 1995 | **2.5x** | Budget Pentium competitor |
| Pentium III | 1999 | **2.0x** | Last pre-NetBurst Intel |
| AMD K6-2 | 1997 | **2.2x** | 3DNow! era |
| VIA C3 | 2001 | **1.9x** | Low-power x86 |

## Time Decay

Vintage bonuses decay 15% per year of blockchain operation:

```python
from vintage_cpu_integration_example import apply_time_decay

# 386 starts at 3.0x
base = 3.0
year = 1985

# After 5 years of chain operation:
decayed = apply_time_decay(base, year)
# → ~1.5x (50% of original bonus decayed)

# After 10 years:
# → 1.0x (full decay)
```

**Rationale**: Incentivizes early adoption while preventing indefinite advantage.

## Difficulty Adjustment

Vintage hardware is slow and may overheat. Difficulty is reduced by age:

| CPU Age | Difficulty Reduction | Example |
|---------|---------------------|---------|
| 0-10 years | None (1x) | Modern CPUs |
| 11-15 years | 10x easier | Pentium 4 era |
| 16-20 years | 100x easier | Pentium III |
| 21-25 years | 1000x easier | 486 |
| 26+ years | 10000x easier | 386, 68000 |

```python
from vintage_cpu_integration_example import adjust_difficulty_for_vintage

cpu_info = detect_all_cpu_architectures("Intel 80386DX")
base_difficulty = 1000.0
adjusted = adjust_difficulty_for_vintage(base_difficulty, cpu_info)
# → 0.1 (10000x easier for 40-year-old CPU)
```

## Running the Demo

### Full Integration Demo

```bash
python3 vintage_cpu_integration_example.py
```

Output:
1. Unified detection test (vintage + modern)
2. Local hardware detection
3. Server-side validation simulation
4. Time decay simulation
5. Difficulty adjustment simulation

### Vintage-Only Demo

```bash
python3 cpu_vintage_architectures.py
```

Output:
- 50+ vintage CPU detections
- Multiplier ranking (3.0x → 1.7x)
- Years spanning 1979-2012

## Detection Patterns

### Linux `/proc/cpuinfo`

**Pentium III:**
```
model name : Intel(R) Pentium(R) III CPU 1000MHz
```

**68K (Emulator or Real):**
```
cpu : 68040
fpu : 68040
```

**MIPS (SGI):**
```
cpu model : MIPS R5000 Revision 2.1
system type : SGI Indy
```

**SPARC (Sun):**
```
cpu : TI UltraSparc II (BlackBird)
```

**Alpha (DEC):**
```
cpu model : EV56
cpu variation : 7
```

### Windows Registry

```
HKEY_LOCAL_MACHINE\HARDWARE\DESCRIPTION\System\CentralProcessor\0\
  ProcessorNameString = "Intel(R) Pentium(R) III processor"
```

### Mac OS X

```bash
sysctl -n machdep.cpu.brand_string
# Output: Apple M1
```

## Anti-Spoofing

### Hardware Fingerprint Checks (RIP-PoA)

All vintage claims should pass fingerprint validation:

1. **Clock drift**: Real vintage oscillators drift after 30+ years
2. **Cache timing**: Unique patterns for each CPU generation
3. **Thermal patterns**: Old silicon heats/cools differently
4. **SIMD latency**: AltiVec/SSE/3DNow! have distinct timings
5. **Jitter variance**: Real hardware has higher jitter

### Cross-Reference Validation

Server validates CPU claims by:

1. Parsing brand string → detect architecture
2. Comparing claimed vs detected architecture
3. Validating multiplier matches expected value
4. Checking hardware fingerprint (RIP-PoA)
5. Flagging suspicious patterns (e.g., 10 "386" miners from same IP)

## Integration with RustChain Miner

### Client-Side (Miner)

```python
# In rustchain_universal_miner.py

from vintage_cpu_integration_example import detect_hardware_for_miner

def build_attestation():
    hardware = detect_hardware_for_miner()

    return {
        "miner": wallet_address,
        "device": hardware,
        "nonce": int(time.time() * 1000),
        # ... other fields
    }
```

### Server-Side (Node)

```python
# In rustchain_v2_integrated_v2.2.1_rip200.py

from vintage_cpu_integration_example import validate_cpu_claim, apply_time_decay

@app.route("/attest/submit", methods=["POST"])
def handle_attestation():
    attestation = request.get_json()

    # Validate CPU claim
    is_valid, reason, arch, mult = validate_cpu_claim(attestation)
    if not is_valid:
        return {"ok": False, "error": reason}, 400

    # Apply time decay to vintage multiplier
    cpu_year = attestation["device"]["cpu_year"]
    final_mult = apply_time_decay(mult, cpu_year)

    # Record attestation with final multiplier
    record_miner_attestation(
        miner_id=attestation["miner"],
        device_arch=arch,
        multiplier=final_mult
    )

    return {"ok": True, "multiplier": final_mult}
```

## Rarity Assessment (2025)

### Extremely Rare (<0.01% chance of encountering)
- Intel 386/486
- Motorola 68000/68020
- MIPS R2000/R3000
- Original Pentium

### Very Rare (0.01-0.1%)
- Pentium Pro/II
- AMD K5/K6
- Cyrix/Transmeta/VIA
- Alpha, PA-RISC, early SPARC

### Rare but Possible (0.1-1%)
- Pentium III (legacy industrial systems)
- PowerPC Amiga (active enthusiast community)
- UltraSPARC (Oracle legacy servers)

### Collectible/Enthusiast (1-5%)
- 68K via emulators (UAE, Basilisk II)
- MIPS via emulators (SGI collectors)
- Alpha via OpenVMS enthusiasts

## Testing

### Unit Tests

```python
# Test vintage detection
from cpu_vintage_architectures import detect_vintage_architecture

assert detect_vintage_architecture("Intel 80386DX")[2] == 1985
assert detect_vintage_architecture("MC68040")[3] == 2.4
assert detect_vintage_architecture("Alpha 21064")[0] == "alpha"
```

### Integration Tests

```bash
# Run full demo
python3 vintage_cpu_integration_example.py

# Expected: All 12 test CPUs detect correctly
# Expected: Local CPU detects (AMD Ryzen 5 8645HS → zen4, 1.0x)
# Expected: Validation passes
# Expected: Time decay shows decreasing multipliers
```

## Performance Impact

- **Detection**: O(N) where N = number of regex patterns (~200 total)
- **Per CPU check**: <1ms on modern hardware
- **Server overhead**: Negligible (cached detection results)

## Future Enhancements

### Phase 1 (Current)
- [x] 50+ vintage architectures
- [x] Unified detection (vintage + modern)
- [x] Time decay
- [x] Difficulty adjustment
- [x] Integration example

### Phase 2 (Planned)
- [ ] GPU detection (NVIDIA, AMD, vintage GPUs)
- [ ] Exotic architectures (ARM pre-v7, RISC-V vintage)
- [ ] Enhanced anti-spoofing (performance benchmarks)
- [ ] Community submissions (rare CPUs)

### Phase 3 (Future)
- [ ] Mainframe CPUs (IBM z/Architecture, older)
- [ ] Embedded CPUs (68332, ARM7TDMI)
- [ ] Exotic RISC (Itanium, VLIW)
- [ ] Historical CPUs (PDP-11, VAX, 6502, Z80)

## Contributing

To add a new vintage CPU:

1. Research release year and market position
2. Add entry to appropriate dict in `cpu_vintage_architectures.py`
3. Determine multiplier based on age and rarity
4. Add regex patterns for detection
5. Add test case to demo
6. Submit PR with documentation

## References

- [Intel Processor History](https://en.wikipedia.org/wiki/List_of_Intel_processors)
- [Motorola 68K Family](https://en.wikipedia.org/wiki/Motorola_68000_series)
- [DEC Alpha](https://en.wikipedia.org/wiki/DEC_Alpha)
- [Sun SPARC](https://en.wikipedia.org/wiki/SPARC)
- [MIPS Architecture](https://en.wikipedia.org/wiki/MIPS_architecture)
- [PA-RISC](https://en.wikipedia.org/wiki/PA-RISC)
- [IBM POWER](https://en.wikipedia.org/wiki/IBM_POWER_microprocessors)
- [Cyrix](https://en.wikipedia.org/wiki/Cyrix)
- [VIA Technologies](https://en.wikipedia.org/wiki/VIA_Technologies)
- [Transmeta](https://en.wikipedia.org/wiki/Transmeta)

## License

Part of the RustChain project. See main repository for license.

## Contact

For questions or issues, see RustChain documentation or file an issue.

---

**Remember**: The goal is to incentivize preservation of computing history, not to make vintage hardware economically dominant. Time decay and difficulty adjustment ensure fairness while honoring the past.
