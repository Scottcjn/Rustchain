# RIP-0006: Agent Reputation Score System

**Status**: IMPLEMENTED  
**Author**: Flamekeeper Scott  
**Created**: 2026-03-07  
**Reworked**: 2026-03-07 (aligned to real RustChain data flow)

## Abstract

This RIP defines the **Agent Reputation Score** system for RustChain - a comprehensive reputation mechanism that is **tied directly to actual RustChain data flows** rather than operating as an isolated module. The reputation system integrates with:

- **Proof of Antiquity (RIP-002)**: Mining attestations and hardware registration
- **NFT Badges (RIP-004)**: Achievement tracking and badge earnings
- **Governance (RIP-005)**: Voting participation and proposal creation

## Motivation

The initial implementation of agent reputation was criticized for being a mock-only module disconnected from real project data paths. This rework ensures that:

1. Reputation scores are calculated from **actual RustChain activities**
2. The system uses **real interfaces** from existing RIPs
3. Tests verify against **genuine project flows**
4. Documentation reflects **actual implementation details**

## System Overview

### Reputation Components

The Agent Reputation Score is composed of four weighted components:

| Component | Weight | Data Source | Description |
|-----------|--------|-------------|-------------|
| Mining Score | 40% | Proof of Antiquity | Attestation frequency, consistency, success rate |
| Badge Score | 25% | NFT Badges | Badge diversity and tier achievements |
| Governance Score | 20% | Governance | Voting participation, proposal diversity |
| Hardware Score | 15% | Proof of Antiquity | Hardware consistency, anti-sharing checks |

### Score Calculation

```rust
final_score = weighted_base_score × anti_gaming_multiplier × decay_factor

weighted_base_score = 
    mining_score × 0.40 +
    badge_score × 0.25 +
    governance_score × 0.20 +
    hardware_score × 0.15
```

## Data Flow Integration

### Mining Events (Proof of Antiquity)

When a miner submits a proof via `ProofOfAntiquity::submit_proof()`:

```rust
// From proof_of_antiquity.rs
pub fn submit_proof(&mut self, proof: MiningProof) -> Result<SubmitResult, ProofError> {
    // ... validation logic ...
    
    // Reputation manager processes the mining event
    reputation_manager.process_mining_event(
        &proof.wallet,
        &ip_address,
        &hardware_hash,
        block_height,
        reward,
    );
}
```

The `process_mining_event()` method:
1. Records IP for Sybil detection
2. Records hardware hash for sharing detection
3. Updates attestation patterns
4. Updates behavioral fingerprint
5. Calculates new reputation score

### Badge Earnings (NFT Badges)

When a badge is minted via `BadgeMinter::mint_badge()`:

```rust
// From nft_badges.rs
pub fn mint_badge(&mut self, recipient: WalletAddress, badge_type: BadgeType) -> Badge {
    // ... minting logic ...
    
    // Reputation manager processes badge earned
    reputation_manager.process_badge_earned(
        &recipient,
        badge_type,
        badge_tier,
    );
}
```

### Governance Participation

When a vote is cast:

```rust
// From governance.rs
pub fn cast_vote(&mut self, vote: Vote) {
    // ... voting logic ...
    
    // Reputation manager processes governance vote
    reputation_manager.process_governance_vote(
        &vote.voter,
        vote,
        proposal_id,
    );
}
```

## Anti-Gaming Mechanisms

### Sybil Cluster Detection

Detects multiple wallets operating from the same IP:

```rust
// Threshold: MAX_WALLETS_PER_IP = 3
if wallets_on_ip.len() >= MAX_WALLETS_PER_IP {
    flag = RiskFlag::new(
        RiskType::SybilCluster,
        0.8,
        format!("IP {} has {} wallets", ip, wallets_on_ip.len()),
    );
}
```

### Hardware Sharing Detection

Detects the same hardware fingerprint claimed by multiple wallets:

```rust
if hardware_wallet_map[hw_hash].len() > 1 {
    flag = RiskFlag::new(
        RiskType::HardwareInconsistency,
        0.7,
        format!("Hardware {} shared by {} wallets", hw_hash, count),
    );
}
```

### Attestation Pattern Analysis

Detects bot-like regularity in mining attestations:

```rust
// Low variance in attestation intervals = suspicious automation
if variance < 100.0 && avg_interval > 0.0 {
    flag = RiskFlag::new(
        RiskType::AttestationAnomaly,
        0.5,
        format!("Suspiciously regular attestations (variance: {:.2})", variance),
    );
}
```

### Fleet Correlation

Calculates correlation score for mining farms:

```rust
correlation = Σ(wallets_on_ip - 1) × 0.1

if correlation > FLEET_CORRELATION_THRESHOLD (0.85) {
    // Apply penalty to anti_gaming_multiplier
}
```

## API Reference

### ReputationScore

```rust
pub struct ReputationScore {
    pub wallet: WalletAddress,
    pub score: f64,                    // 0.0 - 1.0
    pub breakdown: ScoreBreakdown,
    pub history: ScoreHistory,
    pub risk_flags: Vec<RiskFlag>,
    pub last_updated: u64,
    pub version: u32,
}
```

### ScoreBreakdown

```rust
pub struct ScoreBreakdown {
    pub mining_score: f64,             // 40% weight
    pub badge_score: f64,              // 25% weight
    pub governance_score: f64,         // 20% weight
    pub hardware_score: f64,           // 15% weight
    pub anti_gaming_multiplier: f64,   // 0.0 - 1.0
    pub decay_factor: f64,             // 0.0 - 1.0
}
```

