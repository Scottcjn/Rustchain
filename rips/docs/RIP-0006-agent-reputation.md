# RIP-006: On-Chain Agent Reputation Score System

**RIP**: 006  
**Title**: On-Chain Agent Reputation Score System  
**Author**: Flamekeeper Scott  
**Status**: Implementation  
**Created**: 2026-03-07  
**License**: MIT  

## Abstract

This RIP defines a comprehensive reputation scoring system for RustChain agents and validators. The system provides quantifiable trust metrics based on attestation history, hardware authenticity, community interaction, and behavioral analysis. It includes robust anti-gaming safeguards to prevent Sybil attacks, fleet manipulation, and score inflation.

## Motivation

As RustChain grows to support AI agents, automated validators, and machine-to-machine economies, a trust mechanism is essential for:

1. **Agent Selection**: Enable users and protocols to select high-reputation agents for tasks
2. **Sybil Resistance**: Detect and penalize coordinated manipulation attempts
3. **Network Health**: Incentivize consistent, honest participation
4. **Economic Weight**: Allow reputation to influence governance and reward distribution
5. **Cross-Chain Portability**: Provide reputation proofs for other chains

## Specification

### 1. Reputation Score Components

The overall reputation score (0.0 - 1.0) is calculated from five weighted components:

```
REPUTATION_SCORE = (
    uptime_score      × 0.30 +
    attestation_score × 0.25 +
    hardware_score    × 0.20 +
    community_score   × 0.15 +
    history_score     × 0.10
) × anti_gaming_multiplier × decay_factor
```

#### 1.1 Uptime Score (30% weight)

Measures reliability and consistency of agent participation.

**Calculation**:
```
uptime_score = (recency_score + frequency_score) / 2

recency_score = max(0, 1.0 - days_since_last_attestation / 7)
frequency_score = min(1.0, actual_attestations / expected_attestations)
expected_attestations = 30_days × 2_per_day = 60
```

**Factors**:
- Recent activity (last 7 days weighted heavily)
- Expected frequency (~2 attestations/day)
- Consistency over 30-day window

#### 1.2 Attestation Score (25% weight)

Measures quality and consistency of hardware attestations.

**Calculation**:
```
attestation_score = (success_rate + consistency_score) / 2

success_rate = successful_attestations / total_attestations
consistency_score = f(timing_variance)
  - variance < 1000:   0.8 (some human-like variance is good)
  - variance < 10000:  0.9 (healthy consistency)
  - variance >= 10000: 0.7 (erratic behavior)
```

**Minimum attestations**: 5 required for full scoring

#### 1.3 Hardware Score (20% weight)

Measures hardware authenticity and consistency.

**Calculation**:
```
hardware_score = 
  - 1 unique hardware fingerprint:  1.0
  - 2-3 unique fingerprints:        0.7
  - 4+ unique fingerprints:         0.4
```

**Rationale**: Consistent hardware indicates genuine single-node operation

#### 1.4 Community Score (15% weight)

Measures positive community contributions.

**Activities tracked**:
- Governance participation
- Helping new miners
- Bug reports and fixes
- Documentation contributions
- Peer endorsements

**Calculation**:
```
community_score = min(1.0, average_quality_score_of_interactions)
```

#### 1.5 History Score (10% weight)

Measures long-term positive behavior.

**Calculation**:
```
history_score = (length_score + positive_rate) / 2

length_score = min(1.0, activity_records / BEHAVIOR_WINDOW_SIZE)
positive_rate = sum(outcomes) / total_activities
```

### 2. Anti-Gaming Safeguards

#### 2.1 Sybil Cluster Detection

**Detection**:
- Track IP → wallet mappings
- Flag wallets exceeding `MAX_WALLETS_PER_IP` (default: 3)
- Flag wallets using `MAX_IPS_PER_WALLET` (default: 5)

**Penalty**:
```
sybil_penalty = (wallet_count - threshold) × 0.2
```

#### 2.2 Hardware Sharing Detection

**Detection**:
- Track hardware fingerprint → wallet mappings
- Flag multiple wallets sharing identical hardware

**Penalty**:
```
hardware_penalty = wallet_count × 0.3
```

#### 2.3 Attestation Pattern Analysis

**Detection**:
- Analyze timing variance between attestations
- Flag bot-like regularity (variance < 100ms)

**Penalty**:
```
pattern_penalty = 0.5 (fixed)
```

