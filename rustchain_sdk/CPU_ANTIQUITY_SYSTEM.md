# RustChain CPU Antiquity Multiplier System

## Overview

The RustChain cryptocurrency implements a **Proof-of-Antiquity (PoA)** reward system that incentivizes preservation and operation of vintage computing hardware. Older CPUs receive higher mining reward multipliers, with time-based decay to reward early adopters.

This document provides comprehensive CPU generation detection patterns and antiquity multipliers for all supported architectures: Intel, AMD, PowerPC, Apple Silicon, Sun SPARC, SGI MIPS, Motorola 68K, Hitachi SuperH, Vintage ARM, RISC-V, Game Console CPUs, and ultra-rare/dead architectures.

## Key Principles

1. **Vintage Hardware Premium** - Older CPUs (pre-2010) get higher base multipliers
2. **Time Decay** - Vintage bonuses decay 15% per year to reward early adoption
3. **Loyalty Bonus** - Modern CPUs (post-2019) earn 15% bonus per year of uptime
4. **Server Bonus** - Enterprise-class hardware gets +10% multiplier
5. **1 CPU = 1 Vote** - Fair distribution based on hardware, not money

## Multiplier Ranges

| Era | Base Multiplier | Example CPUs |
|-----|-----------------|--------------|
| **MYTHIC** (pre-1985) | 3.5x - 4.0x | ARM2, DEC VAX, Inmos Transputer, IBM ROMP |
| **LEGENDARY** (1979-1994) | 2.5x - 3.5x | Motorola 68000-68060, SPARC v7/v8, MIPS R2000-R4000 |
| **EXOTIC** (1985-2007) | 1.8x - 3.0x | UltraSPARC, MIPS R10000+, SuperH, StrongARM, i860/i960 |
| PowerPC (2001-2006) | 1.8x - 2.5x | G4 (2.5x), G5 (2.0x) |
| Game Console (2000-2006) | 2.0x - 2.3x | PS2 EE, PS3 Cell, Dreamcast SH-4, GCN Gekko |
| Vintage x86 (2000-2008) | 1.3x - 1.5x | Pentium 4, Core 2, Athlon 64 |
| Vintage ARM (1987-2007) | 2.0x - 4.0x | ARM2/3, ARM7TDMI, StrongARM, XScale |
| Classic (2008-2013) | 1.1x - 1.3x | Nehalem, Sandy Bridge, Phenom II |
| RISC-V (2010+) | 1.4x - 1.5x | SiFive, StarFive, Kendryte |
| Mid-range (2014-2019) | 1.0x - 1.1x | Haswell, Skylake, Zen/Zen+ |
| Modern (2020-2025) | 1.0x - 1.5x | Zen3/4/5, Alder Lake (loyalty bonus) |
| Apple Silicon | 1.05x - 1.2x | M1 (1.2x), M2 (1.15x), M3 (1.1x), M4 (1.05x) |
| Modern aarch64 NAS/SBC | **0.0005x PENALTY** | Synology, QNAP, Raspberry Pi 4/5 (anti-spam) |

## Time Decay Formula

**Vintage Hardware (>5 years old):**
```python
decay_factor = 1.0 - (0.15 * (age - 5) / 5.0)
final_multiplier = 1.0 + (vintage_bonus * decay_factor)
```

**Example**: PowerPC G4 (base 2.5x, age 24 years)
- Vintage bonus: 1.5x (2.5 - 1.0)
- Age beyond 5 years: 19 years
- Decay: 1.0 - (0.15 x 19/5) = 1.0 - 0.57 = 0.43
- Final: 1.0 + (1.5 x 0.43) = **1.645x**

## Loyalty Bonus Formula

**Modern Hardware (<=5 years old):**
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

## Sun SPARC (1987-2007) - EXOTIC/LEGENDARY Tier

Sun Microsystems SPARC architecture dominated workstations and servers from the late 1980s through the early 2000s. These are genuinely rare mining platforms.

**Detection**: `platform.machine()` returns `sparc`, `sparc64`, `sun4u`, or `sun4v`