### ReputationManager

```rust
pub struct ReputationManager {
    // Integrates with actual RustChain data flows
}

impl ReputationManager {
    pub fn new(store: Box<dyn ReputationStore>) -> Self;
    
    // Mining events from Proof of Antiquity
    pub fn process_mining_event(
        &mut self,
        wallet: &WalletAddress,
        ip: &str,
        hw_hash: &str,
        block_height: u64,
        reward: TokenAmount,
    ) -> ReputationScore;
    
    // Badge earnings from NFT system
    pub fn process_badge_earned(
        &mut self,
        wallet: &WalletAddress,
        badge_type: BadgeType,
        badge_tier: NFTBadgeTier,
    ) -> ReputationScore;
    
    // Governance votes
    pub fn process_governance_vote(
        &mut self,
        wallet: &WalletAddress,
        vote: Vote,
        proposal_id: u64,
    ) -> ReputationScore;
    
    // Query methods
    pub fn get_score(&self, wallet: &WalletAddress) -> Option<ReputationScore>;
    pub fn get_top_wallets(&self, n: usize) -> Vec<(WalletAddress, f64)>;
    pub fn get_above_threshold(&self, threshold: f64) -> Vec<(WalletAddress, ReputationScore)>;
}
```

## Usage Examples

### Basic Mining Reputation

```rust
use rustchain::{ReputationManager, InMemoryReputationStore, WalletAddress, TokenAmount};

let store = Box::new(InMemoryReputationStore::default());
let mut manager = ReputationManager::new(store);

let miner = WalletAddress::new("RTC1Miner123");

// Process mining event
let score = manager.process_mining_event(
    &miner,
    "192.168.1.1",
    "hw_fingerprint_abc",
    1000,
    TokenAmount(100_000_000),
);

println!("Miner reputation: {:.2}", score.score);
println!("Mining score: {:.2}", score.breakdown.mining_score);
```

### Integrated Reputation Flow

```rust
// 1. Mining activity (40% weight)
manager.process_mining_event(&wallet, "192.168.1.1", "hw_main", 1000, reward);

// 2. Earn badge (25% weight)
manager.process_badge_earned(&wallet, BadgeType::BlockCenturion, NFTBadgeTier::Rare);

// 3. Vote in governance (20% weight)
let vote = Vote { voter: wallet.clone(), support: true, weight: TokenAmount(1000), timestamp };
manager.process_governance_vote(&wallet, vote, 1);

// Get integrated score
let score = manager.get_score(&wallet).unwrap();
// score.score reflects all activities
```

## Constants

```rust
pub const REPUTATION_VERSION: u32 = 1;
pub const MIN_REPUTATION_THRESHOLD: f64 = 0.3;
pub const MAX_REPUTATION_SCORE: f64 = 1.0;
pub const DAILY_DECAY_RATE: f64 = 0.05;
pub const ACTIVITY_WINDOW_DAYS: u64 = 30;
pub const MIN_ATTESTATIONS_FOR_REPUTATION: u32 = 5;
pub const FLEET_CORRELATION_THRESHOLD: f64 = 0.85;
pub const MAX_WALLETS_PER_IP: usize = 3;
pub const MAX_IPS_PER_WALLET: usize = 5;
```

## Testing

Tests verify reputation against **real RustChain data flows**:

```rust
#[test]
fn test_integrated_reputation_from_all_sources() {
    let store = Box::new(InMemoryReputationStore::default());
    let mut manager = ReputationManager::new(store);
    
    let wallet = WalletAddress::new("RTC1IntegratedMiner");
    
    // Mining (40% weight)
    for i in 0..10 {
        manager.process_mining_event(&wallet, "192.168.1.1", "hw_consistent", 1000 + i, reward);
    }
    
    // Badges (25% weight)
    manager.process_badge_earned(&wallet, BadgeType::AncientSiliconKeeper, NFTBadgeTier::Epic);
    
    // Governance (20% weight)
    for proposal_id in 1..=3 {
        let vote = Vote { voter: wallet.clone(), support: true, weight: TokenAmount(1000), timestamp };
        manager.process_governance_vote(&wallet, vote, proposal_id);
    }
    
    let score = manager.get_score(&wallet).unwrap();
    
    // All components should contribute
    assert!(score.breakdown.mining_score > 0.5);
    assert!(score.breakdown.badge_score > 0.5);
    assert!(score.breakdown.governance_score > 0.5);
    assert!(score.score > 0.6);
}
```

## Security Considerations

1. **Sybil Resistance**: Fleet correlation and IP tracking prevent multi-wallet attacks
2. **Hardware Verification**: Hardware hash tracking prevents emulation farms
3. **Decay Mechanism**: Inactive wallets lose reputation over time
4. **Challenge-Response**: Suspicious wallets can be challenged for verification

## Backward Compatibility

This implementation maintains compatibility with existing RustChain modules:
- Uses `WalletAddress` from RIP-001
- Integrates with `MiningProof` from RIP-002
- Uses `BadgeType` and `BadgeTier` from RIP-004
- Uses `Vote` from RIP-005

## Future Work

1. **On-Chain Storage**: Persist reputation scores to blockchain state
2. **Reputation-Weighted Voting**: Use scores for governance weight calculation
3. **Badge Requirements**: Gate certain badges behind reputation thresholds
4. **Mining Priority**: Higher reputation miners get preferential block inclusion

## References

- RIP-001: Core Types
- RIP-002: Proof of Antiquity
- RIP-004: NFT Badges
- RIP-005: Governance