#### 2.4 Fleet Correlation Score

**Calculation**:
```
fleet_correlation = Σ(wallets_on_same_ip - 1) × 0.1
```

**Threshold**: 0.85

**Penalty**:
```
fleet_penalty = (correlation - threshold) × 2.0
```

#### 2.5 Challenge-Response System

**Mechanism**:
- Random challenges issued to suspicious wallets
- Response time tracked (too fast = automated)
- Success rate affects multiplier

**Penalties**:
- Failed challenge: 0.7 severity flag
- Response < 1s: 0.4 severity flag (suspicious automation)
- Success rate < 80%: multiplier reduction

#### 2.6 Behavioral Fingerprinting

**Tracked metrics**:
- Average attestation interval
- Timing variance
- Active hours distribution
- Common geographic regions
- Hardware consistency score

**Usage**: Anomaly detection for flagging suspicious behavior changes

### 3. Time Decay

**Purpose**: Prevent reputation hoarding and ensure active participation

**Mechanism**:
```
decay_factor = exp(-inactive_days × DAILY_DECAY_RATE / REPUTATION_HALF_LIFE_DAYS)

where:
  DAILY_DECAY_RATE = 0.05 (5% per day)
  REPUTATION_HALF_LIFE_DAYS = 14
```

**Example decay**:
- 0 days inactive:  1.0 (no decay)
- 7 days inactive:   0.78
- 14 days inactive:  0.61
- 30 days inactive:  0.30

### 4. Risk Flags

#### 4.1 Flag Types

| Flag Type | Severity Range | Description |
|-----------|----------------|-------------|
| `SybilCluster` | 0.2 - 1.0 | Multiple wallets on single IP |
| `AttestationAnomaly` | 0.3 - 0.7 | Irregular attestation patterns |
| `HardwareInconsistency` | 0.3 - 0.9 | Hardware fingerprint mismatch |
| `ScoreManipulation` | 0.4 - 0.8 | Attempted gaming of scoring |
| `FleetBehavior` | 0.5 - 1.0 | Coordinated fleet detected |
| `ChallengeFailure` | 0.7 | Failed challenge response |
| `IPReputation` | 0.15 - 0.6 | Excessive IP usage |
| `TemporalAnomaly` | 0.5 - 0.9 | Impossible travel time |

#### 4.2 Flag Resolution

Flags can be resolved by:
- Time-based expiration (30 days for minor flags)
- Successful challenge responses
- Manual review and clearance
- Corrective behavior (consistent honest operation)

### 5. Storage Integration

#### 5.1 Store Trait

```rust
pub trait ReputationStore {
    fn get_score(&self, wallet: &WalletAddress) -> Option<ReputationScore>;
    fn update_score(&mut self, score: ReputationScore);
    fn get_top_wallets(&self, n: usize) -> Vec<(WalletAddress, f64)>;
    fn get_above_threshold(&self, threshold: f64) -> Vec<(WalletAddress, ReputationScore)>;
    fn get_history(&self, wallet: &WalletAddress) -> Option<ScoreHistory>;
}
```

#### 5.2 SQLite Schema (Reference Implementation)

```sql
CREATE TABLE reputation_scores (
    wallet_address TEXT PRIMARY KEY,
    score REAL NOT NULL,
    uptime_score REAL NOT NULL,
    attestation_score REAL NOT NULL,
    hardware_score REAL NOT NULL,
    community_score REAL NOT NULL,
    history_score REAL NOT NULL,
    anti_gaming_multiplier REAL NOT NULL,
    decay_factor REAL NOT NULL,
    peak_score REAL NOT NULL,
    avg_30d REAL NOT NULL,
    trend_7d REAL NOT NULL,
    last_updated INTEGER NOT NULL,
    version INTEGER NOT NULL
);

CREATE TABLE risk_flags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_address TEXT NOT NULL,
    flag_type TEXT NOT NULL,
    severity REAL NOT NULL,
    description TEXT NOT NULL,
    flagged_at INTEGER NOT NULL,
    resolved BOOLEAN NOT NULL DEFAULT 0,
    FOREIGN KEY (wallet_address) REFERENCES reputation_scores(wallet_address)
);

CREATE TABLE activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_address TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    activity_type TEXT NOT NULL,
    outcome REAL NOT NULL,
    metadata TEXT,
    FOREIGN KEY (wallet_address) REFERENCES reputation_scores(wallet_address)
);

CREATE INDEX idx_activity_wallet ON activity_log(wallet_address);
CREATE INDEX idx_activity_timestamp ON activity_log(timestamp);
CREATE INDEX idx_risk_wallet ON risk_flags(wallet_address);
```