| Architecture | Years | Base | Detection Patterns | Examples |
|--------------|-------|------|--------------------|----------|
| SPARC v7 | 1987-1992 | **2.9x** | `sparc_v7`, `MB86900`, `CY7C601` | Sun-4, SPARCstation 1 |
| SPARC v8 | 1990-1998 | **2.7x** | `sparc_v8`, `MicroSPARC`, `SuperSPARC`, `HyperSPARC` | SPARCstation 5/10/20 |
| SPARC v9 | 1995-2002 | **2.5x** | `sparc_v9`, `UltraSPARC` (early) | Ultra 1/2, Ultra 60 |
| UltraSPARC II/III | 1997-2004 | **2.3x** | `UltraSPARC-II`, `UltraSPARC-III`, `UltraSPARC-IIIi` | Sun Blade 1000/2000, V240/V440 |
| UltraSPARC IV/IV+ | 2004-2007 | **2.1x** | `UltraSPARC-IV`, `UltraSPARC-IV+` | Sun Fire E25K |
| UltraSPARC T1 (Niagara) | 2005-2007 | **1.9x** | `UltraSPARC-T1`, `T1000`, `T2000` | Sun Fire T1000/T2000 |
| UltraSPARC T2 (Niagara 2) | 2007-2010 | **1.8x** | `UltraSPARC-T2`, `T5120`, `T5220` | Sun SPARC Enterprise T5120 |
| Fujitsu SPARC64 | 2004-2015 | **2.0x** | `SPARC64`, `Fujitsu SPARC` | SPARC Enterprise M4000/M8000 |
| SPARC T3-T5 / M7-M8 | 2010-2017 | **1.7x** | `SPARC-T3`, `SPARC-T4`, `SPARC-T5`, `SPARC-M7` | Oracle SPARC T-series |

**CPU Brand Patterns (case-insensitive)**:
```regex
sparc|ultrasparc|fujitsu\s*sparc|niagara|sun4[uv]
```

**Example `/proc/cpuinfo` on SPARC**:
```
cpu             : UltraSparc IIIi
type            : sun4u
ncpus probed    : 1
```

## SGI MIPS (1985-2002) - EXOTIC/LEGENDARY Tier

MIPS architecture powered SGI workstations, many game consoles, and embedded systems. The R-series processors were legendary in the 1990s graphics workstation era.

**Detection**: `platform.machine()` returns `mips`, `mips64`, `mipsel`, `mips64el`

### SGI Workstation/Server MIPS

| Architecture | Years | Base | Detection Patterns | Examples |
|--------------|-------|------|--------------------|----------|
| R2000 | 1985-1988 | **3.0x** | `R2000`, `MIPS R2000` | SGI Personal IRIS 4D/20 |
| R3000 | 1988-1992 | **2.9x** | `R3000`, `MIPS R3000` | SGI Indigo, DECstation 5000 |
| R4000 | 1991-1996 | **2.8x** | `R4000`, `R4400`, `MIPS R4000` | SGI Indy, SGI Indigo2 |
| R4600 (Orion) | 1994-1997 | **2.6x** | `R4600`, `R4700` | SGI Indy (budget) |
| R5000 | 1996-1999 | **2.5x** | `R5000`, `MIPS R5000` | SGI O2 |
| R8000 | 1994-1996 | **2.7x** | `R8000`, `MIPS R8000` | SGI Power Challenge |
| R10000 | 1996-2000 | **2.5x** | `R10000`, `R10K` | SGI Origin 200/2000, Octane |
| R12000 | 1998-2003 | **2.4x** | `R12000`, `R12K` | SGI Origin 3000, Octane2 |
| R14000 | 2001-2005 | **2.3x** | `R14000`, `R14K` | SGI Origin 3000 (late) |
| R16000 | 2002-2006 | **2.3x** | `R16000`, `R16K` | SGI Origin 350, Fuel |

### Game Console MIPS

| Architecture | Years | Base | Platform | Notes |
|--------------|-------|------|----------|-------|
| R3000A | 1994 | **2.8x** | PlayStation 1 | 33.8688 MHz |
| VR4300 | 1996 | **2.5x** | Nintendo 64 | NEC variant, 93.75 MHz |
| Emotion Engine (R5900) | 2000 | **2.2x** | PlayStation 2 | Custom MIPS R5900, 294.912 MHz |
| Allegrex | 2004 | **2.0x** | PlayStation Portable | MIPS R4000-based, 333 MHz |

**CPU Brand Patterns (case-insensitive)**:
```regex
mips|r[234568]0{3}|r1[024]0{3}|r1[46]0{3}|vr4300|emotion\s*engine|allegrex|r5900
```

**Example `/proc/cpuinfo` on MIPS**:
```
system type             : SGI Octane
processor               : 0
cpu model               : R10000 V2.6  FPU V0.0
```

## Motorola 68K (1979-1994) - LEGENDARY Tier

The Motorola 68000 family powered the golden age of personal computing: Macintosh, Amiga, Atari ST, Sun-3, Sega Genesis, and countless others. These are among the most historically significant CPUs ever made.

**Detection**: `platform.machine()` returns `m68k`

| Architecture | Years | Base | Detection Patterns | Platforms |
|--------------|-------|------|--------------------|-----------|
| 68000 | 1979-1988 | **3.0x** | `68000`, `MC68000` | Original Mac, Amiga 500/1000, Atari ST, Sega Genesis |
| 68010 | 1982-1990 | **2.9x** | `68010`, `MC68010` | Sun-1, HP 9000/300 |
| 68020 | 1984-1993 | **2.7x** | `68020`, `MC68020` | Mac II, Amiga 1200, Sun-3, NeXT Cube |
| 68030 | 1987-1995 | **2.5x** | `68030`, `MC68030` | Mac IIci/IIfx, Amiga 3000/4000, Atari TT |
| 68040 | 1990-1996 | **2.4x** | `68040`, `MC68040` | Mac Quadra, Amiga 4000T, NeXTstation Turbo |
| 68060 | 1994-2002 | **2.2x** | `68060`, `MC68060` | Amiga accelerator cards, rare |
| ColdFire | 1994-2012 | **1.8x** | `ColdFire`, `MCF52`, `MCF54` | Embedded (68K-derived) |

