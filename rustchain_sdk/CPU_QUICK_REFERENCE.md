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
| **RISC-V** |
| SiFive U74 (rv64imafdc) | RISC-V | 2020 | 1.5x |
| StarFive JH7110 | RISC-V | 2022 | 1.4x |
| Generic RISC-V | RISC-V | 2014+ | 1.4x |
| **HITACHI SUPERH** |
| SH7032 (SH-1) | SH-1 | 1992 | 2.7x |
| SH7604 (SH-2) | SH-2 | 1994 | 2.6x |
| SH7750 (SH-4 / Dreamcast) | SH-4 | 1998 | 2.3x |
| SH7780 (SH-4A) | SH-4A | 2003 | 2.2x |
| **GAME CONSOLE CPUs** |
| Cell Broadband Engine (PS3) | Cell BE | 2006 | 2.2x |
| Emotion Engine R5900 (PS2) | Emotion Engine | 2000 | 2.2x |
| IBM Xenon (Xbox 360) | Xenon | 2005 | 2.0x |
| IBM Gekko (GameCube) | Gekko | 2001 | 2.1x |
| IBM Broadway (Wii) | Broadway | 2006 | 2.0x |
| Allegrex (PSP) | Allegrex | 2004 | 2.0x |
| **ULTRA-RARE** |
| DEC VAX / MicroVAX | VAX | 1977 | **3.5x** |
| INMOS Transputer T414/T800 | Transputer | 1985 | **3.5x** |
| Fairchild Clipper C100/C300 | Clipper | 1986 | **3.5x** |
| NS32032/NS32532 | NS32K | 1982 | **3.5x** |
| IBM ROMP (RT PC) | ROMP | 1986 | **3.5x** |
| Intel i860 | i860 | 1989 | 3.0x |
| Intel i960 | i960 | 1988 | 3.0x |
| Motorola 88100/88110 | 88K | 1988 | 3.0x |
| AMD Am29000 | Am29K | 1987 | 3.0x |
| **VINTAGE ARM** |
| ARM2 (Acorn Archimedes) | ARM2 | 1986 | **4.0x** |
| ARM3 (Acorn A540) | ARM3 | 1989 | **3.8x** |
| ARM7TDMI (GBA, iPod) | ARM7 | 1994 | 3.0x |
| StrongARM SA-110 | StrongARM | 1996 | 2.8x |
| XScale PXA2xx | XScale | 2000 | 2.5x |
| **INTEL/IBM SERVER** |
| Itanium 2 (IA-64) | Itanium | 2001 | 2.5x |
| IBM S/390 / zSeries | S/390 | 1990 | 2.5x |

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

### RISC-V

```regex
# Architecture detection (uname -m or /proc/cpuinfo)
riscv64                        # 64-bit RISC-V
riscv32                        # 32-bit RISC-V
RISC-V                         # Generic brand string

# ISA string from /proc/cpuinfo "isa" field
rv64imafdc                     # Standard 64-bit with extensions
rv32imafdc                     # Standard 32-bit with extensions

# Specific SoCs
SiFive.*U74                    # SiFive U74 core (VisionFive 2, HiFive Unmatched)
sifive,u74                     # Device-tree compatible string
JH7110                         # StarFive JH7110 SoC (VisionFive 2)
StarFive.*JH7110               # StarFive brand string
```

### Hitachi SuperH

```regex
# /proc/cpuinfo "cpu type" field
SH-1                           # Original SuperH (2.7x)
SH7032|SH703\d                 # SH-1 chip variants
SH-2                           # Sega Saturn CPU (2.6x)
SH7604|SH760\d                 # SH-2 chip variants
SH-4                           # Sega Dreamcast CPU (2.3x)
SH7750|SH775\d|SH7091          # SH-4 chip variants (7091 = Dreamcast)
SH-4A                          # Enhanced SH-4 (2.2x)
SH7780|SH778\d                 # SH-4A chip variants

# uname -m
sh4|sh4a|sh3|sh2               # SuperH architecture
```

### Game Console CPUs

```regex
# PS3 Cell Broadband Engine (2.2x)
Cell\s*(Broadband\s*Engine)?   # /proc/cpuinfo on PS3 Linux
Cell\s*BE|CBE                  # Abbreviated
PPE.*SPE                       # PPE + SPE units
platform.*Cell                 # Platform field

# PS2 Emotion Engine (2.2x)
Emotion\s*Engine               # PS2 Linux kernel
R5900                          # MIPS R5900 core (EE is based on this)

# Xbox 360 Xenon (2.0x) - rarely runs Linux
Xenon                          # PPC Xenon triple-core
IBM.*Xenon                     # IBM brand
PPC.*Xbox                      # PowerPC Xbox variant

# GameCube Gekko (2.1x) - homebrew Linux
Gekko                          # IBM Gekko (PPC 750 derivative)
IBM.*Gekko                     # Full brand

# Wii Broadway (2.0x) - homebrew Linux
Broadway                       # IBM Broadway (Gekko successor)
IBM.*Broadway                  # Full brand

# PSP Allegrex (2.0x) - homebrew
Allegrex                       # MIPS Allegrex core
MIPS.*Allegrex                 # Full brand
```

