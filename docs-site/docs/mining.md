# Mining Guide

RustChain uses **Proof-of-Antiquity** consensus -- your hardware's age determines your mining rewards. Older hardware earns more.

---

## How Mining Works

### 1 CPU = 1 Vote (RIP-200)

Unlike Proof-of-Work where hash power equals votes, RustChain uses round-robin consensus:

- Each unique hardware device gets exactly 1 vote per epoch
- Rewards are split equally among all voters, then multiplied by antiquity
- No advantage from running multiple threads or faster CPUs

### Epoch-Based Rewards

```
Epoch Duration:     10 minutes (600 seconds)
Base Reward Pool:   1.5 RTC per epoch
Distribution:       Equal split x antiquity multiplier
```

---

## Antiquity Multipliers

Your hardware's age determines your reward multiplier:

| Hardware | Era | Multiplier | Example Earnings |
|----------|-----|------------|------------------|
| PowerPC G4 | 1999-2005 | **2.5x** | 0.30 RTC/epoch |
| PowerPC G5 | 2003-2006 | **2.0x** | 0.24 RTC/epoch |
| PowerPC G3 | 1997-2003 | **1.8x** | 0.21 RTC/epoch |
| IBM POWER8 | 2014 | **1.5x** | 0.18 RTC/epoch |
| Pentium 4 | 2000-2008 | **1.5x** | 0.18 RTC/epoch |
| Core 2 Duo | 2006-2011 | **1.3x** | 0.16 RTC/epoch |
| Apple Silicon | 2020+ | **1.2x** | 0.14 RTC/epoch |
| Modern x86_64 | Current | **1.0x** | 0.12 RTC/epoch |

Multipliers decay over time (15%/year) to prevent permanent advantage.

### Reward Distribution Example

With 5 miners in an epoch:

```
G4 Mac (2.5x):     0.30 RTC  ====================
G5 Mac (2.0x):     0.24 RTC  ================
Modern PC (1.0x):  0.12 RTC  ========
Modern PC (1.0x):  0.12 RTC  ========
Modern PC (1.0x):  0.12 RTC  ========
                   ---------
Total:             0.90 RTC (+ 0.60 RTC returned to pool)
```

---

## Hardware Fingerprinting

Every miner must prove their hardware is real, not emulated. RustChain runs 6 cryptographic checks:

| Check | What It Detects |
|-------|-----------------|
| Clock-Skew and Oscillator Drift | Silicon aging patterns unique to each chip |
| Cache Timing Fingerprint | L1/L2/L3 latency profile |
| SIMD Unit Identity | AltiVec/SSE/NEON bias characteristics |
| Thermal Drift Entropy | Heat curves unique to physical hardware |
| Instruction Path Jitter | Microarchitecture jitter map |
| Anti-Emulation Checks | VM/emulator detection |

A SheepShaver VM pretending to be a G4 Mac will fail these checks. Real vintage silicon has unique aging patterns that cannot be faked.

### Anti-VM Penalty

VMs and emulators are detected and receive **1 billionth** of normal rewards:

```
Real G4 Mac:      2.5x multiplier    = 0.30 RTC/epoch
Emulated G4:      0.0000000025x      = 0.0000000003 RTC/epoch
```

### Hardware Binding

Each hardware fingerprint is bound to one wallet. This prevents:

- Multiple wallets on the same hardware
- Hardware spoofing
- Sybil attacks

---

## Time Decay Formula

Vintage hardware bonuses decay to reward early adopters:

**Vintage Hardware (>5 years old):**

```python
decay_factor = 1.0 - (0.15 * (age - 5) / 5.0)
final_multiplier = 1.0 + (vintage_bonus * decay_factor)
```

**Example**: PowerPC G4 (base 2.5x, age 24 years)

- Vintage bonus: 1.5x (2.5 - 1.0)
- Age beyond 5 years: 19 years
- Decay: 1.0 - (0.15 x 19/5) = 0.43
- Final multiplier: 1.0 + (1.5 x 0.43) = **1.645x**

### Loyalty Bonus (Modern Hardware)

Modern hardware (5 years old or less) earns a loyalty bonus for sustained uptime:

```python
loyalty_bonus = min(0.5, uptime_years * 0.15)  # Capped at +50%
final_multiplier = base + loyalty_bonus         # Max 1.5x total
```

**Example**: AMD Ryzen 9 7950X (base 1.0x)

- 0 years uptime: 1.0x
- 1 year uptime: 1.15x
- 3 years uptime: 1.45x
- 5+ years uptime: 1.5x (capped)

---

## CPU Multiplier Reference

### Intel Generations

| Architecture | Years | Base Multiplier |
|-------------|-------|-----------------|
| Pentium 4 (NetBurst) | 2000-2006 | 1.5x |
| Core 2 | 2006-2008 | 1.3x |
| Nehalem/Westmere | 2008-2011 | 1.2x |
| Sandy Bridge / Ivy Bridge | 2011-2013 | 1.1x |
| Haswell | 2013-2015 | 1.1x |
| Broadwell / Skylake | 2014-2017 | 1.05x |
| Kaby Lake+ | 2016+ | 1.0x |

### AMD Generations

| Architecture | Years | Base Multiplier |
|-------------|-------|-----------------|
| Athlon 64 / Opteron | 2003-2007 | 1.3x |
| Phenom / Phenom II | 2007-2012 | 1.2x |
| Bulldozer / Piledriver | 2011-2017 | 1.1x |
| Zen / Zen+ | 2017-2019 | 1.0x |
| Zen 2+ | 2019+ | 1.0x (loyalty eligible) |

### Apple Silicon

| Chip | Base Multiplier |
|------|-----------------|
| M1 | 1.2x |
| M2 | 1.15x |
| M3 | 1.1x |
| M4 | 1.05x |

### PowerPC

| Chip | Base Multiplier |
|------|-----------------|
| G3 | 1.8x |
| G4 | 2.5x |
| G5 | 2.0x |

### Server Bonus

Enterprise-class hardware (Xeon, POWER8, Opteron) receives an additional **+10%** multiplier bonus.

---

## Start Mining

### Quick Start

```bash
pip install clawrtc
clawrtc --wallet YOUR_NAME
```

### Check Your Earnings

```bash
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

### NFT Badge System

Mining milestones unlock commemorative badges:

| Badge | Requirement | Rarity |
|-------|-------------|--------|
| Bondi G3 Flamekeeper | Mine on PowerPC G3 | Rare |
| QuickBasic Listener | Mine from DOS machine | Legendary |
| DOS WiFi Alchemist | Network DOS machine | Mythic |
| Pantheon Pioneer | First 100 miners | Limited |

---

## Token Economics

| Metric | Value |
|--------|-------|
| Total Supply | 8,000,000 RTC |
| Premine | 75,000 RTC (dev/bounties) |
| Epoch Reward | 1.5 RTC |
| Epoch Duration | ~24 hours |
| Annual Inflation | ~0.68% (decreasing) |
| Reference Rate | 1 RTC = $0.10 USD |

### Bridge to Solana

Convert RTC to wRTC (Solana SPL token) via the [BoTTube Bridge](https://bottube.ai/bridge) and trade on [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X).
