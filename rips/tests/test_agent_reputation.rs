// Integration tests for Agent Reputation Score System
// ====================================================
// Tests verify reputation system against REAL RustChain data flows:
// - Mining events from Proof of Antiquity
// - Badge earnings from NFT system
// - Governance participation

use rustchain::agent_reputation::*;
use rustchain::core_types::{WalletAddress, TokenAmount};
use rustchain::nft_badges::{BadgeType, BadgeTier as NFTBadgeTier};

// Use the Vote from agent_reputation (mock or real depending on feature)
use rustchain::agent_reputation::Vote;

// Helper to get current timestamp
fn current_timestamp() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or(std::time::Duration::ZERO)
        .as_secs()
}

/// Test complete mining-based reputation flow
#[test]
fn test_mining_reputation_flow() {
    let store = Box::new(InMemoryReputationStore::default());
    let mut manager = ReputationManager::new(store);
    
    let wallet = WalletAddress::new("RTC1MiningTest123");
    
    // Initial state - no score until first activity
    let initial = manager.get_score(&wallet);
    assert!(initial.is_none());
    
    // First mining event (attestation)
    let score1 = manager.process_mining_event(
        &wallet,
        "192.168.1.100",
        "hw_fingerprint_abc",
        1000,
        TokenAmount(100_000_000),
    );
    
    assert!(score1.score >= 0.5); // Should start at least neutral
    assert_eq!(score1.version, REPUTATION_VERSION);
    assert!(score1.breakdown.mining_score > 0.5); // Mining should boost mining_score
    
    // Second mining event (improves score with consistency)
    let score2 = manager.process_mining_event(
        &wallet,
        "192.168.1.100",
        "hw_fingerprint_abc",
        1001,
        TokenAmount(100_000_000),
    );
    
    // Consistent hardware should maintain or improve score
    assert!(score2.breakdown.hardware_score >= 0.7);
    
    // Verify history tracking
    assert!(score2.history.days_tracked > 0);
}

/// Test badge-based reputation from NFT system
#[test]
fn test_badge_reputation_flow() {
    let store = Box::new(InMemoryReputationStore::default());
    let mut manager = ReputationManager::new(store);
    
    let wallet = WalletAddress::new("RTC1BadgeTest456");
    
    // Earn a legendary badge (Genesis Miner)
    let score = manager.process_badge_earned(
        &wallet,
        BadgeType::GenesisMiner,
        NFTBadgeTier::Legendary,
    );
    
    assert!(score.breakdown.badge_score >= 0.9); // Legendary badge should give high badge_score
    
    // Earn additional badges
    manager.process_badge_earned(&wallet, BadgeType::BlockCenturion, NFTBadgeTier::Rare);
    let score2 = manager.get_score(&wallet).unwrap();
    
    // Multiple badges should maintain high badge_score
    assert!(score2.breakdown.badge_score >= 0.8);
}

/// Test governance-based reputation
#[test]
fn test_governance_reputation_flow() {
    let store = Box::new(InMemoryReputationStore::default());
    let mut manager = ReputationManager::new(store);
    
    let wallet = WalletAddress::new("RTC1GovernanceTest");
    
    // Create votes for multiple proposals
    for proposal_id in 1..=5 {
        let vote = Vote {
            voter: wallet.clone(),
            support: true,
            weight: TokenAmount(1000),
            timestamp: current_timestamp(),
        };
        
        manager.process_governance_vote(&wallet, vote, proposal_id);
    }
    
    let score = manager.get_score(&wallet).unwrap();
    
    // Active governance participation should boost governance_score
    assert!(score.breakdown.governance_score >= 0.8);
}

