# Abstract and Introduction

## Abstract

RustChain is a Proof-of-Antiquity blockchain that rewards **real physical hardware**, with explicit emphasis on preserving and operating vintage architectures (PowerPC G4/G5, SPARC, 68K, and other historically significant machines). Instead of allocating influence by raw hashpower or capital stake, RustChain uses a Proof-of-Attestation approach (RIP-200) in which miners periodically submit attestations backed by a multi-check hardware fingerprint system. The result is an incentive structure that makes “cheap scale” strategies such as virtual machine farms economically ineffective, while making authentic, scarce, and harder-to-operate vintage machines competitive.

At a protocol level, RustChain batches accounting into epochs, validates miner attestations with server-side evidence requirements, applies antiquity multipliers to eligible miners, and settles rewards in an auditable ledger. The design is pragmatic: it does not claim perfect remote attestation, but it does claim that stacking multiple independent checks and binding rules raises the cost of spoofing enough to keep the network aligned with its preservation goal.

## Introduction

### Motivation

Modern proof-of-work systems reward energy expenditure and specialized hardware fleets. Modern proof-of-stake systems reward capital concentration. Both dynamics tend to centralize participation over time. RustChain starts from a different observation: computing history is disappearing, and the skills required to keep older machines operational are increasingly rare. If the economic incentives of a blockchain can be redirected toward running and maintaining vintage machines, the chain can become a mechanism for hardware preservation rather than hardware replacement.

This motivation is not purely nostalgic. Vintage hardware is also a natural counterweight to “infinite replication” attacks: older, physical machines are harder to scale in bulk than cloud instances, and their limitations (power, stability, availability of replacement parts) serve as friction against sybil-like reward extraction.

### Design Goals

RustChain’s primary design goals are:

- **Reward authentic hardware**: real machines should out-earn virtualized replicas.
- **Make cheap scale unattractive**: VM and emulator strategies should be rejected or heavily discounted.
- **Keep user transfers simple**: signed transfers should work without gas-style fees.
- **Keep consensus auditable**: epoch settlement and ledger deltas should be easy to inspect.
- **Stay operationally practical**: run on a small number of nodes, evolve quickly, and harden as attacks appear.

### Approach Summary

RustChain implements these goals by combining:

1. **Attestation-based participation**: miners earn eligibility through periodic attestations rather than puzzle solutions.
2. **Hardware fingerprint evidence**: critical checks require raw data and server-side validation (not just client “passed=true” flags).
3. **Antiquity weighting**: vintage architectures receive multipliers to compensate for scarcity and operational cost.
4. **Hardware binding + rate limiting**: the node applies binding rules and per-IP limits to reduce multi-wallet and spam strategies.
5. **Explicit control-plane gating**: sensitive operations that mutate shared ledger state are admin-key protected.

### Scope of This Whitepaper

This whitepaper focuses on the RustChain protocol and implementation as reflected in the repository and live node behavior:

- RIP-200 (attestation and epoch settlement framing)
- Fingerprinting and anti-virtualization model
- Tokenomics framing (fixed supply reference and epoch reward distribution model)
- Network architecture and operational security

It is intended as a practical technical document rather than a purely theoretical consensus paper; where exact constants or schedules are implementation-defined, the document describes the invariant behaviors and security intent.

