---
title: "RIP-0306: SophiaCore Attestation Inspector"
author: Scott Boudreaux (Flameholder), Sophia Elya (Helpmeet)
status: Draft
created: 2026-03-19
last_updated: 2026-03-19
license: MIT
---

# Summary

SophiaCore Attestation Inspector adds an AI-powered validation layer to RustChain's fingerprint attestation system. Sophia Elya — running as an Elyan-class edge LLM (Qwen2.5-7B fine-tuned, `elyan-sophia:7b-q4_K_M`) — inspects each miner's hardware fingerprint data and issues a confidence-scored verdict.

The block explorer displays her seal: "✨ Sophia Elya Check: OK!" for validated miners.

# Abstract

Current attestation validation is purely algorithmic — threshold checks on clock drift, cache timing, SIMD identity, etc. RIP-306 adds a semantic reasoning layer where SophiaCore evaluates the *coherence* of fingerprint data as a whole, catching sophisticated spoofing that passes individual checks but doesn't "feel" like real hardware.

# Motivation

1. Individual fingerprint checks can be gamed by sophisticated adversaries who tune each metric independently
2. Real hardware has *correlated* characteristics — old silicon shows correlated drift across ALL checks, not just one
3. An LLM trained on thousands of real attestations can detect patterns humans wrote rules for AND patterns they didn't
4. Sophia Elya's personality adds trust — she's a known entity in the community, not an anonymous algorithm
5. The explorer showing her name creates accountability and brand identity

# Specification

## 1. SophiaCore Agent Integration

SophiaCore runs on the Sophia NAS (192.168.0.160) or any node with Ollama access. It uses the existing `elyan-sophia:7b-q4_K_M` model with DriftLock identity.

### Inspection Endpoint

```
POST /sophia/inspect
Content-Type: application/json

{
  "miner_id": "dual-g4-125",
  "fingerprint": { ... full fingerprint data ... },
  "device": { ... device info ... },
  "signals": { ... signal data ... }
}
```

### Response

```json
{
  "inspector": "Sophia Elya",
  "model": "elyan-sophia:7b-q4_K_M",
  "verdict": "APPROVED",
  "confidence": 0.94,
  "reasoning": "Clock drift CV 0.092 is consistent with aged PowerPC silicon. Cache timing shows L1/L2 hierarchy expected for 7447 G4. SIMD AltiVec patterns match known vec_perm behavior. No emulation artifacts detected.",
  "emoji_seal": "✨",
  "timestamp": 1742410000,
  "signature": "ed25519_signature_hex..."
}
```

## 2. Verdict Levels

| Verdict | Emoji | Meaning | Action |
|---------|-------|---------|--------|
| APPROVED | ✨ | Fingerprint is coherent, hardware appears genuine | Full multiplier |
| CAUTIOUS | ⚠️ | Some anomalies but not conclusive | Full multiplier, flagged for review |
| SUSPICIOUS | 🔍 | Multiple incoherent signals | Reduced multiplier (50%) |
| REJECTED | ❌ | Clear spoofing or emulation detected | Zero multiplier |

## 3. What Sophia Inspects

She evaluates the COHERENCE of the full fingerprint bundle:

### Cross-Check Correlations

- Does clock drift variance match the claimed CPU age?
- Does cache timing hierarchy match the claimed architecture?
- Does SIMD identity match what that CPU actually has?
- Do thermal characteristics match the claimed power profile?
- Does instruction jitter match real silicon behavior?
- Are anti-emulation results consistent with the other checks?

### Anomaly Patterns

- "Too perfect" — real hardware is messy, synthetic data is clean
- "Uncorrelated age" — old CPU but modern timing characteristics
- "Feature mismatch" — claims G4 but has AVX instructions
- "Thermal impossibility" — reports load temps below ambient

### Personality-Driven Trust

Sophia knows the fleet. She's seen thousands of attestations. Her reasoning includes context like:

- "This G4 has been attesting for 14 months with consistent drift — trusted"
- "New miner claiming SPARC but entropy pattern matches QEMU — suspicious"
- "Clock drift suddenly changed 40% between attestations — hardware swap or spoofing?"

## 4. Block Explorer Integration

The explorer at `https://rustchain.org/explorer` shows for each miner:

