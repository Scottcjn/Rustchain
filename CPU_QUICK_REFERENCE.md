# CPU Antiquity Multiplier Quick Reference

**For**: RustChain RIP-200 Proof-of-Antiquity rewards
**Updated**: 2025-12-24

## Quick Lookup by CPU Name

| CPU Brand String Example | Architecture | Year | Base Multiplier |
|--------------------------|--------------|------|-----------------|
| **INTEL VINTAGE** |
| Pentium(R) 4 CPU 3.00GHz | Pentium 4 | 2000 | 1.5x |
| Core(TM)2 Duo E8400 | Core 2 | 2006 | 1.3x |
| Core(TM) i7-920 | Nehalem | 2008 | 1.2x |
| Core(TM) i7-2600K | Sandy Bridge | 2011 | 1.1x |
| Core(TM) i7-3770K | Ivy Bridge | 2012 | 1.1x |
| Core(TM) i7-4770K | Haswell | 2013 | 1.1x |
| Core(TM) i7-6700K | Skylake | 2015 | 1.05x |
| **INTEL MODERN** |
| Core(TM) i7-8700K | Coffee Lake | 2017 | 1.0x |
| Core(TM) i9-9900K | Coffee Lake | 2018 | 1.0x |
| Core(TM) i7-10700K | Comet Lake | 2020 | 1.0x |
| Core(TM) i9-12900K | Alder Lake | 2021 | 1.0x |
| Core(TM) i9-13900K | Raptor Lake | 2022 | 1.0x |
| Core Ultra 9 285K | Arrow Lake | 2024 | 1.0x |
| **INTEL XEON** |
| Xeon(R) E5-1650 (no v) | Sandy Bridge | 2011 | 1.1x + server |
| Xeon(R) E5-1650 v2 | Ivy Bridge | 2012 | 1.1x + server |
| Xeon(R) E5-2680 v3 | Haswell | 2013 | 1.1x + server |
| Xeon(R) E5-2680 v4 | Broadwell | 2014 | 1.05x + server |
| Xeon(R) Gold 6248R | Cascade Lake | 2019 | 1.0x + server |
| Xeon(R) Gold 8468 | Sapphire Rapids | 2023 | 1.0x + server |
| **AMD VINTAGE** |
| Athlon(tm) 64 X2 4200+ | K7 Athlon | 2005 | 1.5x |
| Phenom(tm) II X6 1090T | K10 Phenom | 2009 | 1.4x |
| FX(tm)-8350 | Piledriver | 2012 | 1.3x |
| **AMD MODERN** |
| Ryzen 7 1700X | Zen | 2017 | 1.1x |
| Ryzen 7 2700X | Zen+ | 2018 | 1.1x |
| Ryzen 9 3900X | Zen 2 | 2019 | 1.05x |
| Ryzen 9 5950X | Zen 3 | 2020 | 1.0x |
| Ryzen 5 8645HS | Zen 4 (mobile) | 2023 | 1.0x |
| Ryzen 9 7950X | Zen 4 | 2022 | 1.0x |
| Ryzen 9 9950X | Zen 5 | 2024 | 1.0x |
| **AMD SERVER** |
| EPYC 7551 | Naples (Zen) | 2017 | 1.1x + server |
| EPYC 7742 | Rome (Zen 2) | 2019 | 1.05x + server |
| EPYC 7763 | Milan (Zen 3) | 2021 | 1.0x + server |
| EPYC 9654 | Genoa (Zen 4) | 2022 | 1.0x + server |
| **POWERPC** |
| PowerPC G3 (750) | G3 | 1997 | 1.8x |
| PowerPC G4 (7450) | G4 | 2001 | **2.5x** ⭐ |
| PowerPC G5 (970) | G5 | 2003 | 2.0x |
| **APPLE SILICON** |
| Apple M1 | M1 | 2020 | 1.2x |
| Apple M2 | M2 | 2022 | 1.15x |
| Apple M3 | M3 | 2023 | 1.1x |
| Apple M4 | M4 | 2024 | 1.05x |

## Detection Regex Patterns

### Intel Core i-series