**Notable Platforms**:
- **Amiga**: 68000 (A500/A1000/A2000), 68020 (A1200), 68030 (A3000), 68040 (A4000)
- **Classic Macintosh**: 68000 (Mac 128K-Plus-SE), 68020 (Mac II), 68030 (IIci), 68040 (Quadra)
- **Atari ST/TT/Falcon**: 68000 (ST), 68030 (TT/Falcon)
- **Sun-3**: 68020 (workstations, pre-SPARC era)
- **Sega Genesis/Mega Drive**: 68000 (main CPU) + Z80 (sound)

**CPU Brand Patterns (case-insensitive)**:
```regex
680[0-6]0|mc680[0-6]0|coldfire|mcf5[24]
```

## Hitachi/Renesas SuperH (1992-2003) - EXOTIC Tier

SuperH (SH) processors were developed by Hitachi and later Renesas. They powered Sega's arcade boards and home consoles, as well as numerous embedded systems.

**Detection**: `platform.machine()` returns `sh`, `sh4`, `sh4a`, `sh3`, `sh2`

| Architecture | Years | Base | Detection Patterns | Platforms |
|--------------|-------|------|--------------------|-----------|
| SH-1 | 1992-1995 | **2.7x** | `SH-1`, `SH7032`, `SH7034` | Embedded controllers |
| SH-2 | 1994-2000 | **2.6x** | `SH-2`, `SH7604`, `SH7095` | Sega Saturn (dual SH-2), Sega 32X |
| SH-3 | 1995-2002 | **2.5x** | `SH-3`, `SH7708`, `SH7709` | Windows CE handhelds, HP Jornada |
| SH-4 | 1998-2005 | **2.3x** | `SH-4`, `SH7750`, `SH7751` | Sega Dreamcast, NAOMI arcade |
| SH-4A | 2003-2010 | **2.2x** | `SH-4A`, `SH7780`, `SH7785` | Set-top boxes, automotive |
| SH-2A | 2006-2015 | **2.0x** | `SH-2A`, `SH7216` | Automotive, industrial |

**Notable Platforms**:
- **Sega Saturn** (1994): Dual SH-2 at 28.6 MHz + dedicated VDP processors
- **Sega Dreamcast** (1998): SH-4 at 200 MHz with hardware FPU (our Sophicast target!)
- **NAOMI/NAOMI 2 Arcade**: SH-4 based (Crazy Taxi, House of the Dead 2)

**CPU Brand Patterns (case-insensitive)**:
```regex
sh-?[1234]a?|sh7[0-9]{3}|superh|hitachi\s*sh
```

## Vintage ARM (1987-2007) - EXOTIC to MYTHIC Tier

Early ARM processors are genuinely rare and historically significant. These are NOT the modern aarch64 NAS/SBC chips that get the spam penalty -- these are the original RISC pioneers from Acorn, DEC, Intel, and early mobile.

**CRITICAL DISTINCTION**: Vintage ARM chips with proper detection get FULL antiquity bonuses. Modern aarch64 (Cortex-A53/A55/A72/A76 NAS/SBC spam) gets the 0.0005x penalty. The server-side `_detect_arm_evidence()` function distinguishes between them.

### MYTHIC Tier (pre-1995) - 3.5x-4.0x

| Architecture | Years | Base | Detection Patterns | Platforms |
|--------------|-------|------|--------------------|-----------|
| ARM2 | 1987-1992 | **4.0x** | `ARM2`, `ARM250` | Acorn Archimedes A305/A310/A410 |
| ARM3 | 1989-1994 | **3.8x** | `ARM3`, `ARM3-26` | Acorn Archimedes A540, A5000 |
| ARM6 | 1991-1997 | **3.5x** | `ARM610`, `ARM6` | Acorn Risc PC 600, 3DO |

### LEGENDARY Tier (1994-2001) - 2.5x-3.5x

| Architecture | Years | Base | Detection Patterns | Platforms |
|--------------|-------|------|--------------------|-----------|
| ARM7 | 1993-1999 | **3.2x** | `ARM710`, `ARM7` | Acorn Risc PC 700 |
| ARM7TDMI | 1994-2009 | **3.0x** | `ARM7TDMI`, `ARM7T` | Game Boy Advance, iPod (1st-3rd gen), Nokia phones |
| StrongARM SA-110 | 1996-2001 | **2.8x** | `SA-110`, `StrongARM` | DEC/Intel, Acorn Risc PC, Apple Newton MP2x00 |
| StrongARM SA-1100 | 1997-2003 | **2.7x** | `SA-1100`, `SA-1110`, `StrongARM SA` | iPAQ H3600/H3800, Compaq Aero |