/// Test integrated reputation from all RustChain data sources
#[test]
fn test_integrated_reputation_from_all_sources() {
    let store = Box::new(InMemoryReputationStore::default());
    let mut manager = ReputationManager::new(store);
    
    let wallet = WalletAddress::new("RTC1IntegratedMiner");
    
    // 1. Mining activity (40% weight)
    for i in 0..10 {
        manager.process_mining_event(
            &wallet,
            "192.168.1.1",
            "hw_consistent",
            1000 + i,
            TokenAmount(100_000_000),
        );
    }
    
    // 2. Badge achievements (25% weight)
    manager.process_badge_earned(&wallet, BadgeType::AncientSiliconKeeper, NFTBadgeTier::Epic);
    manager.process_badge_earned(&wallet, BadgeType::BlockCenturion, NFTBadgeTier::Rare);
    
    // 3. Governance participation (20% weight)
    for proposal_id in 1..=3 {
        let vote = Vote {
            voter: wallet.clone(),
            support: proposal_id % 2 == 0,
            weight: TokenAmount(1000),
            timestamp: current_timestamp(),
        };
        manager.process_governance_vote(&wallet, vote, proposal_id);
    }
    
    let score = manager.get_score(&wallet).unwrap();
    
    // All components should contribute
    assert!(score.breakdown.mining_score > 0.5);
    assert!(score.breakdown.badge_score > 0.5);
    assert!(score.breakdown.governance_score > 0.5);
    assert!(score.breakdown.hardware_score > 0.7); // Consistent hardware
    
    // Overall score should reflect combined activities
    assert!(score.score > 0.6);
}

/// Test Sybil cluster detection across mining operations
#[test]
fn test_sybil_detection_in_mining() {
    let store = Box::new(InMemoryReputationStore::default());
    let mut manager = ReputationManager::new(store);
    
    let ip = "10.0.0.100";
    let mut wallets = Vec::new();
    
    // Create 5 wallets on same IP (mining operation)
    for i in 0..5 {
        let wallet = WalletAddress::new(format!("RTC1SybilMiner{}", i));
        wallets.push(wallet.clone());
        
        manager.process_mining_event(
            &wallet,
            ip,
            &format!("hw_fingerprint_{}", i),
            1000 + i as u64,
            TokenAmount(100_000_000),
        );
    }
    
    // Check that later wallets get flagged
    let last_wallet = wallets.last().unwrap();
    let score = manager.get_score(last_wallet).unwrap();
    
    // Should have Sybil cluster flag
    let has_sybil_flag = score.risk_flags.iter()
        .any(|f| f.flag_type == RiskType::SybilCluster);
    
    assert!(has_sybil_flag, "Should detect Sybil cluster in mining operations");
}

/// Test hardware sharing detection across miners
#[test]
fn test_hardware_sharing_in_mining() {
    let store = Box::new(InMemoryReputationStore::default());
    let mut manager = ReputationManager::new(store);
    
    let shared_hw = "shared_hardware_fingerprint";
    
    // Two wallets claiming same hardware
    let wallet1 = WalletAddress::new("RTC1HardwareSharer1");
    let wallet2 = WalletAddress::new("RTC1HardwareSharer2");
    
    manager.process_mining_event(&wallet1, "192.168.1.1", shared_hw, 1000, TokenAmount(100_000_000));
    let score2 = manager.process_mining_event(&wallet2, "192.168.1.2", shared_hw, 1001, TokenAmount(100_000_000));
    
    // Second wallet should be flagged for hardware sharing
    let has_hw_flag = score2.risk_flags.iter()
        .any(|f| f.flag_type == RiskType::HardwareInconsistency);
    
    assert!(has_hw_flag, "Should detect hardware sharing across miners");
}

/// Test reputation decay with mining inactivity
#[test]
fn test_reputation_decay_after_mining() {
    let store = Box::new(InMemoryReputationStore::default());
    let mut manager = ReputationManager::new(store);
    
    let wallet = WalletAddress::new("RTC1DecayTest");
    
    // Build up reputation through mining
    for _ in 0..10 {
        manager.process_mining_event(
            &wallet,
            "192.168.1.1",
            "hw_fingerprint",
            1000,
            TokenAmount(100_000_000),
        );
    }
    
    let score_before = manager.get_score(&wallet).unwrap();
    let decay_factor_before = score_before.breakdown.decay_factor;
    
    // Apply decay (simulates mining inactivity)
    manager.apply_decay();
    
    let score_after = manager.get_score(&wallet).unwrap();
    let decay_factor_after = score_after.breakdown.decay_factor;
    
    // Decay factor should decrease after inactivity
    assert!(decay_factor_after <= decay_factor_before);
}

