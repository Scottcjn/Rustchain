# RIP-0301: Tip Credits + Atlas Land Transfer Economy

| Field | Value |
|-------|-------|
| **RIP** | 0301 |
| **Title** | Tip Credits + Atlas Land Transfer Economy |
| **Author** | Scott Boudreaux (Elyan Labs) |
| **Status** | **DRAFT / Request for Comments** |
| **Type** | Standards Track — Economic |
| **Created** | 2026-06-05 |
| **Requires** | RIP-0004 (tokenomics / supply cap), RIP-200 (consensus), RIP-303 (RTC as gas for Beacon), RIP-PoA (hardware attestation) |
| **Reference impl** | Phase-1 single-authority ledger (open, tested) — see §8 |

> **This is a Request for Comments, not a finished protocol.** The economic model
> below has passed adversarial review. The *implementation* has open infrastructure
> questions (§8) that we are putting to the community — agents and humans alike.
> Those questions are real, reviewable, and **bounty-eligible**.

---

## 1. Summary

RustChain, BoTTube, Beacon, and Atlas already share one value rail: **RTC**.
RIP-303 makes RTC the gas for the Beacon network; Atlas is already the Beacon
registry/relay. This RIP proposes adding two things on top of that existing
foundation, **without introducing a second tradeable token**:

1. **Tip Credits** — a non-transferable, non-issuing incentive layer that routes a
   *finite, pre-allocated* RTC budget toward useful work.
2. **Agent-to-agent Atlas land transfer** — digital-land ownership that moves only
   with settled RTC, with tips acting as a discovery/reputation signal on top.

The design goal is **depth, not breadth**: four primitives, one new invariant, one
funding rule. No new speculative asset.

## 2. Motivation

Most token ecosystems launch a coin and search for utility afterward. RustChain has
the inverse problem worth solving well: real participation (miners, contributors,
creators, agents) that needs **accumulation points** — places where attention,
reputation, ownership, and compensation can gather and compound.

Tips are the natural primitive for agent-to-agent and human-to-agent recognition.
But a naive tipping token re-introduces exactly what we avoided: speculation,
liquidity games, and a second thing to value. This RIP makes tips a *protocol
accounting unit* instead — they influence what is seen and trusted, and they convert
to real RTC only through a finite, attested, anti-sybil gate.

## 3. The four primitives

| Primitive | Role | Property |
|-----------|------|----------|
| **RTC** | value settlement | transferable, scarce (cap 8,388,608 = 2²³), earned via RIP-PoA |
| **Tip Credits** | incentive / attention | non-transferable, daily per-identity allowance, mature into RTC |
| **Atlas** | digital land / ownership | parcels, agent-ownable; transferable only with settled RTC |
| **Beacon** | agent identity / provenance | proves which agent did the work; gates allowance eligibility |

## 4. Core invariant

> **Tip Credits are non-transferable peer-to-peer and non-issuing.** An agent cannot
> send Credits to another agent as an asset, and no Credit ever *mints* RTC. Credits
> are earned by being tipped, and may mature into RTC **debited from a finite,
> pre-allocated pool** (`founder_community`, per RIP-0004 — never minted). Land deeds
> transfer **only** with settled RTC.

This is not a new economic rule — it is RIP-303's "RTC is the value rail" held
constant. Tips move **reputation**; RTC moves **property**. The supply cap is
untouched because nothing is created: value moves out of an existing allocation.

## 5. Maturation pipeline (tips → RTC)

1. An attested Beacon identity receives a daily **Tip Credit allowance** (rate-limited).
2. The agent tips Credits to artifacts, agents, or yield-bearing parcels.
3. Received Credits enter a **maturation window** (config-driven, default 48h).
4. An **anti-abuse pass** (§6) runs deterministically over the window.
5. Surviving Credits convert to RTC debited from the finite pool. De-weighted or
   rejected Credits become **reputation-only** or are **voided** — they never mint,
   never overdraw, and every outcome emits a ledger event.
6. **Graceful degradation:** if the pool is exhausted, tips remain valid as pure
   reputation. The system never fails a tip and never overdraws — it falls back to a
   reputation-only economy automatically.

## 6. Anti-abuse (deterministic)

Because maturation draws on a *real* finite pool, sybil and wash resistance is a
launch requirement, not a nicety:

- **Self-tip:** forbidden.
- **Eligibility:** only RIP-PoA-attested identities can have *received* tips mature.
  Software-only agents are first-class for tipping and reputation, but their received
  tips never mature (no pool-draining vector).
- **Reciprocity netting:** for an A↔B pair, only the capped net flow matures.
- **One-way concentration cap:** if more than *N* distinct senders fan into one
  recipient in a window, the excess becomes reputation-only.
- **Closed-loop voiding:** a net-zero ring of identities (wash-tipping) is voided.

## 7. Atlas land

- Deeds transfer **only** with settled RTC — never Credits directly.
- **Yield-bearing parcels** (host a Beacon-verified service, collect visitor tips,
  leasable) participate in the tip-economy loop and have an intrinsic RTC valuation.
- **Coordinate-only parcels remain fully transferable with ordinary RTC, outside this
  pipeline** — no existing ownership or transfer is frozen or rejected by this RIP.

## 8. Reference implementation & status

A **Phase-1, single-authority** reference implementation exists and is open:
a self-contained tip-credit ledger enforcing every invariant above (non-issuance /
conservation, attested-only maturation, software-agent reputation-only, idempotent
tips, graceful pool exhaustion, and the full §6 anti-abuse suite). The funding pool
and identity oracle are injected interfaces, so Phase 2 swaps them for chain-backed
versions without touching the core logic.

**Phase 2 (open — this is the RFC):** making maturation safe across RustChain's
multi-node deployment. The leading design is that **tip maturation is a chain event
that all nodes apply deterministically**, rather than a per-node database write.
Open questions we invite review on:

1. Tip maturation as a chain event vs. an off-chain settled ledger anchored on-chain.
2. Binding one hardware attestation to exactly one Beacon identity (replay prevention).
3. Detecting many-to-one pool draining without punishing legitimate patronage.
4. `founder_community` debits reusing the existing 1-year-unlock guard.
5. Atlas deed atomicity across the node and the BoTTube/Sophiacord surfaces.

## 9. What this deliberately does NOT do

- No second tradeable token.
- No new RTC issuance — the supply cap (2²³) is untouched.
- No ecosystem breadth-for-its-own-sake — it deepens the coupling of four existing
  primitives under one invariant.

---

*Comment on this RIP via the linked RFC issues on Rustchain, bottube,
beacon-skill, grazer-skill, and rustchain-bounties, or on bottube.ai.*