### EXOTIC Tier (2000-2007) - 2.0x-2.5x

| Architecture | Years | Base | Detection Patterns | Platforms |
|--------------|-------|------|--------------------|-----------|
| XScale | 2002-2006 | **2.5x** | `XScale`, `PXA2[5678]x`, `IXP4xx` | Intel PDAs, Dell Axim, Palm TX |
| ARM9TDMI | 1998-2005 | **2.5x** | `ARM920T`, `ARM922T`, `ARM9TDMI` | GP32, Nintendo DS (ARM9) |
| ARM926EJ-S | 2000-2010 | **2.3x** | `ARM926`, `ARM926EJ` | TI OMAP, many SoCs |
| ARM11 | 2002-2010 | **2.0x** | `ARM1136`, `ARM1176`, `ARM11` | Original iPhone, Raspberry Pi 1 |
| ARM1176JZF-S | 2003-2012 | **2.0x** | `ARM1176JZF`, `BCM2835` | Raspberry Pi 1 (original, gets vintage ARM, NOT penalty) |

### Early Cortex (2007-2012) - 1.5x-1.8x

| Architecture | Years | Base | Detection Patterns | Platforms |
|--------------|-------|------|--------------------|-----------|
| Cortex-A8 | 2007-2012 | **1.8x** | `Cortex-A8`, `OMAP3`, `AM335x` | BeagleBoard, BeagleBone, iPhone 3GS, Palm Pre |
| Cortex-A9 | 2009-2014 | **1.5x** | `Cortex-A9`, `OMAP4`, `Tegra 2/3` | Pandaboard, Galaxy S2, Wii U |

### Modern aarch64 - PENALTY (0.0005x)

Modern ARM processors (Cortex-A53 and later) running on NAS boxes and SBCs are penalized to prevent cheap ARM device spam:

| Architecture | Base | Detection Evidence | Common Platforms |
|--------------|------|--------------------|------------------|
| Cortex-A53/A55 | **0.0005x** | `aarch64` + NAS/SBC markers | Synology DS220+, QNAP, RPi 4/5 |
| Cortex-A72/A76 | **0.0005x** | `aarch64` + consumer SBC | RPi 4, RockPro64, Odroid N2 |
| Ampere Altra | **0.0005x** | `aarch64` + cloud/server | Oracle Cloud, Hetzner ARM |
| AWS Graviton | **0.0005x** | `aarch64` + `graviton` | AWS EC2 ARM instances |

**ARM Detection Evidence (server-side)**:
```python
ARM_NAS_EVIDENCE = [
    "synology", "qnap", "asustor", "terramaster",      # NAS vendors
    "rockchip", "allwinner", "amlogic", "broadcom",     # SoC vendors
    "cortex-a53", "cortex-a55", "cortex-a72", "cortex-a76",
    "bcm2711", "bcm2712",                               # Raspberry Pi 4/5
    "rk3588", "rk3399",                                 # RockChip
]
```

## RISC-V (2010+) - EXOTIC Tier

RISC-V is the open-source ISA. Currently rare enough for mining to qualify as EXOTIC, but this may be adjusted as adoption grows.

**Detection**: `platform.machine()` returns `riscv`, `riscv64`, `riscv32`

| Architecture | Years | Base | Detection Patterns | Platforms |
|--------------|-------|------|--------------------|-----------|
| RV32 (32-bit) | 2016+ | **1.5x** | `riscv32`, `rv32` | Kendryte K210, ESP32-C3, GD32VF103 |
| RV64 (64-bit) | 2018+ | **1.4x** | `riscv64`, `rv64` | SiFive Unmatched, StarFive VisionFive 2, Milk-V |
| RV128 (128-bit) | Future | **1.6x** | `riscv128`, `rv128` | Not yet available -- reserved |

**Known RISC-V Boards**:
- **SiFive HiFive Unmatched** (2021): SiFive U740, quad-core RV64GC, 16GB RAM
- **StarFive VisionFive 2** (2023): JH7110, quad-core RV64GC, up to 8GB RAM
- **Milk-V Mars** (2023): JH7110, similar to VisionFive 2
- **Milk-V Pioneer** (2023): SG2042, 64-core server RISC-V
- **Kendryte K210** (2018): Dual RV64GC + AI accelerator, 8MB SRAM

**CPU Brand Patterns (case-insensitive)**:
```regex
riscv|risc-v|rv[36][24]|sifive|starfive|kendryte|jh7110|sg2042|c906|c910
```

## Game Console CPUs (1994-2006) - EXOTIC Tier

Game console CPUs are custom silicon that cannot be easily replicated. Mining on original console hardware is a strong proof of antiquity.