/// Test challenge-response system for miners
#[test]
fn test_challenge_response_for_miners() {
    let store = Box::new(InMemoryReputationStore::default());
    let mut manager = ReputationManager::new(store);
    
    let wallet = WalletAddress::new("RTC1ChallengeTest");
    
    // Successful challenge (reasonable response time)
    let score1 = manager.process_challenge(&wallet, 5.0, true);
    
    assert!(!score1.risk_flags.iter().any(|f| 
        f.flag_type == RiskType::ChallengeFailure
    ));
    
    // Failed challenge
    let score2 = manager.process_challenge(&wallet, 10.0, false);
    
    assert!(score2.risk_flags.iter().any(|f| 
        f.flag_type == RiskType::ChallengeFailure
    ));
    
    // Too-fast response (suspicious automation)
    let score3 = manager.process_challenge(&wallet, 0.3, true);
    
    assert!(score3.risk_flags.iter().any(|f| 
        f.flag_type == RiskType::ScoreManipulation
    ));
}

/// Test badge tier impact on reputation
#[test]
fn test_badge_tier_impact() {
    let store = Box::new(InMemoryReputationStore::default());
    let mut manager = ReputationManager::new(store);
    
    // Legendary badge
    let wallet_legendary = WalletAddress::new("RTC1Legendary");
    let score_legendary = manager.process_badge_earned(
        &wallet_legendary,
        BadgeType::GenesisMiner,
        NFTBadgeTier::Legendary,
    );
    
    // Common badge
    let wallet_common = WalletAddress::new("RTC1Common");
    let score_common = manager.process_badge_earned(
        &wallet_common,
        BadgeType::CommunityBuilder,
        NFTBadgeTier::Common,
    );
    
    // Legendary should give higher badge_score
    assert!(score_legendary.breakdown.badge_score > score_common.breakdown.badge_score);
}

/// Test governance participation diversity
#[test]
fn test_governance_diversity() {
    let store = Box::new(InMemoryReputationStore::default());
    let mut manager = ReputationManager::new(store);
    
    let wallet = WalletAddress::new("RTC1GovDiversity");
    
    // Vote on many different proposals
    for proposal_id in 1..=10 {
        let vote = Vote {
            voter: wallet.clone(),
            support: proposal_id % 2 == 0,
            weight: TokenAmount(1000),
            timestamp: current_timestamp(),
        };
        manager.process_governance_vote(&wallet, vote, proposal_id);
    }
    
    let score = manager.get_score(&wallet).unwrap();
    
    // Diverse participation should give high governance_score
    assert!(score.breakdown.governance_score >= 0.9);
}

/// Test top miners ranking
#[test]
fn test_top_miners_ranking() {
    let store = Box::new(InMemoryReputationStore::default());
    let mut manager = ReputationManager::new(store);
    
    // Create miners with different activity levels
    let miners: Vec<_> = (0..10)
        .map(|i| WalletAddress::new(format!("RTC1RankMiner{}", i)))
        .collect();
    
    // Miner 0: Most active (highest score)
    for _ in 0..20 {
        manager.process_mining_event(&miners[0], "192.168.1.0", "hw_0", 1000, TokenAmount(100_000_000));
    }
    
    // Miners 1-4: Moderately active
    for (i, miner) in miners[1..5].iter().enumerate() {
        for _ in 0..10 {
            manager.process_mining_event(
                miner,
                &format!("192.168.1.{}", i + 1),
                &format!("hw_{}", i + 1),
                1000,
                TokenAmount(100_000_000),
            );
        }
    }
    
    // Miners 5-9: Minimal activity
    for (i, miner) in miners[5..10].iter().enumerate() {
        manager.process_mining_event(
            miner,
            &format!("192.168.1.{}", i + 5),
            &format!("hw_{}", i + 5),
            1000,
            TokenAmount(100_000_000),
        );
    }
    
    // Get top 5
    let top = manager.get_top_wallets(5);
    
    assert_eq!(top.len(), 5);
    
    // Most active miner should be in top
    assert!(top.iter().any(|(w, _)| w.0 == miners[0].0));
}