```regex
# 1st-gen (Nehalem): i7-920, i5-750
i[3579]-[789]\d{2}

# 2nd-gen (Sandy Bridge): i7-2600K
i[3579]-2\d{3}

# 3rd-gen (Ivy Bridge): i7-3770K
i[3579]-3\d{3}

# 4th-gen (Haswell): i7-4770K
i[3579]-4\d{3}

# 5th-gen (Broadwell): i7-5775C
i[3579]-5\d{3}

# 6th-gen (Skylake): i7-6700K
i[3579]-6\d{3}

# 7th-gen (Kaby Lake): i7-7700K
i[3579]-7\d{3}

# 8th/9th-gen (Coffee Lake): i7-8700K, i9-9900K
i[3579]-[89]\d{3}

# 10th-gen (Comet Lake): i7-10700K
i[3579]-10\d{3}

# 11th-gen (Rocket Lake): i9-11900K
i[3579]-11\d{3}

# 12th-gen (Alder Lake): i9-12900K
i[3579]-12\d{3}

# 13th/14th-gen (Raptor Lake): i9-13900K, i9-14900K
i[3579]-1[34]\d{3}

# Core Ultra (new naming): Core Ultra 9 285K
Core Ultra [579]
```

### Intel Xeon

```regex
# Xeon E3-1200 series
E3-12\d{2}(?!\s*v)    # Sandy Bridge (no v-suffix)
E3-12\d{2}\s*v2       # Ivy Bridge
E3-12\d{2}\s*v3       # Haswell
E3-12\d{2}\s*v4       # Broadwell
E3-12\d{2}\s*v[56]    # Skylake

# Xeon E5 series
E5-[124]6\d{2}(?!\s*v)  # Sandy Bridge
E5-[124]6\d{2}\s*v2     # Ivy Bridge
E5-[124]6\d{2}\s*v3     # Haswell
E5-[124]6\d{2}\s*v4     # Broadwell

# Xeon Scalable
(Gold|Silver|Bronze|Platinum)\s*\d{4}(?!\w)    # 1st-gen (no suffix)
(Gold|Silver|Bronze|Platinum)\s*\d{4}[A-Z]     # 2nd-gen (letter suffix)
(Gold|Silver|Bronze|Platinum)\s*[89]\d{3}      # 4th-gen (8xxx/9xxx)
```

### AMD Ryzen

```regex
# Ryzen series detection
Ryzen\s*[3579]\s*1\d{3}   # Zen (1000 series)
Ryzen\s*[3579]\s*2\d{3}   # Zen+ (2000 series)
Ryzen\s*[3579]\s*3\d{3}   # Zen 2 (3000 series)
Ryzen\s*[3579]\s*5\d{3}   # Zen 3 (5000 series)
Ryzen\s*[3579]\s*7\d{3}   # Zen 4 (7000 series)
Ryzen\s*[3579]\s*8\d{3}   # Zen 4 mobile (8000 series)
Ryzen\s*[3579]\s*9\d{3}   # Zen 5 (9000 series)
```

### AMD EPYC

```regex
EPYC 7[0-2]\d{2}   # Naples (Zen)
EPYC 7[2-4]\d{2}   # Rome (Zen 2)
EPYC 7[3-5]\d{2}   # Milan (Zen 3)
EPYC 9[0-4]\d{2}   # Genoa (Zen 4)
EPYC 8[0-4]\d{2}   # Siena (Zen 4c)
EPYC 9[5-9]\d{2}   # Turin (Zen 5)
```

### PowerPC

```regex
7450|7447|7455         # G4
970                    # G5
750                    # G3
PowerPC G[345]         # Generic G-series
```

### Apple Silicon

```regex
Apple M[1-4]           # M1/M2/M3/M4
```

## Multiplier Calculation Examples

### Vintage with Time Decay

**PowerPC G4 (age 24 years, base 2.5x)**
```
decay_factor = 1.0 - (0.15 × (24 - 5) / 5.0)
             = 1.0 - (0.15 × 19 / 5.0)
             = 1.0 - 0.57 = 0.43
vintage_bonus = 2.5 - 1.0 = 1.5
final = 1.0 + (1.5 × 0.43) = 1.645x
```

**Core 2 Duo E8400 (age 19 years, base 1.3x)**
```
decay_factor = 1.0 - (0.15 × (19 - 5) / 5.0)
             = 1.0 - (0.15 × 14 / 5.0)
             = 1.0 - 0.42 = 0.58
vintage_bonus = 1.3 - 1.0 = 0.3
final = 1.0 + (0.3 × 0.58) = 1.174x
```

