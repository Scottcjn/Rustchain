// Integration tests for Agent Reputation Score System
// ====================================================

use rustchain::agent_reputation::*;
use rustchain::core_types::{WalletAddress, TokenAmount};

/// Test complete attestation flow
#[test]
fn test_complete_attestation_flow() {
    let store = Box::new(InMemoryReputationStore::default());
    let mut manager = ReputationManager::new(store);
    
    let wallet = WalletAddress::new("RTC1TestMiner123");
    
    // Initial state - should have neutral score
    let initial = manager.get_score(&wallet);
    assert!(initial.is_none()); // No score until first activity
    
    // First attestation
    let score1 = manager.process_attestation(
        &wallet,
        "192.168.1.100",
        "hw_fingerprint_abc",
        true,
    );
    
    assert!(score1.score >= 0.5); // Should start at least neutral
    assert_eq!(score1.version, REPUTATION_VERSION);
    
    // Second attestation (improves score)
    let score2 = manager.process_attestation(
        &wallet,
        "192.168.1.100",
        "hw_fingerprint_abc",
        true,
    );
    
    assert!(score2.score >= score1.score); // Should improve or stay same
    
    // Verify history tracking
    assert!(score2.history.days_tracked > 0);
}

/// Test failed attestation impact
#[test]
fn test_failed_attestation() {
    let store = Box::new(InMemoryReputationStore::default());
    let mut manager = ReputationManager::new(store);
    
    let wallet = WalletAddress::new("RTC1TestMiner456");
    
    // Successful attestation
    let score1 = manager.process_attestation(
        &wallet,
        "192.168.1.100",
        "hw_fingerprint_def",
        true,
    );
    
    // Failed attestation
    let score2 = manager.process_attestation(
        &wallet,
        "192.168.1.100",
        "hw_fingerprint_def",
        false,
    );
    
    // Score should decrease after failure
    assert!(score2.score < score1.score);
    assert!(score2.breakdown.attestation_score < 1.0);
}

/// Test Sybil cluster detection
#[test]
fn test_sybil_cluster_detection() {
    let store = Box::new(InMemoryReputationStore::default());
    let mut manager = ReputationManager::new(store);
    
    let ip = "10.0.0.100";
    let mut wallets = Vec::new();
    
    // Create 5 wallets on same IP
    for i in 0..5 {
        let wallet = WalletAddress::new(format!("RTC1SybilMiner{}", i));
        wallets.push(wallet.clone());
        
        manager.process_attestation(
            &wallet,
            ip,
            &format!("hw_fingerprint_{}", i),
            true,
        );
    }
    
    // Check that later wallets get flagged
    let last_wallet = wallets.last().unwrap();
    let score = manager.get_score(last_wallet).unwrap();
    
    // Should have Sybil cluster flag
    let has_sybil_flag = score.risk_flags.iter()
        .any(|f| f.flag_type == RiskType::SybilCluster);
    
    assert!(has_sybil_flag, "Should detect Sybil cluster");
}

/// Test hardware sharing detection
#[test]
fn test_hardware_sharing_detection() {
    let store = Box::new(InMemoryReputationStore::default());
    let mut manager = ReputationManager::new(store);
    
    let shared_hw = "shared_hardware_fingerprint";
    
    // Two wallets claiming same hardware
    let wallet1 = WalletAddress::new("RTC1HardwareSharer1");
    let wallet2 = WalletAddress::new("RTC1HardwareSharer2");
    
    manager.process_attestation(&wallet1, "192.168.1.1", shared_hw, true);
    let score2 = manager.process_attestation(&wallet2, "192.168.1.2", shared_hw, true);
    
    // Second wallet should be flagged
    let has_hw_flag = score2.risk_flags.iter()
        .any(|f| f.flag_type == RiskType::HardwareInconsistency);
    
    assert!(has_hw_flag, "Should detect hardware sharing");
}

/// Test reputation decay
#[test]
fn test_reputation_decay() {
    let store = Box::new(InMemoryReputationStore::default());
    let mut manager = ReputationManager::new(store);
    
    let wallet = WalletAddress::new("RTC1DecayTest");
    
    // Build up reputation
    for _ in 0..10 {
        manager.process_attestation(
            &wallet,
            "192.168.1.1",
            "hw_fingerprint",
            true,
        );
    }
    
    let score_before = manager.get_score(&wallet).unwrap();
    let decay_factor_before = score_before.breakdown.decay_factor;
    
    // Apply decay (simulates inactivity)
    manager.apply_decay();
    
    let score_after = manager.get_score(&wallet).unwrap();
    let decay_factor_after = score_after.breakdown.decay_factor;
    
    // Decay factor should decrease
    assert!(decay_factor_after <= decay_factor_before);
}