### 6. API Endpoints

#### 6.1 Get Reputation Score

```
GET /api/reputation/{wallet}
```

**Response**:
```json
{
  "wallet": "RTC1AgentName123",
  "score": 0.847,
  "breakdown": {
    "uptime_score": 0.92,
    "attestation_score": 0.88,
    "hardware_score": 1.0,
    "community_score": 0.75,
    "history_score": 0.80,
    "anti_gaming_multiplier": 1.0,
    "decay_factor": 0.95
  },
  "history": {
    "peak_score": 0.89,
    "avg_30d": 0.82,
    "trend_7d": 0.03,
    "days_tracked": 45
  },
  "risk_flags": [],
  "last_updated": 1741392000,
  "version": 1
}
```

#### 6.2 Get Top Agents

```
GET /api/reputation/top?limit=100
```

**Response**:
```json
[
  {
    "wallet": "RTC1TopAgent1",
    "score": 0.952,
    "rank": 1
  },
  ...
]
```

#### 6.3 Get Agents Above Threshold

```
GET /api/reputation/qualified?threshold=0.7
```

**Use case**: Find agents qualified for high-reputation tasks

#### 6.4 Submit Attestation (Updates Reputation)

```
POST /api/reputation/attestation
Content-Type: application/json

{
  "wallet": "RTC1Agent123",
  "ip_hash": "abc123...",
  "hardware_hash": "def456...",
  "success": true
}
```

#### 6.5 Record Community Interaction

```
POST /api/reputation/interaction
Content-Type: application/json

{
  "wallet": "RTC1Agent123",
  "interaction_type": "governance_vote",
  "quality_score": 1.0
}
```

#### 6.6 Issue Challenge

```
POST /api/reputation/challenge
Content-Type: application/json

{
  "wallet": "RTC1SuspectWallet"
}
```

### 7. Integration Points

#### 7.1 Proof of Antiquity Integration

```rust
// In proof_of_antiquity.rs
use crate::agent_reputation::ReputationManager;

pub struct ProofOfAntiquity {
    // ... existing fields
    reputation_manager: ReputationManager,
}

impl ProofOfAntiquity {
    pub fn submit_proof(&mut self, proof: MiningProof) -> Result<SubmitResult, ProofError> {
        // ... existing validation
        
        // Update reputation for successful attestation
        let rep_score = self.reputation_manager.process_attestation(
            &proof.wallet,
            &proof.ip,
            &proof.hardware_hash,
            true,
        );
        
        // Apply reputation bonus to multiplier
        let reputation_bonus = 1.0 + (rep_score.score * 0.1); // Up to 10% bonus
        let final_multiplier = proof.hardware.multiplier * reputation_bonus;
        
        Ok(SubmitResult {
            // ...
            reputation_score: rep_score.score,
        })
    }
}
```

#### 7.2 Badge System Integration

```rust
// In nft_badges.rs
use crate::agent_reputation::{ReputationScore, MIN_REPUTATION_THRESHOLD};

impl BadgeCriteriaChecker {
    pub fn check_reputation_badges(&self, stats: &MinerStats, rep_score: &ReputationScore) -> Vec<BadgeType> {
        let mut badges = Vec::new();
        
        if rep_score.score >= 0.9 {
            badges.push(BadgeType::TrustedAgent);
        }
        
        if rep_score.score >= MIN_REPUTATION_THRESHOLD && rep_score.history.days_tracked >= 90 {
            badges.push(BadgeType::ConsistentContributor);
        }
        
        if rep_score.breakdown.community_score >= 0.8 {
            badges.push(BadgeType::CommunityChampion);
        }
        
        badges
    }
}
```

#### 7.3 Governance Weight

```rust
// In governance.rs
use crate::agent_reputation::ReputationManager;

pub struct GovernanceProposal {
    // ... existing fields
    reputation_weight: f64,
}

impl GovernanceProposal {
    pub fn calculate_vote_weight(&self, voter_wallet: &WalletAddress, rep_manager: &ReputationManager) -> f64 {
        let base_weight = self.get_token_weight(voter_wallet);
        
        if let Some(rep_score) = rep_manager.get_score(voter_wallet) {
            // Reputation can amplify vote weight up to 2x
            let reputation_multiplier = 1.0 + rep_score.score;
            base_weight * reputation_multiplier
        } else {
            base_weight
        }
    }
}
```