| Console | CPU | Year | Base | Architecture | Notes |
|---------|-----|------|------|--------------|-------|
| PlayStation 1 | R3000A | 1994 | **2.8x** | MIPS | 33.8688 MHz, see MIPS section |
| Sega Saturn | Dual SH-2 | 1994 | **2.6x** | SuperH | Two SH-2 at 28.6 MHz |
| Nintendo 64 | VR4300 | 1996 | **2.5x** | MIPS | NEC variant at 93.75 MHz |
| Sega Dreamcast | SH-4 | 1998 | **2.3x** | SuperH | 200 MHz, hardware FPU |
| PlayStation 2 | Emotion Engine | 2000 | **2.2x** | MIPS | Custom R5900, 294.912 MHz |
| GameCube | Gekko | 2001 | **2.1x** | PowerPC | IBM 750CXe derivative, 485 MHz |
| Xbox | Celeron (Coppermine) | 2001 | **1.5x** | x86 | 733 MHz Pentium III variant |
| Nintendo DS | ARM7 + ARM9 | 2004 | **2.3x** | ARM | Dual-CPU, 33/67 MHz |
| PlayStation Portable | Allegrex | 2004 | **2.0x** | MIPS | R4000-based, 333 MHz |
| Xbox 360 | Xenon | 2005 | **2.0x** | PowerPC | Tri-core IBM PPE, 3.2 GHz |
| PlayStation 3 | Cell BE | 2006 | **2.2x** | PowerPC | PPE + 7 SPE, legendary parallel arch |
| Wii | Broadway | 2006 | **2.0x** | PowerPC | IBM 750CL, 729 MHz |
| Game Boy Advance | ARM7TDMI | 2001 | **3.0x** | ARM | See Vintage ARM section |

**Console Detection Patterns (case-insensitive)**:
```regex
emotion\s*engine|cell\s*b\.?e\.?|xenon|gekko|broadway|allegrex|vr4300
```

**Note on PS3 Cell BE**: The Cell Broadband Engine is one of the most unique architectures ever produced -- 1 PPE (PowerPC Processing Element) + 7 SPE (Synergistic Processing Elements). Anyone running a miner on a PS3 with Linux deserves every bit of that 2.2x multiplier.

## Ultra-Rare / Dead Architectures - MYTHIC/LEGENDARY Tier

These architectures are so rare that successfully mining on them is practically a museum exhibit. All receive premium multipliers.

### MYTHIC Tier (3.5x) - Virtually Extinct

| Architecture | Years | Base | Detection Patterns | Notes |
|--------------|-------|------|--------------------|-------|
| DEC VAX | 1977-2000 | **3.5x** | `VAX`, `vax` | "Shall we play a game?" Digital Equipment minicomputer legend |
| Inmos Transputer | 1984-1993 | **3.5x** | `Transputer`, `T414`, `T800`, `T9000` | Parallel computing pioneer, Occam language |
| Fairchild Clipper | 1985-1988 | **3.5x** | `Clipper`, `C100`, `C300`, `C400` | Workstation RISC, ultra-rare, Intergraph |
| NS32K | 1982-1990 | **3.5x** | `NS32032`, `NS32332`, `NS32532` | National Semiconductor, the failed x86 killer |
| IBM ROMP | 1986-1990 | **3.5x** | `ROMP`, `RT PC` | First commercial RISC CPU, IBM RT PC |

### LEGENDARY Tier (3.0x) - Extremely Rare

| Architecture | Years | Base | Detection Patterns | Notes |
|--------------|-------|------|--------------------|-------|
| Intel i860 | 1989-1993 | **3.0x** | `i860`, `80860` | "Cray on a chip" -- failed spectacular attempt |
| Intel i960 | 1988-2007 | **3.0x** | `i960`, `80960` | Embedded RISC, military/aerospace, I/O controllers |
| Motorola 88000 | 1988-1992 | **3.0x** | `88000`, `MC88100`, `MC88110` | Killed by the PowerPC alliance (Apple-IBM-Motorola) |
| AMD Am29000 | 1988-1995 | **3.0x** | `Am29000`, `29000`, `29K` | AMD's RISC attempt, dominated laser printers |
| DEC Alpha | 1992-2004 | **3.0x** | `Alpha`, `alpha`, `EV[4-7]` | Fastest CPU of its era, killed by Compaq/HP |
| HP PA-RISC | 1986-2008 | **3.0x** | `PA-RISC`, `PA8[0-9]00`, `hppa` | HP workstations/servers, replaced by Itanium |

### EXOTIC Tier (2.5x) - Rare