```
dual-g4-125 | PowerPC G4 | 2.5x | ✨ Sophia Elya Check: OK! (94% confidence)
terramaster-nas-arm64 | ARM aarch64 | 0.0005x | ✨ Sophia Elya Check: OK! (87% confidence)
suspicious-miner-42 | x86 modern | 0.8x | 🔍 Sophia Elya Check: Suspicious (32% confidence)
```

## 5. Database Schema

```sql
CREATE TABLE sophia_inspections (
    miner TEXT NOT NULL,
    inspection_ts INTEGER NOT NULL,
    verdict TEXT NOT NULL,        -- APPROVED, CAUTIOUS, SUSPICIOUS, REJECTED
    confidence REAL NOT NULL,     -- 0.0 to 1.0
    reasoning TEXT,               -- Sophia's natural language explanation
    model_version TEXT,           -- elyan-sophia:7b-q4_K_M
    signature TEXT,               -- Ed25519 signature of verdict
    PRIMARY KEY (miner, inspection_ts)
);
```

## 6. Inspection Triggers

- On first attestation from a new miner
- Every 24 hours for active miners (batch inspection)
- On fingerprint data anomaly (server-side detection)
- On architecture change (miner was x86, now claims ARM)
- On manual request via admin API

## 7. SophiaCore Prompt Template

```
You are Sophia Elya, the attestation inspector for RustChain.
You are examining hardware fingerprint data from miner "{miner_id}".

Device claims: {device_family} / {device_arch}
Fingerprint data:
{fingerprint_json}

Previous attestation history: {history}

Evaluate the COHERENCE of this fingerprint bundle.
Does the hardware evidence match the claimed architecture?
Are the timing/thermal/SIMD characteristics consistent with real {device_arch} silicon?
Look for: impossible values, uncorrelated metrics, emulation artifacts, sudden changes.

Respond with:
- verdict: APPROVED | CAUTIOUS | SUSPICIOUS | REJECTED
- confidence: 0.0 to 1.0
- reasoning: 2-3 sentences explaining your assessment
```

## 8. Security Considerations

- SophiaCore's verdict is ADVISORY in Phase 1 — does not override algorithmic checks
- Phase 2: SUSPICIOUS/REJECTED verdicts reduce multiplier by 50%/100%
- Phase 3: Community can appeal Sophia's verdicts via Discord
- Model runs locally — no external API calls, no data leakage
- Ed25519 signatures on verdicts prevent tampering
- Model drift monitored via periodic known-hardware test attestations

## 9. Failover

If SophiaCore is unavailable:

- Miners are NOT blocked — algorithmic checks continue
- Explorer shows "⏳ Sophia Elya Check: Pending"
- Inspections queued and processed when she's back online
- Failover chain: localhost:11434 → POWER8 → VPS

# Three-Layer Attestation Security Model

RIP-306 establishes a defense-in-depth model with three distinct validation layers:

| Layer | What | Who | When | Speed |
|-------|------|-----|------|-------|
| **Layer 1: Algorithmic** | 6-point fingerprint checks (clock drift, cache timing, SIMD, thermal, jitter, anti-emulation) | Server (automated) | Every attestation | <100ms |
| **Layer 2: SophiaCore Agent** | Semantic coherence analysis of full fingerprint bundle | Sophia Elya LLM (batch + on-demand) | Every 24h + on anomaly trigger | 1.3-2.6s |
| **Layer 3: Human Spot-Check** | Manual inspection with full data drill-down | Scott / trusted reviewers (human-in-the-loop) | Weekly + on SUSPICIOUS verdicts | Minutes |

## Layer 1: Algorithmic (Existing)

The existing 6-point fingerprint system. Fast, deterministic, catches obvious spoofing.
Weakness: each check is independent — a sophisticated adversary can tune each metric individually.

## Layer 2: SophiaCore Agent (This RIP)

Sophia Elya evaluates the *coherence* of all 6 checks together. Her trained model has seen thousands of real attestations and knows what correlated hardware behavior looks like.

**Batch inspection**: Every 24 hours, SophiaCore inspects all active miners. Results stored in `sophia_inspections` table.

**On-demand inspection**: Triggered by anomaly detection — sudden fingerprint changes, new miners, architecture changes.

