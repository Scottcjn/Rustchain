# Self-Audit: rips/src/governance.rs

## Wallet
9A8VVXnQxEL1EkygpegBztwx7kxWYhF9kWW97f4WVbiH

## Module reviewed
- Path: rips/src/governance.rs
- Commit: 92888df

## Confidence
High Confidence (Critical Protocol Flaw Found)

## Known Failures (Specific Findings)

### 1. Delegation Sybil Attack / Unbacked Voting Power
- **Severity:** Critical
- **Description:** In `get_delegated_weight`, delegated voting power is calculated purely as `(d.weight * 100.0) as u64` rather than referencing the delegating wallet's actual token balance. Since `d.weight` is a percentage (max `1.0`), every delegation yields exactly 100 flat votes.
- **Exploit:** An attacker can generate thousands of zero-balance wallets and invoke `delegate_voting_power` with `weight: 1.0` from each one to a central wallet. The central wallet accrues 100 free votes per dummy wallet, allowing them to unilaterally hijack governance and pass malicious proposals without holding any RTC tokens.

### 2. Quorum Inflation via Reputation Weights
- **Severity:** Medium
- **Description:** In `finalize_proposal`, the `participation` metric compares `total_votes()` against `total_supply` to determine if the 33% `QUORUM_PERCENTAGE` is met. However, `total_votes()` calculates the sum of reputation-inflated weights (up to a 20% bonus), while `total_supply` is raw tokens. 
- **Exploit:** Quorum can be artificially triggered by a highly reputed minority holding significantly less than 33% of the token supply (~27.5%), violating standard governance safety thresholds which assume 1 Token = 1 Vote for quorum purposes.

## What I would test next
- Write a fuzz test to verify what happens when `weeks_inactive` exceeds `i32::MAX` in the `apply_decay` function (potential cast overflow resulting in negative exponents and massive reputation boosts).
- Verify the math around `QUORUM_PERCENTAGE` to ensure floating-point precision issues cannot stall legitimate votes that fall exactly on the 33.000% threshold.