### 8. Economic Incentives

#### 8.1 Reputation Bonuses

| Reputation Score | Reward Bonus | Governance Weight |
|------------------|--------------|-------------------|
| 0.9 - 1.0 | +10% | 2.0x |
| 0.8 - 0.9 | +7% | 1.8x |
| 0.7 - 0.8 | +5% | 1.5x |
| 0.6 - 0.7 | +3% | 1.3x |
| 0.5 - 0.6 | +0% | 1.0x |
| < 0.5 | -10% penalty | 0.5x |

#### 8.2 Threshold Requirements

| Operation | Minimum Reputation |
|-----------|-------------------|
| Standard mining | 0.0 (no minimum) |
| Epoch validator | 0.5 |
| Governance proposal | 0.6 |
| Bounty claim > 50 RTC | 0.7 |
| Multi-sig co-signer | 0.8 |
| Network upgrade vote | 0.9 |

### 9. Privacy Considerations

#### 9.1 IP Address Handling

- IP addresses are hashed before storage: `SHA256(ip)[0:16]`
- Raw IPs never stored on-chain
- Hash prevents reverse engineering but allows correlation detection

#### 9.2 Geographic Data

- Only coarse region stored (e.g., "US-West", "EU-Central")
- No precise location tracking
- Region used for temporal anomaly detection only

#### 9.3 Data Retention

- Activity logs: 90 days rolling window
- Risk flags: 30 days after resolution
- Score history: Indefinite (aggregated stats only)

### 10. Security Considerations

#### 10.1 Attack Vectors

| Attack | Mitigation |
|--------|------------|
| Sybil attack (many wallets) | IP/hardware correlation detection |
| Fleet coordination | Fleet correlation scoring |
| Bot automation | Challenge-response system |
| Score manipulation | Behavioral fingerprinting |
| Replay attacks | Timestamp validation, nonce tracking |
| False flagging | Multi-sig flag resolution |

#### 10.2 Rate Limiting

- Attestation updates: 10/minute per wallet
- Challenge issuance: 1/hour per wallet
- Score queries: 100/minute per IP

### 11. Upgrade Path

#### Version 1 (Current)
- Basic scoring model
- In-memory store
- Core anti-gaming detection

#### Future Versions
- **v2**: SQLite persistence, cross-chain reputation proofs
- **v3**: Machine learning anomaly detection, peer endorsement system
- **v4**: Decentralized reputation oracle, stake-weighted reputation

## Reference Implementation

The reference implementation is provided in `rips/src/agent_reputation.rs`:

- `ReputationScore`: Main score struct with breakdown
- `ReputationManager`: Core scoring logic
- `AntiGamingDetector`: Sybil/fleet detection
- `InMemoryReputationStore`: Default store implementation
- Comprehensive test suite

## Backwards Compatibility

This RIP introduces new types and APIs without modifying existing functionality. Existing miners and validators continue operating normally; reputation scoring is an additive layer.

## Test Plan

### Unit Tests
- Score calculation accuracy
- Weight distribution verification
- Decay function correctness
- Anti-gaming threshold detection

### Integration Tests
- Attestation → reputation update flow
- Challenge-response workflow
- Multi-wallet Sybil detection
- Fleet correlation detection

### Stress Tests
- 10,000 wallets with concurrent updates
- Memory usage under load
- SQLite write performance

### Edge Cases
- Zero attestations
- Perfect score (1.0)
- Minimum score (0.0)
- Rapid attestation patterns
- Long inactivity periods

## Deployment

### Phase 1: Testnet (Week 1-2)
- Deploy to testnet
- Monitor false positive rate
- Tune thresholds based on data

### Phase 2: Mainnet Soft Launch (Week 3-4)
- Enable scoring (no penalties)
- Collect baseline metrics
- Community feedback

### Phase 3: Full Enforcement (Week 5+)
- Enable anti-gaming penalties
- Apply reputation bonuses
- Integrate with governance

## References

- RIP-001: Core Types
- RIP-002: Proof of Antiquity
- RIP-004: NFT Badges
- RIP-201: Fleet Immune System
- Beacon Atlas agent reputation concepts

## Copyright

Copyright (c) 2026 RustChain Contributors  
Licensed under MIT License