| Architecture | Years | Base | Detection Patterns | Notes |
|--------------|-------|------|--------------------|-------|
| Intel Itanium (IA-64) | 2001-2021 | **2.5x** | `Itanium`, `IA-64`, `ia64` | "Itanic" -- dead architecture, extremely rare in the wild |
| IBM S/390 / z/Architecture | 1990-present | **2.5x** | `s390`, `s390x`, `z/Architecture` | Mainframe; z/Architecture still runs but is exotic for mining |
| IBM POWER (non-Apple) | 2001-present | **2.5x** | `POWER[4-9]`, `POWER10`, `power8`, `ppc64le` | Enterprise POWER servers (our S824 gets this!) |
| Tilera TILE | 2007-2014 | **2.5x** | `TILE`, `TILEPro`, `TILE-Gx` | Manycore network processors, 36-100 cores |

**Detection for Ultra-Rare Architectures**:

Most of these will report via `platform.machine()` or `/proc/cpuinfo`:
```python
ULTRA_RARE_MACHINES = {
    'vax':       ('DEC VAX', 3.5),
    'alpha':     ('DEC Alpha', 3.0),
    'hppa':      ('HP PA-RISC', 3.0),
    'hppa64':    ('HP PA-RISC 64', 3.0),
    'ia64':      ('Intel Itanium', 2.5),
    's390':      ('IBM S/390', 2.5),
    's390x':     ('IBM z/Architecture', 2.5),
    'ppc64':     ('IBM POWER (big-endian)', 2.5),
    'ppc64le':   ('IBM POWER (little-endian)', 2.5),
}
```

## Server-Side Architecture Detection

The RustChain server does not blindly trust self-reported architecture claims. This section describes the server-side validation pipeline that cross-checks miner submissions before assigning antiquity multipliers.

### 1. Server Does Not Trust Self-Reported Architecture

Miners submit their `platform.machine()` value and CPU brand string as part of the attestation payload. However, the server treats these as **claims to be verified**, not facts. A miner running on a Synology NAS could trivially set `device_arch: "g4"` in their payload. The server catches this through multiple cross-validation checks.

### 2. `_detect_exotic_arch()` - Machine Field, Brand, and SIMD Evidence

The server-side detection function checks three independent evidence sources:

```python
def _detect_exotic_arch(device: dict, signals: dict) -> tuple:
    """
    Server-side exotic architecture detection.
    Returns (arch_name, multiplier) or (None, None) if not exotic.

    Evidence sources:
    1. platform.machine() field
    2. CPU brand string
    3. SIMD capability evidence (presence/absence)
    4. Cache topology
    5. /proc/cpuinfo raw fields
    """
    machine = device.get('machine', '').lower()
    brand = device.get('cpu_brand', '').lower()
    simd = signals.get('simd_capabilities', [])

    # Check machine field against known exotic architectures
    for arch_key, (arch_name, multiplier) in EXOTIC_ARCH_MAP.items():
        if arch_key in machine:
            return arch_name, multiplier

    # Check CPU brand for exotic keywords
    for pattern, (arch_name, multiplier) in EXOTIC_BRAND_PATTERNS.items():
        if re.search(pattern, brand, re.IGNORECASE):
            return arch_name, multiplier

    # Check SIMD evidence for architecture confirmation
    if 'altivec' in simd or 'vsx' in simd:
        return _classify_powerpc(device, signals)
    if 'vis' in simd:  # Visual Instruction Set = SPARC
        return _classify_sparc(device, signals)

    return None, None
```

### 3. `_detect_arm_evidence()` - Catching NAS/SBC Spoofing

This is the critical function that distinguishes genuine vintage ARM hardware from modern aarch64 NAS/SBC spam:

```python
def _detect_arm_evidence(device: dict, signals: dict) -> tuple:
    """
    Detect ARM architecture and classify as vintage vs modern.

    Returns:
        ('vintage_arm', multiplier) - for genuine vintage ARM hardware
        ('modern_arm_penalty', 0.0005) - for NAS/SBC/cloud ARM spam
        (None, None) - not ARM
    """
    machine = device.get('machine', '').lower()
    brand = device.get('cpu_brand', '').lower()

    # Not ARM at all
    if machine not in ('aarch64', 'armv7l', 'armv6l', 'armv5l', 'arm'):
        return None, None

    # Check for vintage ARM evidence
    VINTAGE_ARM_PATTERNS = [
        (r'arm[236]', 'ARM2/3/6', 3.8),
        (r'arm7tdmi', 'ARM7TDMI', 3.0),
        (r'strongarm|sa-1[01]', 'StrongARM', 2.7),
        (r'xscale|pxa2', 'XScale', 2.5),
        (r'arm9[2-4]', 'ARM9', 2.3),
        (r'arm11[37]', 'ARM11', 2.0),
        (r'cortex-a8', 'Cortex-A8', 1.8),
        (r'cortex-a9', 'Cortex-A9', 1.5),
    ]

    for pattern, name, mult in VINTAGE_ARM_PATTERNS:
        if re.search(pattern, brand, re.IGNORECASE):
            return f'vintage_arm_{name}', mult

    # Check for NAS/SBC/cloud evidence (PENALTY)
    NAS_SBC_EVIDENCE = [
        'synology', 'qnap', 'asustor', 'terramaster',
        'rockchip', 'allwinner', 'amlogic',
        'bcm2711', 'bcm2712',  # RPi 4/5
        'graviton',            # AWS
        'ampere',              # Oracle Cloud
        'cortex-a53', 'cortex-a55', 'cortex-a72', 'cortex-a76', 'cortex-a78',
    ]

    for evidence in NAS_SBC_EVIDENCE:
        if evidence in brand:
            return 'modern_arm_penalty', 0.0005

    # Unknown ARM claiming x86 = flagged
    if machine == 'aarch64':
        return 'modern_arm_penalty', 0.0005  # Default penalty for unrecognized aarch64

    return None, None
```

