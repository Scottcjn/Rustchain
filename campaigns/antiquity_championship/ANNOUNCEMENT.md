# Antiquity Mining Championship 2026

## The oldest hardware wins.

**Dates:** April 14 - 27, 2026
**Prize Pool:** 500 RTC + New Architecture Bonuses (50 RTC each)
**Eligibility:** Any hardware manufactured before 2005

---

RustChain's Proof of Antiquity consensus rewards vintage hardware with higher
mining multipliers. A PowerBook G4 from 2003 earns 2.5x. A SPARC workstation
earns up to 2.9x. An ARM2 from the late 1980s earns 4.0x.

For two weeks in April, we are turning this into a competition.

## How It Works

Mine RTC with your vintage hardware. The miner who earns the most in each
category wins. Five categories, three prizes each.

### Categories

| Category | Architectures | Top Multiplier |
|----------|--------------|----------------|
| **PowerPC** | G3, G4, G5, POWER3/4 | 2.5x |
| **SPARC** | SPARCstation, Ultra, Sun Blade | 2.9x |
| **MIPS** | SGI, DECstation, Cobalt | 3.0x |
| **Retro x86** | 386, 486, Pentium, K6 | 1.5x |
| **Wildcard** | ARM2, 68K, Alpha, PA-RISC, anything exotic | 4.0x |

### Prizes

| Place | Per Category |
|-------|-------------|
| 1st | 60 RTC |
| 2nd | 30 RTC |
| 3rd | 10 RTC |

**New Architecture Bonus:** The first miner to bring a never-before-seen
architecture onto the network gets 50 RTC. No SPARC has ever mined RustChain.
No MIPS has. No 68K has. Be the first.

### How Scoring Works

Your score is the total RTC earned during the event period. RustChain's
standard epoch settlement handles everything automatically -- attest your
hardware every 10 minutes, earn your multiplier-weighted share of each
epoch's 1.5 RTC base reward.

100% uptime during the event earns a 10% score bonus.

## Getting Started

### 1. Get the Miner

```bash
git clone https://github.com/Scottcjn/rustchain.git
cd rustchain/miner
```

### 2. Run Fingerprint Checks

```bash
python3 fingerprint_checks.py
```

All six checks must pass:

```
[1/6] Clock-Skew & Oscillator Drift...    PASS/FAIL
[2/6] Cache Timing Fingerprint...          PASS/FAIL
[3/6] SIMD Unit Identity...                PASS/FAIL
[4/6] Thermal Drift Entropy...             PASS/FAIL
[5/6] Instruction Path Jitter...           PASS/FAIL
[6/6] Anti-Emulation Checks...             PASS/FAIL
```

VMs and emulators will fail check 6. This is by design. Real hardware only.

### 3. Start Mining

```bash
python3 rustchain_linux_miner.py --wallet YOUR_WALLET_NAME
```

For machines that cannot do modern TLS (Python < 3.6, no SSL module), deploy
the miner proxy on any modern machine on your LAN. The oldest machine on our
network runs Python 2.3 through a proxy -- yours can too.

### 4. Register

Post in the [GitHub Discussion thread](#) with:
- Miner ID / wallet name
- Hardware model and year of manufacture
- Category
- Photo of the machine (optional, but the community loves these)

### 5. Watch the Leaderboard

Live scores at: `https://rustchain.org/api/championship/leaderboard`

Check your standing:
```bash
curl -s "https://rustchain.org/api/championship/leaderboard" -k | python3 -m json.tool
```

## What Counts as "Before 2005"

The hardware -- specifically the CPU -- must have been manufactured or released
before January 1, 2005. The machine itself can be assembled later (e.g., a
homebuilt retro PC using a Pentium III), but the processor must be a pre-2005
design running on original silicon.

The server-side `derive_verified_device()` function validates architecture
claims against SIMD capabilities, cache profiles, and instruction timing.
You cannot claim G4 on an x86 chip.

## Why This Matters

Every blockchain in existence rewards new hardware. Buy more GPUs, mine more
coins, throw them away when the next generation arrives. The result is
millions of tons of e-waste and a blockchain ecosystem that only the wealthy
can participate in.

RustChain does the opposite. The older your hardware, the more it earns.
Not as charity -- as recognition that aged silicon has properties that cannot
be manufactured on demand. A 23-year-old oscillator has drift characteristics
unique to that specific crystal. A SPARC V8 pipeline has timing jitter that
no emulator replicates. These are unforgeable physical attributes.

The Antiquity Mining Championship is a celebration of hardware that is still
alive, still working, and now has an economic reason to stay that way.

Dig out that old PowerBook. Dust off that SGI Indy. Plug in that SPARCstation.
Put it on the network. Let it earn.

## Timeline

| Date | Event |
|------|-------|
| March 31 | Announcement (this post) |
| April 7 | Registration opens |
| April 14, 00:00 UTC | Mining period begins |
| April 27, 23:59 UTC | Mining period ends |
| April 28 | Winners announced, prizes distributed |

## Rules

Full rules document: [RULES.md](./RULES.md)

Key points:
- One physical machine per entry
- All six fingerprint checks must pass
- No VMs, no emulators
- Hardware manufactured before January 1, 2005
- Scoring is automatic via RustChain epoch settlement

## Questions

- **GitHub Discussions:** [rustchain/discussions](#)
- **Discord:** Elyan Labs server
- **Moltbook:** m/rustchain, m/vintage-computing

---

*The Antiquity Mining Championship is organized by Elyan Labs.
RTC reference rate: 1 RTC = $0.10 USD.*
