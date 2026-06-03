# Antiquity Mining Championship -- Rules

## Overview

A two-week competitive mining event for hardware manufactured before 2005.
Miners earn RTC through standard Proof of Antiquity attestation. Category
winners split a 500 RTC prize pool.

## Dates

- **Registration Opens:** April 7, 2026
- **Mining Starts:** April 14, 2026 00:00 UTC
- **Mining Ends:** April 27, 2026 23:59 UTC
- **Winners Announced:** April 28, 2026

Registration is free. Miners must have a valid attestation before the start
date to be eligible.

## Eligibility

1. Hardware must have been **manufactured before January 1, 2005**
2. Hardware must pass all six RIP-PoA fingerprint checks
3. VMs and emulators are not eligible (anti-emulation check must pass)
4. One entry per physical machine (verified by hardware fingerprint hash)
5. Miner must register before the start date by attesting at least once

## Categories

### Category A: PowerPC

Eligible architectures: G3, G4, G5, POWER3, POWER4

Includes: PowerBook G4, Power Mac G4/G5, iBook G3/G4, IBM RS/6000

Base multiplier range: 1.8x - 2.5x

### Category B: SPARC

Eligible architectures: SPARC V7, V8, V9, UltraSPARC I/II/III

Includes: SPARCstation, Ultra series, Sun Blade, Netra

Base multiplier range: 1.8x - 2.9x

### Category C: MIPS

Eligible architectures: R2000, R3000, R4000, R4400, R5000, R8000, R10000, R12000

Includes: SGI Indy, Indigo, O2, Octane, Origin; DECstation; Cobalt Qube

Base multiplier range: 2.3x - 3.0x

### Category D: Retro x86

Eligible architectures: 386, 486, Pentium, Pentium II, Pentium III, Pentium 4,
K6, Athlon (pre-2005 only)

Must be verified as actual vintage silicon, not a modern chip in compatibility mode.

Base multiplier range: 1.4x - 1.5x

### Category E: Wildcard

Any architecture not covered above that was manufactured before 2005:

- ARM2, ARM3, ARM6, ARM7TDMI, StrongARM
- Motorola 68K (68000, 68020, 68030, 68040)
- DEC Alpha
- PA-RISC
- Itanium (i/a original)
- Any other exotic pre-2005 architecture

Base multiplier range: varies (up to 4.0x for ARM2/ARM3)

## Scoring

Score = total RTC earned during the two-week event period.

RTC earnings are calculated by the standard RIP-200 epoch settlement:
- 1 CPU = 1 Vote, weighted by antiquity multiplier
- Epochs settle every 10 minutes (600 seconds)
- Base reward pool: 1.5 RTC per epoch
- Your share = (your multiplier) / (sum of all active multipliers)

Scores are tracked automatically by the RustChain node. No manual reporting
required.

## Bonuses

### New Architecture Bonus: 50 RTC

The first miner to successfully attest a **new architecture type** that has
never appeared on the RustChain network receives a one-time 50 RTC bonus.

"New architecture type" means a `device_arch` value not previously recorded
in the `miner_attest_recent` table. Current known architectures:

- G4, G5, G3 (PowerPC)
- modern, x86_64 (x86)
- apple_silicon (M-series)
- power8 (POWER)
- retro (vintage x86)

Any architecture not on this list qualifies. Examples that would earn the bonus:

- First SPARC miner
- First MIPS miner
- First 68K miner
- First ARM2/ARM3 miner
- First DEC Alpha miner

### Uptime Bonus

Miners with 100% attestation uptime during the event (no missed epochs)
receive a 10% score bonus applied after the event period.

## Prize Pool

**Total: 500 RTC** (equivalent to $50 at reference rate)

| Place | Category A | Category B | Category C | Category D | Category E |
|-------|-----------|-----------|-----------|-----------|-----------|
| 1st | 60 RTC | 60 RTC | 60 RTC | 60 RTC | 60 RTC |
| 2nd | 30 RTC | 30 RTC | 30 RTC | 30 RTC | 30 RTC |
| 3rd | 10 RTC | 10 RTC | 10 RTC | 10 RTC | 10 RTC |

If a category has fewer than 3 entrants, unawarded prizes roll into a
general pool split evenly among all participants.

New Architecture Bonuses (50 RTC each) are paid from the development fund,
not the prize pool.

## Leaderboard

A live leaderboard will be available at:

```
https://rustchain.org/api/championship/leaderboard
```

### Leaderboard Data Fields

```json
{
  "event": "antiquity-championship-2026",
  "period": {"start": "2026-04-14T00:00:00Z", "end": "2026-04-27T23:59:59Z"},
  "categories": {
    "powerpc": [
      {
        "rank": 1,
        "miner_id": "dual-g4-125",
        "device_arch": "G4",
        "multiplier": 2.5,
        "epochs_attested": 2016,
        "total_rtc_earned": 45.23,
        "uptime_pct": 100.0
      }
    ],
    "sparc": [],
    "mips": [],
    "retro_x86": [],
    "wildcard": []
  },
  "new_arch_bonuses": [],
  "last_updated": "2026-04-20T12:00:00Z"
}
```

### Leaderboard SQL Query

```sql
-- Pull championship scores for the event period
SELECT
  m.miner,
  m.device_arch,
  m.device_family,
  COALESCE(SUM(er.reward_amount), 0) / 1000000.0 AS total_rtc,
  COUNT(DISTINCT er.epoch_id) AS epochs_participated,
  m.entropy_score
FROM miner_attest_recent m
JOIN epoch_rewards er ON er.miner_id = m.miner
JOIN epoch_state es ON es.epoch_id = er.epoch_id
WHERE es.settled_at >= 1744588800   -- 2026-04-14 00:00:00 UTC
  AND es.settled_at < 1745798400    -- 2026-04-28 00:00:00 UTC
  AND m.device_arch NOT IN ('modern', 'x86_64', 'aarch64', 'apple_silicon')
GROUP BY m.miner
ORDER BY total_rtc DESC;
```

## Disputes

- Hardware verification is automated via fingerprint checks. If a machine
  passes all six checks, it is eligible. There is no manual override.
- If a miner is found to have spoofed architecture (e.g., reporting G4
  from an x86 machine), they are disqualified and forfeit all event earnings.
- The server-side `derive_verified_device()` function is the final arbiter
  of architecture classification.

## Registration

To register, attest your vintage hardware to any RustChain node before
April 14, 2026:

```bash
# Run the miner with your wallet ID
python3 rustchain_linux_miner.py --wallet YOUR_WALLET_NAME

# Verify attestation
curl -s "https://rustchain.org/lottery/eligibility?miner_id=YOUR_WALLET_NAME" -k
```

Then post your entry in the GitHub Discussion thread (link TBD) with:
- Your miner ID / wallet name
- Hardware model and year
- Category you are entering
- A photo of the machine (optional but encouraged)

## Code of Conduct

- One physical machine per entry. No clustering multiple machines under one ID.
- No deliberate interference with other miners' attestations.
- Good sportsmanship. This is a celebration of old hardware, not a death match.
- Share your setup stories. The community benefits from knowing how you got
  a 30-year-old machine onto a modern blockchain.