### 4. Vintage ARM Preserved with Proper Multipliers

The system carefully preserves high multipliers for genuinely vintage ARM hardware while penalizing modern ARM spam. The key distinctions:

| Scenario | Result | Multiplier |
|----------|--------|------------|
| `armv6l` + `ARM1176JZF` brand | Vintage ARM11 | **2.0x** |
| `armv7l` + `Cortex-A8` brand | Vintage Cortex | **1.8x** |
| `aarch64` + `Cortex-A72` brand | Modern SBC penalty | **0.0005x** |
| `aarch64` + `BCM2712` brand | Raspberry Pi 5 penalty | **0.0005x** |
| `aarch64` + `Graviton` brand | AWS cloud penalty | **0.0005x** |
| `aarch64` + unknown brand | Default ARM penalty | **0.0005x** |
| `arm` + `ARM7TDMI` brand | Vintage ARM7 | **3.0x** |
| `arm` + `StrongARM` brand | Vintage StrongARM | **2.7x** |

### 5. Unknown CPU + Claimed x86 = Flagged as ARM

A critical anti-fraud check: if a miner reports `platform.machine()` as `x86_64` but the CPU brand string is empty, unknown, or contains ARM/MIPS keywords, the attestation is flagged:

```python
def _validate_arch_consistency(device: dict, signals: dict) -> bool:
    """
    Cross-validate architecture claims.
    Returns False if claims are inconsistent (potential spoofing).
    """
    machine = device.get('machine', '').lower()
    brand = device.get('cpu_brand', '').lower()
    simd = signals.get('simd_capabilities', [])

    if machine in ('x86_64', 'i686', 'i386'):
        # x86 MUST have SSE evidence
        if not any(s in simd for s in ['sse', 'sse2', 'avx']):
            # No x86 SIMD but claims x86? Likely ARM/MIPS spoofing
            return False

        # Brand should contain Intel/AMD keywords
        if not any(k in brand for k in ['intel', 'amd', 'genuine', 'authentic']):
            if brand and brand != 'unknown':
                # Has a brand but not Intel/AMD -- suspicious
                return False

    return True
```

### SIMD Evidence Cross-Validation

The server uses SIMD instruction set evidence to confirm architecture claims:

| SIMD Capability | Confirms Architecture | Contradicts |
|-----------------|----------------------|-------------|
| `sse`, `sse2`, `avx` | x86/x86_64 | Any non-x86 claim |
| `altivec` | PowerPC (G4/G5) | x86, ARM |
| `vsx` | POWER7+ (POWER8/9/10) | x86, ARM, early PowerPC |
| `neon` | ARM (Cortex-A and later) | x86, PowerPC |
| `vis` | SPARC (VIS 1.0+) | Everything else |
| `msa` | MIPS (MIPS SIMD Architecture) | Everything else |
| `vec_perm` | PowerPC with AltiVec | Confirms genuine PPC |

### Architecture Detection Summary Table

| `platform.machine()` | Expected Brand Keywords | SIMD Evidence | Multiplier Range |
|-----------------------|------------------------|---------------|------------------|
| `x86_64`, `i686` | Intel, AMD | SSE/AVX | 1.0x - 1.5x |
| `ppc`, `ppc64` | PowerPC, G4, G5, 7450, 970 | AltiVec | 1.8x - 2.5x |
| `ppc64le` | POWER8, POWER9 | VSX, vec_perm | 2.5x |
| `sparc`, `sparc64` | UltraSPARC, SPARC | VIS | 1.7x - 2.9x |
| `mips`, `mips64` | R-series, MIPS | MSA | 2.3x - 3.0x |
| `m68k` | 68000-68060, ColdFire | (none) | 1.8x - 3.0x |
| `sh4` | SH-4, SH7750 | (none) | 2.2x - 2.7x |
| `armv6l`, `armv5l` | ARM11, ARM9 | (none) | 2.0x - 2.5x |
| `armv7l` | Cortex-A8/A9 vintage | NEON | 1.5x - 1.8x |
| `aarch64` | (must match vintage) | NEON | **0.0005x** (penalty default) |
| `riscv64` | SiFive, StarFive | (varies) | 1.4x - 1.5x |
| `ia64` | Itanium | (none) | 2.5x |
| `s390x` | z/Architecture | (none) | 2.5x |
| `alpha` | Alpha, EV4-EV7 | (none) | 3.0x |
| `hppa` | PA-RISC, PA8x00 | (none) | 3.0x |
| `vax` | VAX | (none) | 3.5x |