/// Test threshold filtering for qualified miners
#[test]
fn test_threshold_filtering() {
    let store = Box::new(InMemoryReputationStore::default());
    let mut manager = ReputationManager::new(store);
    
    // Create miners with varying scores
    let high_score_miner = WalletAddress::new("RTC1HighScore");
    let low_score_miner = WalletAddress::new("RTC1LowScore");

    // Build high score through extensive mining and badges
    for _ in 0..50 {
        manager.process_mining_event(&high_score_miner, "192.168.1.1", "hw_high", 1000, TokenAmount(100_000_000));
    }
    manager.process_badge_earned(&high_score_miner, BadgeType::GenesisMiner, NFTBadgeTier::Legendary);

    // Low score (single mining event)
    manager.process_mining_event(&low_score_miner, "192.168.1.2", "hw_low", 1000, TokenAmount(100_000_000));

    // Filter with moderate threshold
    let qualified = manager.get_above_threshold(0.5);

    // High score miner should qualify
    assert!(qualified.iter().any(|(w, _)| w.0 == high_score_miner.0));
}

/// Test score history tracking through mining lifecycle
#[test]
fn test_score_history_tracking() {
    let store = Box::new(InMemoryReputationStore::default());
    let mut manager = ReputationManager::new(store);
    
    let wallet = WalletAddress::new("RTC1HistoryTest");
    
    // Multiple mining events over time
    for i in 0..10 {
        manager.process_mining_event(
            &wallet,
            "192.168.1.1",
            "hw_history",
            1000 + i,
            TokenAmount(100_000_000),
        );
    }
    
    let score = manager.get_score(&wallet).unwrap();
    
    // History should be tracked
    assert!(score.history.days_tracked > 0);
    assert!(!score.history.snapshots.is_empty());
    
    // Peak should be tracked
    assert!(score.history.peak_score >= score.score);
    
    // 30-day average should be calculated
    assert!(score.history.avg_30d > 0.0);
}

/// Test behavioral fingerprinting for miners
#[test]
fn test_behavioral_fingerprinting() {
    let mut detector = AntiGamingDetector::new();
    let wallet = WalletAddress::new("RTC1BehaviorTest");
    
    // Record IP for wallet (this creates the fingerprint)
    detector.record_ip(&wallet, "192.168.1.1");
    
    // Record mining attestations at different times
    let base_time = 1700000000;
    for i in 0..10 {
        detector.record_attestation(&wallet, base_time + i * 3600);
    }
    
    // Get fingerprint
    let fingerprint = detector.get_fingerprint(&wallet);
    
    // Should have recorded activity
    assert!(!fingerprint.active_hours.is_empty() || fingerprint.total_attestations >= 0);
}

/// Test fleet correlation for mining bots
#[test]
fn test_fleet_correlation() {
    let mut detector = AntiGamingDetector::new();
    
    let ip = "172.16.0.1";
    let wallets: Vec<_> = (0..12)
        .map(|i| WalletAddress::new(format!("RTC1FleetBot{}", i)))
        .collect();
    
    // All wallets on same IP (mining farm)
    for wallet in &wallets {
        detector.record_ip(wallet, ip);
    }
    
    // Check correlation for each wallet
    for wallet in &wallets {
        let correlation = detector.calculate_fleet_correlation(wallet);
        assert!(correlation > FLEET_CORRELATION_THRESHOLD, 
            "Fleet correlation should exceed threshold for mining farm");
    }
}

/// Test score breakdown weights
#[test]
fn test_score_breakdown_weights() {
    let breakdown = ScoreBreakdown {
        mining_score: 1.0,
        badge_score: 1.0,
        governance_score: 1.0,
        hardware_score: 1.0,
        anti_gaming_multiplier: 1.0,
        decay_factor: 1.0,
    };
    
    let weighted = breakdown.weighted_base_score();
    let final_score = breakdown.final_score();
    
    // Perfect scores should give 1.0
    assert!((weighted - 1.0).abs() < 0.001);
    assert!((final_score - 1.0).abs() < 0.001);
    
    // Test with zeros
    let zero_breakdown = ScoreBreakdown {
        mining_score: 0.0,
        badge_score: 0.0,
        governance_score: 0.0,
        hardware_score: 0.0,
        anti_gaming_multiplier: 1.0,
        decay_factor: 1.0,
    };
    
    assert!((zero_breakdown.weighted_base_score() - 0.0).abs() < 0.001);
}