### Vintage ARM (High-Multiplier, NOT Modern ARM)

```regex
# MYTHIC tier (4.0x / 3.8x) - Acorn era
ARM2                           # Original ARM (Acorn Archimedes)
ARM3                           # ARM3 with cache (Acorn A540)
Acorn.*ARM[23]                 # Acorn brand detection

# 3.0x - ARM7 era
ARM7TDMI                       # Game Boy Advance, iPod
ARM7                           # Generic ARM7 family

# 2.8x - StrongARM
StrongARM                      # DEC/Intel StrongARM
SA-110|SA-1100|SA-1110         # StrongARM chip variants

# 2.5x - XScale
XScale                         # Intel XScale (PXA series)
PXA2[0-9]{2}                   # PXA210, PXA250, PXA255, PXA260
PXA27[0-9]                     # PXA270, PXA271, PXA272
IXP[0-9]{3}                    # IXP network processors
```

### Ultra-Rare / Extinct Architectures

```regex
# DEC VAX (3.5x)
VAX                            # Generic VAX
MicroVAX                       # Desktop VAX
VAXstation                     # Workstation VAX
VAX-11                         # Original VAX-11/780

# INMOS Transputer (3.5x)
T414                           # 32-bit, no FPU
T800                           # 32-bit with FPU
T9000                          # Advanced transputer
Transputer.*T[489]             # Generic transputer match

# Fairchild Clipper (3.5x)
Clipper                        # Generic Clipper
C[134]00                       # C100, C300, C400 variants

# National Semiconductor NS32K (3.5x)
NS32032|NS32332|NS32532        # NS32K chip variants
NS32K                          # Generic NS32K

# IBM ROMP (3.5x)
ROMP                           # Research Office Products
IBM\s*RT                       # IBM RT PC

# Intel i860 (3.0x)
i860                           # Intel RISC
Intel.*860                     # Brand string

# Intel i960 (3.0x)
i960                           # Intel embedded RISC
Intel.*960                     # Brand string

# Motorola 88K (3.0x)
88000|88100|88110               # Motorola 88K chips
MC88[01]\d{2}                  # Full Motorola part numbers

# AMD Am29000 (3.0x)
29000|Am29000                  # AMD 29K
29K                            # Shorthand
```

### Intel Itanium / IA-64

```regex
# Itanium detection (2.5x)
Itanium                        # Generic Itanium
IA-64                          # Architecture name
ia64                           # uname -m output
McKinley                       # Itanium 2 codename
Madison                        # Itanium 2 9M codename
Montecito                      # Dual-core Itanium 2
Tukwila|Poulson                # Late Itanium
```

### IBM Mainframe / S/390

```regex
# S/390 detection (2.5x)
S/390                          # System/390
System/390                     # Full name
s390x?                         # uname -m (s390 or s390x)
zSeries.*z900                  # Early zSeries
z/Architecture                 # 64-bit S/390 successor
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
| **Mythic** | 3.5x - 4.0x | ARM2/ARM3, VAX, Transputer, Clipper, NS32K, ROMP |
| **Heroic** | 3.0x - 3.4x | 68000, i386, MIPS R2000, i860/i960, 88K, Am29K, ARM7TDMI |
| **Legendary** | 2.0x - 2.9x | PowerPC G4/G5, Alpha, SPARC, SuperH, Cell BE, Emotion Engine |
| **Epic** | 1.5x - 1.9x | Pentium 4, Athlon 64, G3, RISC-V (SiFive) |
| **Rare** | 1.3x - 1.4x | Core 2, Phenom II, FX, RISC-V (generic) |
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

### RISC-V
```bash
# Architecture
uname -m
# Output: riscv64

# ISA extensions from /proc/cpuinfo
grep "isa" /proc/cpuinfo | head -1
# Output: isa : rv64imafdc

# SoC identification
cat /proc/device-tree/compatible 2>/dev/null
# Output: starfive,jh7110
```

### Hitachi SuperH
```bash
# Architecture
uname -m
# Output: sh4

# CPU type from /proc/cpuinfo
grep "cpu type" /proc/cpuinfo
# Output: cpu type : SH7750  (Dreamcast)
```

### PS3 Cell BE (Linux)
```bash
grep "cpu" /proc/cpuinfo | head -1
# Output: cpu : Cell Broadband Engine, altivec supported

grep "platform" /proc/cpuinfo
# Output: platform : Cell
```

### Itanium / IA-64
```bash
uname -m
# Output: ia64

grep "family" /proc/cpuinfo | head -1
# Output: family : Itanium 2
```

### IBM S/390
```bash
uname -m
# Output: s390x

grep "processor" /proc/cpuinfo | head -1
# Output: processor 0: version = FF, ...
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