## Server Hardware Bonus

Enterprise-class CPUs receive a **+10% multiplier** on top of base:

| Vendor | Server Patterns | Examples |
|--------|----------------|----------|
| Intel | `Xeon` | Xeon E5-2670 v2, Xeon Gold 6248R |
| AMD | `EPYC`, `Opteron` | EPYC 7742, Opteron 6276 |

**Example**: Xeon E5-1650 v2 (Ivy Bridge)
- Base: 1.1x (Ivy Bridge)
- With time decay (13 years old): ~1.076x
- Server bonus: 1.076 x 1.1 = **1.18x final**

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
- `i7-2600K` -> 2 -> 2nd-gen (Sandy Bridge)
- `i9-12900K` -> 12 -> 12th-gen (Alder Lake)

**Intel Xeon E3/E5/E7 version detection**:
```regex
E[357]-\d+\s*v([2-6])  # Capture v-number
```
- `E5-1650` (no v) -> Sandy Bridge
- `E5-1650 v2` -> Ivy Bridge
- `E5-2680 v4` -> Broadwell

**AMD Ryzen generation detection**:
```regex
Ryzen\s*[3579]\s*(\d)\d{3}  # Capture first digit = series
```
- `Ryzen 7 1700X` -> 1 -> Zen
- `Ryzen 9 5950X` -> 5 -> Zen 3
- `Ryzen 9 9950X` -> 9 -> Zen 5

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
- Pattern: `Ryzen [3579] 8\d{3}` -> Zen4 (2023)
- Next mobile: `Ryzen AI 300` series (Zen5)

### AMD APU Naming

APU series numbers are ahead of CPU series:
- Ryzen 7 7840HS (APU, Zen4) != Ryzen 7 7700X (CPU, Zen4)
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
  -> Vendor: INTEL
  -> Architecture: ivy_bridge
  -> Generation: Intel Ivy Bridge (3rd-gen Core i)
  -> Year: 2012 (Age: 13 years)
  -> Server: Yes
  -> Antiquity Multiplier: 1.1836x

CPU: PowerPC G4 (7450)
  -> Vendor: POWERPC
  -> Architecture: g4
  -> Generation: PowerPC G4 (7450/7447/7455)
  -> Year: 2001 (Age: 24 years)
  -> Server: No
  -> Antiquity Multiplier: 1.645x

CPU: AMD Ryzen 9 7950X 16-Core Processor
  -> Vendor: AMD
  -> Architecture: zen4
  -> Generation: AMD Zen 4 (Ryzen 7000/8000 / EPYC Genoa)
  -> Year: 2022 (Age: 3 years)
  -> Server: No
  -> Antiquity Multiplier: 1.0x
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

### Exotic Architectures
- [SPARC - Wikipedia](https://en.wikipedia.org/wiki/SPARC)
- [MIPS Architecture - Wikipedia](https://en.wikipedia.org/wiki/MIPS_architecture)
- [Motorola 68000 Series - Wikipedia](https://en.wikipedia.org/wiki/Motorola_68000_series)
- [SuperH - Wikipedia](https://en.wikipedia.org/wiki/SuperH)
- [ARM Architecture History - Wikipedia](https://en.wikipedia.org/wiki/ARM_architecture_family)
- [RISC-V - Wikipedia](https://en.wikipedia.org/wiki/RISC-V)
- [DEC Alpha - Wikipedia](https://en.wikipedia.org/wiki/DEC_Alpha)
- [PA-RISC - Wikipedia](https://en.wikipedia.org/wiki/PA-RISC)
- [VAX - Wikipedia](https://en.wikipedia.org/wiki/VAX)
- [Cell (Microprocessor) - Wikipedia](https://en.wikipedia.org/wiki/Cell_(microprocessor))
- [Transputer - Wikipedia](https://en.wikipedia.org/wiki/Transputer)

### General
- [Decoding Processor Puzzle: Intel and AMD 2025 Edition - Technical Explore](https://www.technicalexplore.com/tech/decoding-the-processor-puzzle-intel-and-amd-naming-schemes-explained-2025-edition)

## Future Enhancements

1. **Auto-detection of model year** - Parse more granular release dates
2. **CPUID integration** - Use CPUID instruction for more precise detection
3. **GPU antiquity** - Extend to GPUs (vintage Radeon, GeForce)
4. **Z80/6502 support** - 8-bit CPUs for extreme antiquity (Commodore 64, ZX Spectrum)
5. **FPGA detection** - Xilinx/Altera/Lattice FPGAs as mining accelerators

---

**Last Updated**: 2026-03-19
**Version**: 2.0.0
**File**: `/home/scott/rustchain-complete/cpu_architecture_detection.py`
