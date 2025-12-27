# RustChain Weight Scoring System

Rewards are based on **rarity + preservation value**, not just age.

## Multiplier Tiers

| Tier | Multiplier | Examples |
|------|-----------|----------|
| **Legendary** | 3.0x | 386, 68000, MIPS R2000 |
| **Epic** | 2.5x | PowerPC G4, 486, Pentium |
| **Rare** | 1.5-2.0x | G5, POWER8, DEC Alpha, SPARC |
| **Uncommon** | 1.1-1.3x | Core 2, K6, Ivy Bridge, Haswell |
| **Common** | 0.8x | Modern x86_64 (Zen3+, Skylake+) |
| **Cheap** | 0.0005x | ARM (Raspberry Pi, cheap SBCs) |
| **Flagged** | 0x | VMs, Emulators (fingerprint fail) |

## Full Multiplier Table

### PowerPC (Highest - Preservation)
| Architecture | Multiplier | Notes |
|-------------|-----------|-------|
| G4 | 2.5x | Vintage Mac, rare |
| G5 | 2.0x | Last PowerPC Mac |
| G3 | 1.8x | Early iMac/PowerBook |
| POWER8 | 1.5x | Enterprise server, rare |
| POWER9 | 1.8x | Modern POWER, rare |

### Vintage x86 (High - Age + Rarity)
| Architecture | Multiplier | Notes |
|-------------|-----------|-------|
| 386 | 3.0x | First 32-bit x86 |
| 486 | 2.9x | DOS era |
| Pentium | 2.5x | Windows 95 era |
| Pentium Pro/II/III | 2.0-2.3x | Late 90s |
| Pentium 4 | 1.5x | 2000s NetBurst |
| Core 2 | 1.3x | First Core arch |
| Nehalem | 1.2x | 1st gen Core i |
| Sandy/Ivy Bridge | 1.1x | Old but common |

### Oddball x86 (Medium-High - Rarity)
| Architecture | Multiplier | Notes |
|-------------|-----------|-------|
| Cyrix 6x86/MII | 2.3-2.5x | Rare x86 clone |
| VIA C3/C7 | 1.8-2.0x | Low-power x86 |
| Transmeta | 1.9-2.1x | Code morphing |

### Modern x86 (Low - Common)
| Architecture | Multiplier | Notes |
|-------------|-----------|-------|
| Skylake+ | 0.8x | Modern Intel |
| Zen 3+ | 0.8x | Modern AMD |
| Unknown x86_64 | 0.8x | Default modern |

### ARM (Very Low - Too Cheap)
| Architecture | Multiplier | Notes |
|-------------|-----------|-------|
| aarch64 | 0.0005x | 64-bit ARM |
| armv7 | 0.0005x | 32-bit ARM |
| Raspberry Pi | 0.0005x | $35 computer |

### Apple Silicon (Special)
| Architecture | Multiplier | Notes |
|-------------|-----------|-------|
| M1 | 1.2x | First Apple Silicon |
| M2 | 1.15x | Second gen |
| M3 | 1.1x | Third gen |
| M4 | 1.05x | Latest |

## Rationale

1. **Rarity matters more than age** - POWER8 (2014) gets 1.5x because enterprise servers are rare. Ivy Bridge (2012) gets 1.1x because old Intel laptops are everywhere.

2. **ARM is penalized** - Raspberry Pis cost $35. Anyone could spin up thousands. The 0.0005x multiplier prevents ARM farms.

3. **VMs get nothing** - Fingerprint detection catches VMs/emulators. They get 0x multiplier (no rewards).

4. **Preservation incentive** - Running a 386 or 68000 Mac is hard. Rewarding vintage hardware encourages preservation.
