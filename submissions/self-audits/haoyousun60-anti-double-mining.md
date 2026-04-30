# Self-Audit: node/anti_double_mining.py

## Wallet
0xB7729D3927d507E4f1687B6f462F1eA3c654C8Fe

## Module reviewed
- Path: node/anti_double_mining.py
- Commit: HEAD (latest)
- Lines reviewed: whole-file (1034 lines)

## Deliverable: 3 specific findings

### 1. Entropy Score Gaming via Fallback Selection

- **Severity**: medium
- **Location**: node/anti_double_mining.py:305-318
- **Description**: The `select_representative_miner()` function selects the miner with highest entropy_score as the representative. However, entropy_score is self-reported from attestation and can be artificially inflated. When multiple miners share the same machine identity, the one with the highest (potentially fake) entropy gets all rewards, creating an incentive to game the attestation system.
- **Reproduction**: A malicious actor runs multiple miner IDs on the same machine, each with different attestation strategies. The one that produces the highest entropy_score (through timing manipulation or cache-timing tricks) will be selected as representative and receive all rewards.
- **Recommendation**: Consider adding entropy_score bounds validation (e.g., reject scores > 1.0 or < 0.0) and cross-reference with historical attestation patterns to detect sudden entropy spikes.

### 2. Warthog Bonus Multiplier Applied Without Validation

- **Severity**: medium
- **Location**: node/anti_double_mining.py:515-523
- **Description**: The Warthog dual-mining bonus is read from `miner_attest_recent.warthog_bonus` and multiplied directly into the weight without any bounds checking. The code only checks `if wart_row[0] > 1.0`, meaning any value > 1.0 (including extremely large values like 1000.0) will be accepted and multiply the miner's reward weight proportionally.
- **Reproduction**: A miner could potentially manipulate their attestation to set `warthog_bonus` to an extremely high value, gaining disproportionate rewards even with a single miner ID.
- **Recommendation**: Add an upper bound for the warthog_bonus multiplier (e.g., cap at 2.0 or 3.0) and validate against historical bonus values for the same miner.

### 3. Fallback to miner_attest_recent When epoch_enroll Is Empty

- **Severity**: low
- **Location**: node/anti_double_mining.py:183-205, 367-395
- **Description**: When `epoch_enroll` has no rows for an epoch, the code falls back to querying `miner_attest_recent` with a time-window filter. This fallback is logged as a warning but the time-window query may include miners who attested outside the epoch boundary or miss miners whose attestations expired. The comment "SECURITY FIX #2159" acknowledges this is a known vulnerability.
- **Reproduction**: If epoch settlement is delayed (e.g., network congestion), miners who attested early in the epoch may have their `ts_ok` expire, causing them to be excluded from rewards. Conversely, miners who attested just before the epoch start could be included.
- **Recommendation**: Consider using a wider time-window buffer (e.g., epoch_start - 1 hour) for the fallback query, or implement a separate enrollment confirmation mechanism that doesn't rely solely on time-windowed attestation queries.

## What I would test next

1. **Entropy score distribution analysis**: Query the database for entropy_score distribution across all miners to identify outliers or suspicious patterns.
2. **Warthog bonus historical analysis**: Check if any miners have had sudden spikes in warthog_bonus values.
3. **Epoch settlement timing**: Analyze the time gap between epoch end and settlement to quantify how often the fallback path is triggered and how many miners are affected.
4. **Machine identity collision testing**: Test with intentionally similar but distinct hardware profiles to verify the identity hash doesn't produce false collisions.

## Summary

The anti-double-mining module is well-designed with clear separation of concerns. The main risks are around attestation data integrity (entropy_score and warthog_bonus manipulation) rather than logic flaws. The fallback mechanism is a known trade-off between availability and accuracy.