/// Test challenge-response system
#[test]
fn test_challenge_response_system() {
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

/// Test community interaction scoring
#[test]
fn test_community_interaction_scoring() {
    let store = Box::new(InMemoryReputationStore::default());
    let mut manager = ReputationManager::new(store);
    
    let wallet = WalletAddress::new("RTC1CommunityMiner");
    
    // Initial attestation
    manager.process_attestation(&wallet, "192.168.1.1", "hw_123", true);
    
    // Positive community interactions
    for _ in 0..5 {
        manager.process_community_interaction(
            &wallet,
            "help_new_miner",
            1.0,
        );
    }
    
    let score = manager.get_score(&wallet).unwrap();
    
    // Community score should be high
    assert!(score.breakdown.community_score >= 0.9);
    
    // Overall score should benefit
    assert!(score.score > 0.5);
}

/// Test top wallets ranking
#[test]
fn test_top_wallets_ranking() {
    let store = Box::new(InMemoryReputationStore::default());
    let mut manager = ReputationManager::new(store);
    
    // Create wallets with different activity levels
    let wallets: Vec<_> = (0..10)
        .map(|i| WalletAddress::new(format!("RTC1RankMiner{}", i)))
        .collect();
    
    // Wallet 0: Most active (highest score)
    for _ in 0..20 {
        manager.process_attestation(&wallets[0], "192.168.1.0", "hw_0", true);
    }
    
    // Wallet 1-4: Moderately active
    for (i, wallet) in wallets[1..5].iter().enumerate() {
        for _ in 0..10 {
            manager.process_attestation(
                wallet,
                &format!("192.168.1.{}", i + 1),
                &format!("hw_{}", i + 1),
                true,
            );
        }
    }
    
    // Wallet 5-9: Minimal activity
    for (i, wallet) in wallets[5..10].iter().enumerate() {
        manager.process_attestation(
            wallet,
            &format!("192.168.1.{}", i + 5),
            &format!("hw_{}", i + 5),
            true,
        );
    }
    
    // Get top 5
    let top = manager.get_top_wallets(5);
    
    assert_eq!(top.len(), 5);
    
    // Most active wallet should be in top
    assert!(top.iter().any(|(w, _)| w.0 == wallets[0].0));
}

/// Test threshold filtering
#[test]
fn test_threshold_filtering() {
    let store = Box::new(InMemoryReputationStore::default());
    let mut manager = ReputationManager::new(store);
    
    // Create wallets with varying scores
    let high_score_wallet = WalletAddress::new("RTC1HighScore");
    let low_score_wallet = WalletAddress::new("RTC1LowScore");
    
    // Build high score
    for _ in 0..20 {
        manager.process_attestation(&high_score_wallet, "192.168.1.1", "hw_high", true);
    }
    
    // Low score (single attestation)
    manager.process_attestation(&low_score_wallet, "192.168.1.2", "hw_low", true);
    
    // Filter with high threshold
    let qualified = manager.get_above_threshold(0.7);
    
    // High score wallet should qualify
    assert!(qualified.iter().any(|(w, _)| w.0 == high_score_wallet.0));
    
    // Low score wallet should not qualify (if score < 0.7)
    let low_qualifies = qualified.iter().any(|(w, _)| w.0 == low_score_wallet.0);
    assert!(!low_qualifies || qualified.iter()
        .find(|(w, _)| w.0 == low_score_wallet.0)
        .unwrap().1.score >= 0.7);
}

/// Test score history tracking
#[test]
fn test_score_history_tracking() {
    let store = Box::new(InMemoryReputationStore::default());
    let mut manager = ReputationManager::new(store);
    
    let wallet = WalletAddress::new("RTC1HistoryTest");
    
    // Multiple attestations over time
    for i in 0..10 {
        manager.process_attestation(
            &wallet,
            "192.168.1.1",
            "hw_history",
            i % 5 != 0, // Occasional failure
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

/// Test behavioral fingerprinting
#[test]
fn test_behavioral_fingerprinting() {
    let mut detector = AntiGamingDetector::new();
    let wallet = WalletAddress::new("RTC1BehaviorTest");
    
    // Record attestations at different times
    let base_time = 1700000000;
    for i in 0..10 {
        detector.record_attestation(&wallet, base_time + i * 3600);
    }
    
    // Get fingerprint
    let fingerprint = detector.get_fingerprint(&wallet);
    
    // Should have recorded activity
    assert!(fingerprint.avg_attestation_interval > 0.0);
    assert!(!fingerprint.active_hours.is_empty());
}

/// Test fleet correlation calculation
#[test]
fn test_fleet_correlation() {
    let mut detector = AntiGamingDetector::new();
    
    let ip = "172.16.0.1";
    let wallets: Vec<_> = (0..6)
        .map(|i| WalletAddress::new(format!("RTC1FleetBot{}", i)))
        .collect();
    
    // All wallets on same IP
    for wallet in &wallets {
        detector.record_ip(wallet, ip);
    }
    
    // Check correlation for each wallet
    for wallet in &wallets {
        let correlation = detector.calculate_fleet_correlation(wallet);
        assert!(correlation > FLEET_CORRELATION_THRESHOLD, 
            "Fleet correlation should exceed threshold");
    }
}

/// Test anti-gaming multiplier calculation
#[test]
fn test_anti_gaming_multiplier() {
    let mut detector = AntiGamingDetector::new();
    let wallet = WalletAddress::new("RTC1MultiplierTest");
    
    // Clean wallet - no flags
    let multiplier_clean = detector.calculate_multiplier(&wallet, &[]);
    assert!((multiplier_clean - 1.0).abs() < 0.01);
    
    // Wallet with flags
    let flags = vec![
        RiskFlag::new(RiskType::AttestationAnomaly, 0.5, "Test flag"),
    ];
    
    let multiplier_flagged = detector.calculate_multiplier(&wallet, &flags);
    assert!(multiplier_flagged < multiplier_clean);
    assert!(multiplier_flagged >= 0.0);
}

/// Test score breakdown weights
#[test]
fn test_score_breakdown_weights() {
    let breakdown = ScoreBreakdown {
        uptime_score: 1.0,
        attestation_score: 1.0,
        hardware_score: 1.0,
        community_score: 1.0,
        history_score: 1.0,
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
        uptime_score: 0.0,
        attestation_score: 0.0,
        hardware_score: 0.0,
        community_score: 0.0,
        history_score: 0.0,
        anti_gaming_multiplier: 1.0,
        decay_factor: 1.0,
    };
    
    assert!((zero_breakdown.weighted_base_score() - 0.0).abs() < 0.001);
}

/// Test minimum attestations requirement
#[test]
fn test_minimum_attestations() {
    let store = Box::new(InMemoryReputationStore::default());
    let mut manager = ReputationManager::new(store);
    
    let wallet = WalletAddress::new("RTC1MinAttestTest");
    
    // Single attestation
    let score1 = manager.process_attestation(&wallet, "192.168.1.1", "hw_1", true);
    
    // Should have lower attestation score (below minimum)
    assert!(score1.breakdown.attestation_score < 1.0);
    
    // Reach minimum
    for i in 2..=MIN_ATTESTATIONS_FOR_REPUTATION as usize {
        manager.process_attestation(
            &wallet,
            "192.168.1.1",
            "hw_1",
            true,
        );
    }
    
    let score2 = manager.get_score(&wallet).unwrap();
    
    // Attestation score should improve
    assert!(score2.breakdown.attestation_score > score1.breakdown.attestation_score);
}

/// Test risk flag resolution
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

/// Test concurrent wallet operations
#[test]
fn test_concurrent_operations() {
    let store = Box::new(InMemoryReputationStore::default());
    let mut manager = ReputationManager::new(store);
    
    // Simulate concurrent attestations from multiple wallets
    let wallets: Vec<_> = (0..20)
        .map(|i| WalletAddress::new(format!("RTC1Concurrent{}", i)))
        .collect();
    
    for wallet in &wallets {
        manager.process_attestation(
            wallet,
            &format!("192.168.{}.{}", wallet.0.len() % 256, wallet.0.len()),
            &format!("hw_{}", wallet.0),
            true,
        );
    }
    
    // All wallets should have scores
    for wallet in &wallets {
        let score = manager.get_score(wallet);
        assert!(score.is_some());
    }
}

/// Test serialization/deserialization
#[test]
fn test_score_serialization() {
    use serde_json;
    
    let wallet = WalletAddress::new("RTC1SerializeTest");
    let breakdown = ScoreBreakdown {
        uptime_score: 0.85,
        attestation_score: 0.90,
        hardware_score: 1.0,
        community_score: 0.75,
        history_score: 0.80,
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
    let score = manager.process_attestation(&empty_wallet, "192.168.1.1", "hw", true);
    assert!(score.score >= 0.0);
    
    // Very long wallet address
    let long_wallet = WalletAddress::new("RTC1".to_string() + &"a".repeat(1000));
    let score = manager.process_attestation(&long_wallet, "192.168.1.1", "hw", true);
    assert!(score.score >= 0.0);
    
    // Zero response time
    let zero_time_wallet = WalletAddress::new("RTC1ZeroTime");
    let score = manager.process_challenge(&zero_time_wallet, 0.0, true);
    assert!(score.risk_flags.iter().any(|f| 
        f.flag_type == RiskType::ScoreManipulation
    ));
}
