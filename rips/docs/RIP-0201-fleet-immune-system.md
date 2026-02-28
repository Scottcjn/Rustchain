# RIP-201: Fleet Detection Immune System

**Status**: Deployed (2026-02-28)
**Author**: Scott Boudreaux (Elyan Labs)
**Type**: Economic Security
**Requires**: RIP-200 (Round-Robin Consensus)

## Abstract

RIP-201 introduces a fleet detection immune system that makes large-scale coordinated mining attacks economically worthless. It replaces per-CPU reward distribution with Equal Bucket Split, where the epoch reward pot is divided equally among active hardware *classes*, not individual CPUs.

## Motivation

Under RIP-200, rewards are distributed pro-rata by time-aged antiquity multiplier. A fleet of 500 identical modern boxes could claim ~99% of the reward pot by sheer count, overwhelming solo miners despite the 1 CPU = 1 Vote design.

**Without RIP-201**: 500 modern boxes earn 200x what a solo G4 earns.
**With RIP-201**: 500 modern boxes share one bucket slice. Solo G4 gets its own. Fleet ROI: $27/year on $5M investment.

## Specification

### Hardware Buckets

Miners are classified into six hardware buckets:

| Bucket | Architectures | Description |
|--------|--------------|-------------|
| `vintage_powerpc` | G3, G4, G5, PowerPC | Classic Macs, pre-Intel |
| `vintage_x86` | Pentium, Core2, retro, Nehalem, Sandy Bridge | Pre-2012 x86 |
| `apple_silicon` | M1, M2, M3 | Modern Apple chips |
| `modern` | x86_64, modern | Current-generation processors |
| `exotic` | POWER8, SPARC | Datacenter/research hardware |
| `arm` | aarch64, armv7 | ARM processors |

### Equal Bucket Split

Each epoch's reward pot (1.5 RTC) is divided equally among buckets that have at least one active miner. Within each bucket, rewards are distributed by time-aged antiquity multiplier (per RIP-200).

```
Bucket share = Total reward / Number of active buckets
Miner share  = Bucket share × (miner_weight / bucket_total_weight)
```

### Fleet Detection Signals

Three vectors detect coordinated mining operations:

1. **IP/Subnet Clustering** (40% weight) — miners sharing /24 subnets
2. **Fingerprint Similarity** (40% weight) — identical hardware fingerprints
3. **Attestation Timing Correlation** (20% weight) — synchronized submission patterns

### Fleet Score

```
fleet_score = (ip_score × 0.4) + (fingerprint_score × 0.4) + (timing_score × 0.2)
```

- Score 0.0–0.3: CLEAN (no penalty)
- Score 0.3–0.7: MODERATE (reward decay applied)
- Score 0.7–1.0: SEVERE (significant penalty)

### Fleet Decay

```python
effective_multiplier = base × (1.0 - fleet_score × FLEET_DECAY_COEFF)
# Floor at 60% of base multiplier
```

### Minimum Detection Threshold

Fleet detection only activates when 4+ miners share signals, preventing false positives on small networks.

## Economics

| Scenario | Without RIP-201 | With RIP-201 |
|----------|-----------------|--------------|
| Solo G4 miner | ~2% of pot | ~16.7% of pot (1/6 buckets) |
| 500 modern boxes | ~99% of pot | ~16.7% of pot (shared) |
| Fleet per-box ROI | 200x solo | 0.005x solo |
| $5M fleet revenue | ~$3,000/year | ~$27/year |
| Fleet payback period | ~1.5 years | ~182,648 years |

## Implementation

- `fleet_immune_system.py` — Core module (signals, scoring, bucket split)
- `rip201_server_patch.py` — Automated patcher for existing server code

## Red Team Bounties

600 RTC in bounties for breaking this system:
- Fleet Detection Bypass: 200 RTC
- Bucket Normalization Gaming: 150 RTC
- False Positive Testing: 100 RTC (+50 bonus)
- Fleet Score Manipulation: 150 RTC

## Design Philosophy

> "Diversity IS the immune system. One of everything beats a hundred of one thing."

The system makes hardware diversity structurally profitable and homogeneous fleets structurally unprofitable, regardless of detection accuracy. Detection is the second line of defense — the economics already killed the attack.