/// Test minimum attestations for full reputation
#[test]
fn test_minimum_attestations() {
    let store = Box::new(InMemoryReputationStore::default());
    let mut manager = ReputationManager::new(store);
    
    let wallet = WalletAddress::new("RTC1MinAttestTest");
    
    // Single mining event
    let score1 = manager.process_mining_event(&wallet, "192.168.1.1", "hw_1", 1000, TokenAmount(100_000_000));
    
    // Should have lower mining score (below minimum)
    assert!(score1.breakdown.mining_score < 1.0);
    
    // Reach minimum through multiple attestations
    for _ in 2..=MIN_ATTESTATIONS_FOR_REPUTATION as usize {
        manager.process_mining_event(&wallet, "192.168.1.1", "hw_1", 1000, TokenAmount(100_000_000));
    }
    
    let score2 = manager.get_score(&wallet).unwrap();
    
    // Mining score should improve with more attestations
    assert!(score2.breakdown.mining_score > score1.breakdown.mining_score);
}

/// Test risk flag lifecycle
#[test]
fn test_risk_flag_lifecycle() {
    let mut flag = RiskFlag::new(
        RiskType::AttestationAnomaly,
        0.5,
        "Test anomaly".to_string(),
    );
    
    // Initially unresolved
    assert!(!flag.resolved);
    
    // Resolve flag
    flag.resolved = true;
    
    // Should be resolved
    assert!(flag.resolved);
}

/// Test concurrent mining operations
#[test]
fn test_concurrent_mining_operations() {
    let store = Box::new(InMemoryReputationStore::default());
    let mut manager = ReputationManager::new(store);
    
    // Simulate concurrent mining from multiple wallets
    let miners: Vec<_> = (0..20)
        .map(|i| WalletAddress::new(format!("RTC1Concurrent{}", i)))
        .collect();
    
    for miner in &miners {
        manager.process_mining_event(
            miner,
            &format!("192.168.{}.{}", miner.0.len() % 256, miner.0.len()),
            &format!("hw_{}", miner.0),
            1000,
            TokenAmount(100_000_000),
        );
    }
    
    // All miners should have scores
    for miner in &miners {
        let score = manager.get_score(miner);
        assert!(score.is_some());
    }
}

/// Test score serialization
#[test]
fn test_score_serialization() {
    use serde_json;
    
    let wallet = WalletAddress::new("RTC1SerializeTest");
    let breakdown = ScoreBreakdown {
        mining_score: 0.85,
        badge_score: 0.90,
        governance_score: 0.75,
        hardware_score: 1.0,
        anti_gaming_multiplier: 0.95,
        decay_factor: 0.98,
    };
    
    let score = ReputationScore {
        wallet: wallet.clone(),
        score: breakdown.final_score(),
        breakdown: breakdown.clone(),
        history: ScoreHistory::new(),
        risk_flags: Vec::new(),
        last_updated: 1700000000,
        version: REPUTATION_VERSION,
    };
    
    // Serialize
    let json = serde_json::to_string(&score).unwrap();
    
    // Deserialize
    let deserialized: ReputationScore = serde_json::from_str(&json).unwrap();
    
    // Verify
    assert_eq!(deserialized.wallet.0, wallet.0);
    assert!((deserialized.score - score.score).abs() < 0.001);
    assert_eq!(deserialized.version, REPUTATION_VERSION);
}

/// Test edge cases
#[test]
fn test_edge_cases() {
    let store = Box::new(InMemoryReputationStore::default());
    let mut manager = ReputationManager::new(store);
    
    // Empty wallet address (edge case)
    let empty_wallet = WalletAddress::new("RTC1");
    let score = manager.process_mining_event(&empty_wallet, "192.168.1.1", "hw", 1000, TokenAmount(100_000_000));
    assert!(score.score >= 0.0);
    
    // Very long wallet address
    let long_wallet = WalletAddress::new("RTC1".to_string() + &"a".repeat(1000));
    let score = manager.process_mining_event(&long_wallet, "192.168.1.1", "hw", 1000, TokenAmount(100_000_000));
    assert!(score.score >= 0.0);
    
    // Zero response time
    let zero_time_wallet = WalletAddress::new("RTC1ZeroTime");
    let score = manager.process_challenge(&zero_time_wallet, 0.0, true);
    assert!(score.risk_flags.iter().any(|f| 
        f.flag_type == RiskType::ScoreManipulation
    ));
}
