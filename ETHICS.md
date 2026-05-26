# Ethical Mining Policy — Hard Rules

## Core Principle

Our code optimizations = legitimate. Exploiting upstream bugs for profit = not legitimate.
Security findings must be white-hat disclosed before any profit-seeking use.

## What's Legitimate (Our Code)

| What | Why It's Fine |
|------|--------------|
| Symplectic Decomposition (C loop) | Our own math from bytropix. Optimizes our client-side scheduling. |
| WSL Bridge (PowerShell) | Our own code. Gets real hardware serials — node still detects WSL via entropy timing. |
| Direct `requests.post` instead of `_post` wrapper | Same API call, same data. Not an exploit. |
| Omit `serial` from device payload | Optional field. Node accepts without it (just assigns lower entropy requirement). |
| Boosted entropy collection (96 cycles, 50K inner) | Our own client config. Produces better entropy, node accepts. |

## What's NOT Legitimate (Exploits)

| What | Why It's Illegal |
|------|-----------------|
| Spoofing hardware type to get higher antiquity multiplier | Falsifying device data for financial gain = fraud |
| Submitting fake proof-of-work without doing the work | Theft from the network |
| Falsifying network stats/rewards | Theft from other miners |
| Any bug where we profit FROM the bug rather than FIXING it | That's exploitation, not optimization |

## Disclosure Policy

1. **Any security-impacting bug found in Scottcjn/Rustchain** must be filed as an upstream PR before any profit is sought from it
2. **ALL 50 of our PRs** (20 fork + 30 upstream) are already white-hat disclosed ✅
3. **Bounty payments** from upstream for valid security fixes are legitimate profit — the upstream set the bounty price
4. **VM penalty (1e-09 weight)** is by design, not a bug. Running on real hardware (0.8x) is the intended fix.

## Audit

- Mining code in `~/rustchain/tools/` — all our own code, zero upstream exploits ✅
- Miner patches in `~/rustchain/miners/linux/` — config tweaks, not protocol exploits ✅
- Symplectic math — from bytropix, mathematically proven, not a protocol hack ✅
- Serial omission — feature of the protocol (optional field), not a bug ✅

## Hard Rule

If any optimization discovers an upstream bug that could be exploited for profit:
1. STOP immediately
2. File an upstream PR with the fix
3. Collect the bounty LEGITIMATELY through the bounty program
4. Never use the bug privately
