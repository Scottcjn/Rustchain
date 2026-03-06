# Tokenomics

## Summary

RustChain has a fixed total supply of **8.3M RTC** (per project reference docs). The protocol distributes RTC primarily through mining rewards tied to Proof-of-Antiquity (PoA): real, vintage hardware earns higher multipliers than modern commodity hardware. Transfers are designed to be fee-free (or near-zero fee) at the protocol level, emphasizing distribution via contribution rather than transaction tolls.

This section documents the token supply framing, reward distribution mechanics, and the practical implications for miners and node operators.

## Supply

- **Total supply**: 8.3M RTC (fixed reference supply).
- **Unit convention**: internal accounting often uses integer micro-units (uRTC) with display in RTC; conversions should be explicit in APIs and code.
- **No gas-style transfer fee model**: RustChain aims for free transfers; spam protection is handled via rate limiting, admin-gated sensitive endpoints, and validation logic rather than per-tx fees.

## Distribution Model

### Mining Rewards

RustChain rewards miners in discrete time windows (epochs). At epoch settlement:

1. Eligible miners are selected based on accepted attestations in the epoch window.
2. Each miner receives a weight that reflects hardware antiquity and fingerprint validity.
3. The epoch reward pool is distributed proportionally to miner weights.

While implementation details evolve, the key design goals are consistent:

- **Incentivize diversity of real hardware**: PowerPC G4/G5, SPARC, and other vintage architectures should be competitively rewarded versus easily-scaled virtualized environments.
- **Prevent “cheap scale”**: VM farms should not be able to dominate distribution via trivial replication.

### Antiquity Multipliers

The Proof-of-Antiquity model applies architecture/family-specific multipliers to a miner’s attestation weight. Examples (illustrative) include:

- Vintage PowerPC machines earning higher multipliers than modern x86-64 hosts.
- Exotic/rare architectures receiving additional weighting where appropriate.

The multiplier is not intended to be an arbitrary bonus: it is a compensation mechanism for the higher operational cost and scarcity of real vintage hardware.

### Fingerprint Validation as an Economic Gate

Hardware fingerprint checks are an economic control surface:

- **Pass with evidence**: miners provide structured fingerprint data and raw evidence for critical checks.
- **Fail or degrade**: miners in emulated/virtualized environments are rejected or discounted, which directly reduces reward extraction.

This ties token distribution to verifiable contribution rather than purely compute quantity.

## Fees, Spam Resistance, and Admin-Gated Operations

Because RustChain does not rely on gas fees, it uses other controls:

- **Per-IP rate limiting** on high-abuse endpoints (attestations, registrations, etc.).
- **Admin-key gating** for sensitive operations that mutate shared ledger state (e.g., settlement, internal transfers, ledger exports).
- **Replay protection** and canonical signing rules for signed transfer flows.

This approach keeps user transfers cheap while making abuse costly (operationally) and observable (audit trails).

## Economic Considerations

### Miner Behavior

The distribution mechanism encourages miners to:

- Run on genuine hardware (preferably vintage).
- Maintain consistent uptime and successful attestations.
- Avoid fingerprint failures that reduce weight or disqualify eligibility.

### Centralization Pressure

RustChain’s design explicitly targets common centralization drivers:

- Gas fees do not provide an advantage to sophisticated MEV operators.
- VM-scale strategies are economically discouraged by the fingerprint gate and binding logic.

Residual centralization risks still exist (e.g., shared NAT environments, homogenous hardware fleets), and the system is expected to evolve as adversaries adapt.

## Open Questions / Future Work

- Formalize a stable public specification for reward weight calculation.
- Publish and version the multiplier schedule and its rationale.
- Improve privacy guarantees around hardware binding signals while preserving anti-sybil utility.