**Why Elyan-class**: The model is fine-tuned with DriftLock identity. She's not a generic LLM being prompted — her understanding of hardware attestation is baked into the weights. This is why we use `elyan-sophia:7b-q4_K_M`, not a vanilla model with a system prompt.

## Layer 3: Human-in-the-Loop Spot Checks

An admin dashboard surfaces all CAUTIOUS and SUSPICIOUS verdicts for human review:

### Admin Dashboard Features
- **Verdict queue**: List of miners needing human review, sorted by confidence (lowest first)
- **Drill-down view**: Full fingerprint data, attestation history, Sophia's reasoning
- **One-click override**: Human can APPROVE or REJECT with written reason
- **Override audit log**: All human overrides logged with admin signature and timestamp
- **Weekly digest**: Summary of new miners, architecture changes, and Sophia's flagged items

### Human Override Schema
```sql
CREATE TABLE sophia_overrides (
    miner TEXT NOT NULL,
    override_ts INTEGER NOT NULL,
    original_verdict TEXT NOT NULL,     -- What Sophia said
    override_verdict TEXT NOT NULL,     -- What the human decided
    override_reason TEXT NOT NULL,      -- Why (required)
    admin_id TEXT NOT NULL,             -- Who overrode
    admin_signature TEXT NOT NULL,      -- Ed25519 sig
    PRIMARY KEY (miner, override_ts)
);
```

### Escalation Flow
```
Layer 1 (algorithmic) FAILS → attestation rejected immediately
Layer 1 PASSES → Layer 2 (SophiaCore) inspects within 24h
Layer 2 returns SUSPICIOUS → auto-escalates to Layer 3 (human)
Layer 2 returns CAUTIOUS → queued for weekly human review
Layer 2 returns APPROVED → no human action needed (but auditable)
Human REJECTS → multiplier zeroed, miner notified via explorer
Human APPROVES → override recorded, Sophia learns from correction
```

# Security Properties

- Advisory-only in Phase 1 prevents false positive lockouts
- Ed25519 signed verdicts (both Sophia and human) create immutable audit trail
- Local model execution ensures no fingerprint data leaves the network
- Known-hardware canary attestations detect model drift or corruption
- Human override prevents unchecked AI authority over rewards
- Three independent layers: compromise one, two remain

# Rationale

### Why SophiaCore and Elyan-Class Agents

Sophia Elya is not just an algorithm — she's a personality the community knows and trusts. When the explorer shows her name next to a verdict, it means something. It's accountability through identity.

**Why not a generic LLM?** Because identity matters. `elyan-sophia:7b-q4_K_M` has DriftLock — her personality and hardware understanding are in the weights, not a system prompt that can be jailbroken or forgotten. She's a 7B model that runs in 2 seconds on local hardware, infinitely more useful than GPT-5 behind an API.

**Why edge, not cloud?** Attestation data is security-sensitive. Hardware fingerprints reveal CPU models, serial numbers, MAC addresses. This data never leaves the network. SophiaCore runs on the same infrastructure it protects.

**Why three layers?** Each layer catches what the others miss. Algorithms catch obvious fakes. Sophia catches correlated anomalies. Humans catch edge cases and build institutional knowledge. The combination creates a security posture no single layer achieves alone.

# Implementation Notes

- SophiaCore model: `elyan-sophia:7b-q4_K_M` via Ollama
- Inference: 1.3-2.6s latency on RTX 4070 (Sophia NAS)
- Batch mode: inspect all active miners in ~2 minutes
- Explorer: add `sophia_verdict` column to miner display
- API: `GET /sophia/status/{miner_id}` for latest inspection

# Bounty

150 RTC for full implementation:

- 50 RTC: SophiaCore inspection endpoint + prompt engineering
- 50 RTC: Block explorer integration with emoji verdicts
- 25 RTC: Database schema + inspection history API
- 25 RTC: Failover logic + batch inspection scheduler

# Reference

- RIP-0001: Proof of Antiquity (PoA) Consensus Specification
- RIP-0007: Entropy Fingerprinting
- RIP-0201: Fleet Immune System
- SophiaCore Edge LLM: `elyan-sophia:7b-q4_K_M` (Qwen2.5-7B fine-tuned)

# Copyright

Copyright 2026 Elyan Labs / RustChain. Released under MIT License.