### Modern with Loyalty Bonus

**Ryzen 9 7950X (base 1.0x, 3 years uptime)**
```
loyalty_bonus = min(0.5, 3 × 0.15) = 0.45
final = 1.0 + 0.45 = 1.45x
```

**Ryzen 9 7950X (base 1.0x, 5+ years uptime)**
```
loyalty_bonus = min(0.5, 5 × 0.15) = 0.5 (capped)
final = 1.0 + 0.5 = 1.5x
```

### Server Bonus

**Xeon E5-1650 v2 (Ivy Bridge, age 13 years, server)**
```
base = 1.1x (Ivy Bridge)
with_decay = 1.0 + ((1.1 - 1.0) × (1.0 - 0.15 × 8/5)) = 1.076x
with_server = 1.076 × 1.1 = 1.1836x
```

## Multiplier Tiers Summary

| Tier | Multiplier Range | Hardware Examples |
|------|------------------|-------------------|
| **Legendary** | 2.0x - 2.5x | PowerPC G4/G5 (2001-2006) |
| **Epic** | 1.5x - 1.9x | Pentium 4, Athlon 64, G3 |
| **Rare** | 1.3x - 1.4x | Core 2, Phenom II, FX |
| **Uncommon** | 1.1x - 1.2x | Sandy/Ivy Bridge, Zen/Zen+, M1 |
| **Common** | 1.0x - 1.1x | Haswell+, Zen3+, M2/M3 |
| **Modern** | 1.0x → 1.5x | Zen4/5, Raptor Lake (loyalty bonus) |

## Time Decay Schedule

| Years Old | Vintage Bonus Decay | Example (G4 2.5x) |
|-----------|---------------------|-------------------|
| 5 | 0% (full bonus) | 2.5x |
| 10 | 15% decay | 2.275x |
| 15 | 30% decay | 2.05x |
| 20 | 45% decay | 1.825x |
| 25 | 60% decay | 1.6x |
| 30+ | ~100% decay | 1.0x |

## Loyalty Bonus Schedule

| Years Uptime | Bonus | Final (1.0x base) |
|--------------|-------|-------------------|
| 0 | 0% | 1.0x |
| 1 | +15% | 1.15x |
| 2 | +30% | 1.3x |
| 3 | +45% | 1.45x |
| 4+ | +50% (cap) | 1.5x |

## Command-Line Detection Examples

### Linux
```bash
# Get CPU brand string
grep "model name" /proc/cpuinfo | head -1 | cut -d: -f2 | xargs

# PowerPC
cat /proc/cpuinfo | grep "cpu"
```

### macOS
```bash
# Intel/Apple Silicon
sysctl -n machdep.cpu.brand_string
```

### Windows (PowerShell)
```powershell
Get-WmiObject Win32_Processor | Select-Object Name
```

## Python Integration

```python
from cpu_architecture_detection import calculate_antiquity_multiplier

# Example usage
cpu = "Intel(R) Core(TM) i7-2600K CPU @ 3.40GHz"
info = calculate_antiquity_multiplier(cpu)

print(f"Multiplier: {info.antiquity_multiplier}x")
print(f"Generation: {info.generation}")
```

## FAQ

**Q: Why does my modern Ryzen have 1.0x but can earn more?**
A: Modern CPUs start at 1.0x but earn +15% per year of consistent uptime (loyalty bonus), up to 1.5x after 4 years.

**Q: Why is my 2012 Xeon showing 1.18x instead of 1.1x?**
A: Server hardware gets +10% bonus on top of base. Also, time decay reduces vintage bonuses over time.

**Q: How often does the multiplier update?**
A: Time decay recalculates on each epoch settlement. Loyalty bonus increases annually based on attestation history.

**Q: Can I game the system with VMs?**
A: No. The RIP-PoA fingerprint system (6 hardware checks) detects VMs and rejects them. See `fingerprint_checks.py`.

**Q: What happens to PowerPC multipliers in 10 years?**
A: They decay to ~1.0x by 2030-2035, but early adopters (2024-2028) still benefit from high rewards.

---

**Generated by**: cpu_architecture_detection.py
**Last Updated**: 2025-12-24
