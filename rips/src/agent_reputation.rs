// RIP-006: On-Chain Agent Reputation Score System
// ================================================
// Comprehensive reputation scoring for RustChain agents and validators
// Status: IMPLEMENTATION
// Author: Flamekeeper Scott
// Created: 2026-03-07

use std::collections::{HashMap, HashSet, VecDeque};
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use sha2::{Sha256, Digest};
use serde::{Serialize, Deserialize};

// Import from RIP-001
use crate::core_types::{WalletAddress, TokenAmount};

/// Reputation score version for schema tracking
pub const REPUTATION_VERSION: u32 = 1;

/// Minimum reputation score required for certain operations
pub const MIN_REPUTATION_THRESHOLD: f64 = 0.3;

/// Maximum reputation score (capped at 1.0)
pub const MAX_REPUTATION_SCORE: f64 = 1.0;

/// Base reputation decay per day of inactivity (5%)
pub const DAILY_DECAY_RATE: f64 = 0.05;

/// Time window for recent activity tracking (30 days)
pub const ACTIVITY_WINDOW_DAYS: u64 = 30;

/// Minimum attestations required for full reputation calculation
pub const MIN_ATTESTATIONS_FOR_REPUTATION: u32 = 5;

/// Sliding window size for behavior analysis
pub const BEHAVIOR_WINDOW_SIZE: usize = 100;

/// Suspicious activity threshold (triggers investigation)
pub const SUSPICIOUS_ACTIVITY_THRESHOLD: f64 = 0.7;

/// Fleet correlation threshold (above this = likely Sybil)
pub const FLEET_CORRELATION_THRESHOLD: f64 = 0.85;

/// Maximum IP addresses per wallet before flagging
pub const MAX_IPS_PER_WALLET: usize = 5;

/// Maximum wallets per IP before flagging
pub const MAX_WALLETS_PER_IP: usize = 3;

/// Time-based challenge response window (seconds)
pub const CHALLENGE_RESPONSE_WINDOW: u64 = 300;

/// Reputation decay half-life in days
pub const REPUTATION_HALF_LIFE_DAYS: f64 = 14.0;

/// Agent reputation score with detailed breakdown
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReputationScore {
    /// Wallet address this score belongs to
    pub wallet: WalletAddress,
    
    /// Overall reputation score (0.0 - 1.0)
    pub score: f64,
    
    /// Detailed score breakdown
    pub breakdown: ScoreBreakdown,
    
    /// Historical scores for trend analysis
    pub history: ScoreHistory,
    
    /// Risk flags and warnings
    pub risk_flags: Vec<RiskFlag>,
    
    /// Last update timestamp
    pub last_updated: u64,
    
    /// Version of scoring algorithm used
    pub version: u32,
}

/// Detailed breakdown of reputation components
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScoreBreakdown {
    /// Uptime reliability score (0.0 - 1.0) - 30% weight
    pub uptime_score: f64,
    
    /// Attestation consistency score (0.0 - 1.0) - 25% weight
    pub attestation_score: f64,
    
    /// Hardware authenticity score (0.0 - 1.0) - 20% weight
    pub hardware_score: f64,
    
    /// Community interaction score (0.0 - 1.0) - 15% weight
    pub community_score: f64,
    
    /// Historical behavior score (0.0 - 1.0) - 10% weight
    pub history_score: f64,
    
    /// Anti-gaming penalty multiplier (0.0 - 1.0)
    pub anti_gaming_multiplier: f64,
    
    /// Time decay factor (0.0 - 1.0)
    pub decay_factor: f64,
}

impl ScoreBreakdown {
    /// Calculate weighted base score before penalties
    pub fn weighted_base_score(&self) -> f64 {
        self.uptime_score * 0.30 +
        self.attestation_score * 0.25 +
        self.hardware_score * 0.20 +
        self.community_score * 0.15 +
        self.history_score * 0.10
    }
    
    /// Calculate final score with all modifiers
    pub fn final_score(&self) -> f64 {
        let base = self.weighted_base_score();
        base * self.anti_gaming_multiplier * self.decay_factor
    }
}

/// Historical score tracking
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScoreHistory {
    /// Peak reputation score achieved
    pub peak_score: f64,
    
    /// Average score over last 30 days
    pub avg_30d: f64,
    
    /// Score trend direction (positive = improving)
    pub trend_7d: f64,
    
    /// Total days tracked
    pub days_tracked: u64,
    
    /// Recent score snapshots (timestamp, score)
    pub snapshots: VecDeque<(u64, f64)>,
}

impl ScoreHistory {
    pub fn new() -> Self {
        ScoreHistory {
            peak_score: 0.0,
            avg_30d: 0.0,
            trend_7d: 0.0,
            days_tracked: 0,
            snapshots: VecDeque::with_capacity(30),
        }
    }
    
    /// Add a new score snapshot
    pub fn add_snapshot(&mut self, timestamp: u64, score: f64) {
        self.snapshots.push_back((timestamp, score));
        
        // Keep only last 30 days
        let cutoff = timestamp.saturating_sub(ACTIVITY_WINDOW_DAYS * 86400);
        while let Some((ts, _)) = self.snapshots.front() {
            if *ts < cutoff {
                self.snapshots.pop_front();
            } else {
                break;
            }
        }
        
        // Update peak
        if score > self.peak_score {
            self.peak_score = score;
        }
        
        // Update 30-day average
        self.update_avg_30d();
        
        // Update 7-day trend
        self.update_trend_7d();
    }
    
    fn update_avg_30d(&mut self) {
        if self.snapshots.is_empty() {
            self.avg_30d = 0.0;
            return;
        }
        
        let sum: f64 = self.snapshots.iter().map(|(_, s)| s).sum();
        self.avg_30d = sum / self.snapshots.len() as f64;
    }
    
    fn update_trend_7d(&mut self) {
        if self.snapshots.len() < 2 {
            self.trend_7d = 0.0;
            return;
        }
        
        let cutoff = current_timestamp().saturating_sub(7 * 86400);
        let recent: Vec<_> = self.snapshots.iter().filter(|(ts, _)| *ts >= cutoff).collect();
        
        if recent.len() < 2 {
            self.trend_7d = 0.0;
            return;
        }
        
        let first = recent.first().unwrap().1;
        let last = recent.last().unwrap().1;
        self.trend_7d = last - first;
    }
}

/// Risk flags for suspicious behavior
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RiskFlag {
    /// Flag type
    pub flag_type: RiskType,
    
    /// Severity level (0.0 - 1.0)
    pub severity: f64,
    
    /// Description of the issue
    pub description: String,
    
    /// Timestamp when flagged
    pub flagged_at: u64,
    
    /// Whether this flag has been resolved
    pub resolved: bool,
}

/// Types of risk flags
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum RiskType {
    /// Multiple wallets from same IP
    SybilCluster,
    
    /// Unusual attestation patterns
    AttestationAnomaly,
    
    /// Hardware fingerprint inconsistency
    HardwareInconsistency,
    
    /// Rapid score manipulation attempt
    ScoreManipulation,
    
    /// Fleet behavior detected
    FleetBehavior,
    
    /// Challenge response failure
    ChallengeFailure,
    
    /// IP address reputation issue
    IPReputation,
    
    /// Temporal anomaly (impossible travel, etc.)
    TemporalAnomaly,
}

impl RiskFlag {
    pub fn new(flag_type: RiskType, severity: f64, description: String) -> Self {
        RiskFlag {
            flag_type,
            severity,
            description,
            flagged_at: current_timestamp(),
            resolved: false,
        }
    }
}

/// Agent activity record
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ActivityRecord {
    /// Activity timestamp
    pub timestamp: u64,
    
    /// Type of activity
    pub activity_type: ActivityType,
    
    /// Associated metadata
    pub metadata: ActivityMetadata,
    
    /// Outcome/score of activity
    pub outcome: f64,
}

/// Types of agent activities
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum ActivityType {
    /// Hardware attestation submitted
    Attestation,
    
    /// Block mined/validated
    BlockMining,
    
    /// Community interaction (help, governance vote)
    CommunityInteraction,
    
    /// Challenge response
    ChallengeResponse,
    
    /// Badge earned
    BadgeEarned,
    
    /// Peer endorsement received
    Endorsement,
}

/// Activity metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ActivityMetadata {
    /// IP address (hashed for privacy)
    pub ip_hash: Option<String>,
    
    /// Hardware fingerprint hash
    pub hardware_hash: Option<String>,
    
    /// Geographic region (coarse)
    pub region: Option<String>,
    
    /// Session ID
    pub session_id: Option<String>,
    
    /// Additional context
    pub extra: HashMap<String, String>,
}

/// Anti-gaming detection system
#[derive(Debug)]
pub struct AntiGamingDetector {
    /// IP to wallet mapping
    ip_wallet_map: HashMap<String, HashSet<WalletAddress>>,
    
    /// Wallet to IP mapping
    wallet_ip_map: HashMap<WalletAddress, HashSet<String>>,
    
    /// Hardware fingerprint to wallet mapping
    hardware_wallet_map: HashMap<String, HashSet<WalletAddress>>,
    
    /// Recent attestation patterns
    attestation_patterns: HashMap<WalletAddress, VecDeque<u64>>,
    
    /// Behavioral fingerprints
    behavioral_fingerprints: HashMap<WalletAddress, BehavioralFingerprint>,
    
    /// Challenge-response tracking
    challenge_tracker: HashMap<WalletAddress, ChallengeRecord>,
}

/// Behavioral fingerprint for anomaly detection
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BehavioralFingerprint {
    /// Average time between attestations
    pub avg_attestation_interval: f64,
    
    /// Variance in attestation timing
    pub timing_variance: f64,
    
    /// Typical activity hours (0-23)
    pub active_hours: HashSet<u8>,
    
    /// Common regions
    pub common_regions: HashSet<String>,
    
    /// Hardware consistency score
    pub hardware_consistency: f64,
}

impl BehavioralFingerprint {
    pub fn new() -> Self {
        BehavioralFingerprint {
            avg_attestation_interval: 0.0,
            timing_variance: 0.0,
            active_hours: HashSet::new(),
            common_regions: HashSet::new(),
            hardware_consistency: 1.0,
        }
    }
}

/// Challenge-response record
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChallengeRecord {
    /// Last challenge issued
    pub last_challenge: u64,
    
    /// Challenge count
    pub total_challenges: u32,
    
    /// Successful responses
    pub successful_responses: u32,
    
    /// Failed responses
    pub failed_responses: u32,
    
    /// Average response time
    pub avg_response_time: f64,
}

impl ChallengeRecord {
    pub fn new() -> Self {
        ChallengeRecord {
            last_challenge: 0,
            total_challenges: 0,
            successful_responses: 0,
            failed_responses: 0,
            avg_response_time: 0.0,
        }
    }
    
    pub fn success_rate(&self) -> f64 {
        if self.total_challenges == 0 {
            return 1.0;
        }
        self.successful_responses as f64 / self.total_challenges as f64
    }
}

impl AntiGamingDetector {
    pub fn new() -> Self {
        AntiGamingDetector {
            ip_wallet_map: HashMap::new(),
            wallet_ip_map: HashMap::new(),
            hardware_wallet_map: HashMap::new(),
            attestation_patterns: HashMap::new(),
            behavioral_fingerprints: HashMap::new(),
            challenge_tracker: HashMap::new(),
        }
    }
    
    /// Record wallet-IP association
    pub fn record_ip(&mut self, wallet: &WalletAddress, ip: &str) -> Vec<RiskFlag> {
        let mut flags = Vec::new();
        
        let ip_hash = self.hash_ip(ip);
        
        // Update mappings
        self.ip_wallet_map
            .entry(ip_hash.clone())
            .or_insert_with(HashSet::new)
            .insert(wallet.clone());
        
        self.wallet_ip_map
            .entry(wallet.clone())
            .or_insert_with(HashSet::new)
            .insert(ip_hash.clone());
        
        // Check for Sybil clustering
        let wallets_on_ip = self.ip_wallet_map.get(&ip_hash).unwrap().len();
        if wallets_on_ip > MAX_WALLETS_PER_IP {
            flags.push(RiskFlag::new(
                RiskType::SybilCluster,
                (wallets_on_ip - MAX_WALLETS_PER_IP) as f64 * 0.2,
                format!("IP has {} wallets (threshold: {})", wallets_on_ip, MAX_WALLETS_PER_IP),
            ));
        }
        
        // Check wallet IP count
        let ip_count = self.wallet_ip_map.get(wallet).unwrap().len();
        if ip_count > MAX_IPS_PER_WALLET {
            flags.push(RiskFlag::new(
                RiskType::IPReputation,
                (ip_count - MAX_IPS_PER_WALLET) as f64 * 0.15,
                format!("Wallet using {} IPs (threshold: {})", ip_count, MAX_IPS_PER_WALLET),
            ));
        }
        
        flags
    }
    
    /// Record hardware fingerprint
    pub fn record_hardware(&mut self, wallet: &WalletAddress, hw_hash: &str) -> Vec<RiskFlag> {
        let mut flags = Vec::new();
        
        self.hardware_wallet_map
            .entry(hw_hash.to_string())
            .or_insert_with(HashSet::new)
            .insert(wallet.clone());
        
        // Check for hardware sharing (multiple wallets on same hardware)
        let wallet_count = self.hardware_wallet_map.get(hw_hash).unwrap().len();
        if wallet_count > 1 {
            flags.push(RiskFlag::new(
                RiskType::HardwareInconsistency,
                wallet_count as f64 * 0.3,
                format!("Hardware shared by {} wallets", wallet_count),
            ));
        }
        
        flags
    }
    
    /// Record attestation timestamp
    pub fn record_attestation(&mut self, wallet: &WalletAddress, timestamp: u64) -> Vec<RiskFlag> {
        let mut flags = Vec::new();
        
        let patterns = self.attestation_patterns
            .entry(wallet.clone())
            .or_insert_with(|| VecDeque::with_capacity(BEHAVIOR_WINDOW_SIZE));
        
        patterns.push_back(timestamp);
        
        // Keep window size manageable
        if patterns.len() > BEHAVIOR_WINDOW_SIZE {
            patterns.pop_front();
        }
        
        // Check for bot-like patterns (too regular)
        if patterns.len() >= 10 {
            let intervals: Vec<u64> = patterns.iter().collect::<Vec<_>>().windows(2)
                .map(|w| w[1] - w[0])
                .collect();

            let avg_interval = intervals.iter().sum::<u64>() as f64 / intervals.len() as f64;
            let variance = intervals.iter()
                .map(|i| (*i as f64 - avg_interval).powi(2))
                .sum::<f64>() / intervals.len() as f64;
            
            // Very low variance = suspicious automation
            if variance < 100.0 && avg_interval > 0.0 {
                flags.push(RiskFlag::new(
                    RiskType::AttestationAnomaly,
                    0.5,
                    format!("Suspiciously regular attestations (variance: {:.2})", variance),
                ));
            }
        }
        
        flags
    }
    
    /// Calculate fleet correlation score
    pub fn calculate_fleet_correlation(&self, wallet: &WalletAddress) -> f64 {
        let mut correlation = 0.0;
        
        if let Some(ips) = self.wallet_ip_map.get(wallet) {
            for ip in ips {
                if let Some(wallets) = self.ip_wallet_map.get(ip) {
                    // More wallets on same IP = higher correlation
                    correlation += (wallets.len() - 1) as f64 * 0.1;
                }
            }
        }
        
        correlation.min(1.0)
    }
    
    /// Issue a challenge to a wallet
    pub fn issue_challenge(&mut self, wallet: &WalletAddress) {
        let record = self.challenge_tracker
            .entry(wallet.clone())
            .or_insert_with(ChallengeRecord::new);
        
        record.last_challenge = current_timestamp();
        record.total_challenges += 1;
    }
    
    /// Record challenge response
    pub fn record_challenge_response(&mut self, wallet: &WalletAddress, success: bool, response_time: f64) -> Vec<RiskFlag> {
        let mut flags = Vec::new();
        
        let record = self.challenge_tracker
            .entry(wallet.clone())
            .or_insert_with(ChallengeRecord::new);
        
        if success {
            record.successful_responses += 1;
        } else {
            record.failed_responses += 1;
            flags.push(RiskFlag::new(
                RiskType::ChallengeFailure,
                0.7,
                "Failed challenge response".to_string(),
            ));
        }
        
        // Update average response time
        record.avg_response_time = (record.avg_response_time * (record.successful_responses - 1) as f64 + response_time)
            / record.successful_responses.max(1) as f64;
        
        // Check for too-fast responses (automated)
        if response_time < 1.0 {
            flags.push(RiskFlag::new(
                RiskType::ScoreManipulation,
                0.4,
                format!("Suspiciously fast response time: {:.2}s", response_time),
            ));
        }
        
        flags
    }
    
    /// Get or create behavioral fingerprint
    pub fn get_fingerprint(&mut self, wallet: &WalletAddress) -> &mut BehavioralFingerprint {
        self.behavioral_fingerprints
            .entry(wallet.clone())
            .or_insert_with(BehavioralFingerprint::new)
    }
    
    /// Calculate anti-gaming multiplier
    pub fn calculate_multiplier(&self, wallet: &WalletAddress, flags: &[RiskFlag]) -> f64 {
        let mut multiplier = 1.0;
        
        // Apply penalties for unresolved flags
        for flag in flags {
            if !flag.resolved {
                multiplier -= flag.severity * 0.3;
            }
        }
        
        // Apply fleet correlation penalty
        let fleet_corr = self.calculate_fleet_correlation(wallet);
        if fleet_corr > FLEET_CORRELATION_THRESHOLD {
            multiplier -= (fleet_corr - FLEET_CORRELATION_THRESHOLD) * 2.0;
        }
        
        // Check challenge success rate
        if let Some(record) = self.challenge_tracker.get(wallet) {
            let success_rate = record.success_rate();
            if success_rate < 0.8 {
                multiplier -= (0.8 - success_rate) * 0.5;
            }
        }
        
        multiplier.max(0.0)
    }
    
    fn hash_ip(&self, ip: &str) -> String {
        let mut hasher = Sha256::new();
        hasher.update(ip.as_bytes());
        hex::encode(&hasher.finalize()[..16])
    }
}

/// Reputation storage and retrieval
pub trait ReputationStore {
    /// Get reputation score for wallet
    fn get_score(&self, wallet: &WalletAddress) -> Option<ReputationScore>;
    
    /// Update reputation score
    fn update_score(&mut self, score: ReputationScore);
    
    /// Get top N wallets by reputation
    fn get_top_wallets(&self, n: usize) -> Vec<(WalletAddress, f64)>;
    
    /// Get all wallets with reputation above threshold
    fn get_above_threshold(&self, threshold: f64) -> Vec<(WalletAddress, ReputationScore)>;
    
    /// Get score history for wallet
    fn get_history(&self, wallet: &WalletAddress) -> Option<ScoreHistory>;
}

/// In-memory reputation store (for testing and lightweight nodes)
#[derive(Debug, Default)]
pub struct InMemoryReputationStore {
    scores: HashMap<WalletAddress, ReputationScore>,
}

impl ReputationStore for InMemoryReputationStore {
    fn get_score(&self, wallet: &WalletAddress) -> Option<ReputationScore> {
        self.scores.get(wallet).cloned()
    }
    
    fn update_score(&mut self, score: ReputationScore) {
        self.scores.insert(score.wallet.clone(), score);
    }
    
    fn get_top_wallets(&self, n: usize) -> Vec<(WalletAddress, f64)> {
        let mut wallets: Vec<_> = self.scores
            .iter()
            .map(|(w, s)| (w.clone(), s.score))
            .collect();
        
        wallets.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        wallets.truncate(n);
        wallets
    }
    
    fn get_above_threshold(&self, threshold: f64) -> Vec<(WalletAddress, ReputationScore)> {
        self.scores
            .iter()
            .filter(|(_, s)| s.score >= threshold)
            .map(|(w, s)| (w.clone(), s.clone()))
            .collect()
    }
    
    fn get_history(&self, wallet: &WalletAddress) -> Option<ScoreHistory> {
        self.scores.get(wallet).map(|s| s.history.clone())
    }
}

/// Reputation calculator and manager
pub struct ReputationManager {
    /// Reputation storage
    store: Box<dyn ReputationStore>,
    
    /// Anti-gaming detector
    anti_gaming: AntiGamingDetector,
    
    /// Activity log
    activity_log: HashMap<WalletAddress, VecDeque<ActivityRecord>>,
}

impl ReputationManager {
    pub fn new(store: Box<dyn ReputationStore>) -> Self {
        ReputationManager {
            store,
            anti_gaming: AntiGamingDetector::new(),
            activity_log: HashMap::new(),
        }
    }
    
    /// Process attestation and update reputation
    pub fn process_attestation(
        &mut self,
        wallet: &WalletAddress,
        ip: &str,
        hw_hash: &str,
        success: bool,
    ) -> ReputationScore {
        let timestamp = current_timestamp();
        
        // Record for anti-gaming
        let mut flags = Vec::new();
        flags.extend(self.anti_gaming.record_ip(wallet, ip));
        flags.extend(self.anti_gaming.record_hardware(wallet, hw_hash));
        flags.extend(self.anti_gaming.record_attestation(wallet, timestamp));
        
        // Update behavioral fingerprint
        let fingerprint = self.anti_gaming.get_fingerprint(wallet);
        fingerprint.active_hours.insert((timestamp / 3600 % 24) as u8);
        
        // Record activity
        self.record_activity(wallet, ActivityRecord {
            timestamp,
            activity_type: ActivityType::Attestation,
            metadata: ActivityMetadata {
                ip_hash: Some(self.anti_gaming.hash_ip(ip)),
                hardware_hash: Some(hw_hash.to_string()),
                region: None,
                session_id: None,
                extra: HashMap::new(),
            },
            outcome: if success { 1.0 } else { 0.0 },
        });
        
        // Calculate new score
        let score = self.calculate_score(wallet, flags);
        self.store.update_score(score.clone());
        
        score
    }
    
    /// Process block mining event
    pub fn process_block_mined(
        &mut self,
        wallet: &WalletAddress,
        block_height: u64,
        _reward: TokenAmount,
    ) -> ReputationScore {
        let timestamp = current_timestamp();
        
        self.record_activity(wallet, ActivityRecord {
            timestamp,
            activity_type: ActivityType::BlockMining,
            metadata: ActivityMetadata {
                ip_hash: None,
                hardware_hash: None,
                region: None,
                session_id: None,
                extra: {
                    let mut m = HashMap::new();
                    m.insert("block_height".to_string(), block_height.to_string());
                    m
                },
            },
            outcome: 1.0,
        });
        
        let score = self.calculate_score(wallet, Vec::new());
        self.store.update_score(score.clone());
        
        score
    }
    
    /// Process community interaction
    pub fn process_community_interaction(
        &mut self,
        wallet: &WalletAddress,
        interaction_type: &str,
        quality_score: f64,
    ) -> ReputationScore {
        let timestamp = current_timestamp();
        
        self.record_activity(wallet, ActivityRecord {
            timestamp,
            activity_type: ActivityType::CommunityInteraction,
            metadata: ActivityMetadata {
                ip_hash: None,
                hardware_hash: None,
                region: None,
                session_id: None,
                extra: {
                    let mut m = HashMap::new();
                    m.insert("interaction_type".to_string(), interaction_type.to_string());
                    m
                },
            },
            outcome: quality_score,
        });
        
        let score = self.calculate_score(wallet, Vec::new());
        self.store.update_score(score.clone());
        
        score
    }
    
    /// Issue and verify challenge
    pub fn process_challenge(
        &mut self,
        wallet: &WalletAddress,
        response_time: f64,
        success: bool,
    ) -> ReputationScore {
        let flags = self.anti_gaming.record_challenge_response(wallet, success, response_time);
        
        if !success {
            self.anti_gaming.issue_challenge(wallet);
        }
        
        self.record_activity(wallet, ActivityRecord {
            timestamp: current_timestamp(),
            activity_type: ActivityType::ChallengeResponse,
            metadata: ActivityMetadata {
                ip_hash: None,
                hardware_hash: None,
                region: None,
                session_id: None,
                extra: {
                    let mut m = HashMap::new();
                    m.insert("success".to_string(), success.to_string());
                    m.insert("response_time".to_string(), response_time.to_string());
                    m
                },
            },
            outcome: if success { 1.0 } else { 0.0 },
        });
        
        let score = self.calculate_score(wallet, flags);
        self.store.update_score(score.clone());
        
        score
    }
    
    /// Get current reputation score
    pub fn get_score(&self, wallet: &WalletAddress) -> Option<ReputationScore> {
        self.store.get_score(wallet)
    }
    
    /// Get top wallets by reputation
    pub fn get_top_wallets(&self, n: usize) -> Vec<(WalletAddress, f64)> {
        self.store.get_top_wallets(n)
    }
    
    /// Get wallets above threshold
    pub fn get_above_threshold(&self, threshold: f64) -> Vec<(WalletAddress, ReputationScore)> {
        self.store.get_above_threshold(threshold)
    }
    
    /// Apply time decay to all scores
    pub fn apply_decay(&mut self) {
        let timestamp = current_timestamp();
        
        // Get all current scores
        let wallets: Vec<_> = self.get_top_wallets(10000).iter().map(|(w, _)| w.clone()).collect();
        
        for wallet in wallets {
            if let Some(mut score) = self.store.get_score(&wallet) {
                // Calculate decay based on inactivity
                let last_activity = self.activity_log
                    .get(&wallet)
                    .and_then(|log| log.back())
                    .map(|r| r.timestamp)
                    .unwrap_or(0);
                
                let inactive_days = (timestamp - last_activity) / 86400;
                
                if inactive_days > 0 {
                    // Exponential decay
                    let decay = (-(inactive_days as f64) * DAILY_DECAY_RATE / REPUTATION_HALF_LIFE_DAYS).exp();
                    score.breakdown.decay_factor = decay;
                    
                    // Recalculate final score
                    score.score = score.breakdown.final_score();
                    score.last_updated = timestamp;
                    
                    self.store.update_score(score);
                }
            }
        }
    }
    
    fn record_activity(&mut self, wallet: &WalletAddress, record: ActivityRecord) {
        let log = self.activity_log
            .entry(wallet.clone())
            .or_insert_with(|| VecDeque::with_capacity(BEHAVIOR_WINDOW_SIZE));
        
        log.push_back(record);
        
        // Keep window manageable
        if log.len() > BEHAVIOR_WINDOW_SIZE {
            log.pop_front();
        }
    }
    
    fn calculate_score(&self, wallet: &WalletAddress, flags: Vec<RiskFlag>) -> ReputationScore {
        let timestamp = current_timestamp();
        
        // Get or create base score
        let base_score = self.store.get_score(wallet).unwrap_or_else(|| {
            ReputationScore {
                wallet: wallet.clone(),
                score: 0.5, // Start with neutral score
                breakdown: ScoreBreakdown {
                    uptime_score: 0.5,
                    attestation_score: 0.5,
                    hardware_score: 0.5,
                    community_score: 0.5,
                    history_score: 0.5,
                    anti_gaming_multiplier: 1.0,
                    decay_factor: 1.0,
                },
                history: ScoreHistory::new(),
                risk_flags: Vec::new(),
                last_updated: timestamp,
                version: REPUTATION_VERSION,
            }
        });
        
        // Calculate component scores from activity
        let activity = self.activity_log.get(wallet);
        
        let uptime_score = self.calculate_uptime_score(activity);
        let attestation_score = self.calculate_attestation_score(activity);
        let hardware_score = self.calculate_hardware_score(activity);
        let community_score = self.calculate_community_score(activity);
        let history_score = self.calculate_history_score(activity);
        
        // Calculate anti-gaming multiplier
        let anti_gaming_multiplier = self.anti_gaming.calculate_multiplier(wallet, &flags);
        
        // Calculate decay factor
        let decay_factor = base_score.breakdown.decay_factor;
        
        let breakdown = ScoreBreakdown {
            uptime_score,
            attestation_score,
            hardware_score,
            community_score,
            history_score,
            anti_gaming_multiplier,
            decay_factor,
        };
        
        let mut score = ReputationScore {
            wallet: wallet.clone(),
            score: breakdown.final_score(),
            breakdown,
            history: base_score.history,
            risk_flags: flags,
            last_updated: timestamp,
            version: REPUTATION_VERSION,
        };
        
        // Update history
        score.history.add_snapshot(timestamp, score.score);
        
        score
    }
    
    fn calculate_uptime_score(&self, activity: Option<&VecDeque<ActivityRecord>>) -> f64 {
        let Some(log) = activity else { return 0.5 };
        
        if log.is_empty() {
            return 0.5;
        }
        
        let timestamp = current_timestamp();
        let window_start = timestamp.saturating_sub(ACTIVITY_WINDOW_DAYS * 86400);
        
        let attestations: Vec<_> = log
            .iter()
            .filter(|r| r.activity_type == ActivityType::Attestation && r.timestamp >= window_start)
            .collect();
        
        if attestations.is_empty() {
            return 0.3;
        }
        
        // Score based on regularity and recency
        let last_attest = attestations.iter().map(|r| r.timestamp).max().unwrap_or(0);
        let recency_score = (1.0 - (timestamp - last_attest) as f64 / (7 * 86400) as f64).max(0.0);
        
        // Expected ~2 attestations per day
        let expected = ACTIVITY_WINDOW_DAYS * 2;
        let actual = attestations.len() as u64;
        let frequency_score = (actual as f64 / expected as f64).min(1.0);
        
        (recency_score + frequency_score) / 2.0
    }
    
    fn calculate_attestation_score(&self, activity: Option<&VecDeque<ActivityRecord>>) -> f64 {
        let Some(log) = activity else { return 0.5 };
        
        let attestations: Vec<_> = log
            .iter()
            .filter(|r| r.activity_type == ActivityType::Attestation)
            .collect();
        
        if attestations.is_empty() {
            return 0.5;
        }
        
        // Success rate
        let success_rate = attestations.iter().map(|r| r.outcome).sum::<f64>() / attestations.len() as f64;
        
        // Consistency (low variance in timing)
        if attestations.len() >= MIN_ATTESTATIONS_FOR_REPUTATION as usize {
            let intervals: Vec<u64> = attestations.windows(2)
                .map(|w| w[1].timestamp - w[0].timestamp)
                .collect();
            
            let avg = intervals.iter().sum::<u64>() as f64 / intervals.len() as f64;
            let variance = intervals.iter()
                .map(|i| (*i as f64 - avg).powi(2))
                .sum::<f64>() / intervals.len() as f64;
            
            // Some variance is good (human-like), too much is bad
            let consistency_score = if variance < 1000.0 {
                0.8
            } else if variance < 10000.0 {
                0.9
            } else {
                0.7
            };
            
            (success_rate + consistency_score) / 2.0
        } else {
            success_rate
        }
    }
    
    fn calculate_hardware_score(&self, activity: Option<&VecDeque<ActivityRecord>>) -> f64 {
        let Some(log) = activity else { return 0.5 };
        
        let hardware_hashes: HashSet<_> = log
            .iter()
            .filter_map(|r| r.metadata.hardware_hash.clone())
            .collect();
        
        // Single consistent hardware = good
        if hardware_hashes.len() <= 1 {
            1.0
        } else if hardware_hashes.len() <= 3 {
            0.7
        } else {
            0.4
        }
    }
    
    fn calculate_community_score(&self, activity: Option<&VecDeque<ActivityRecord>>) -> f64 {
        let Some(log) = activity else { return 0.5 };
        
        let interactions: Vec<_> = log
            .iter()
            .filter(|r| r.activity_type == ActivityType::CommunityInteraction)
            .collect();
        
        if interactions.is_empty() {
            return 0.5;
        }
        
        let avg_quality = interactions.iter().map(|r| r.outcome).sum::<f64>() / interactions.len() as f64;
        avg_quality.min(1.0)
    }
    
    fn calculate_history_score(&self, activity: Option<&VecDeque<ActivityRecord>>) -> f64 {
        let Some(log) = activity else { return 0.5 };
        
        if log.is_empty() {
            return 0.5;
        }
        
        // Longer history = better
        let history_len = log.len();
        let length_score = (history_len as f64 / BEHAVIOR_WINDOW_SIZE as f64).min(1.0);
        
        // Positive outcomes
        let positive_rate = log.iter().map(|r| r.outcome).sum::<f64>() / log.len() as f64;
        
        (length_score + positive_rate) / 2.0
    }
}

/// Helper to get current Unix timestamp
fn current_timestamp() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or(Duration::ZERO)
        .as_secs()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_reputation_score_creation() {
        let wallet = WalletAddress::new("RTC1TestAgent123");
        let breakdown = ScoreBreakdown {
            uptime_score: 0.8,
            attestation_score: 0.9,
            hardware_score: 1.0,
            community_score: 0.7,
            history_score: 0.6,
            anti_gaming_multiplier: 1.0,
            decay_factor: 1.0,
        };
        
        let score = ReputationScore {
            wallet: wallet.clone(),
            score: breakdown.final_score(),
            breakdown: breakdown.clone(),
            history: ScoreHistory::new(),
            risk_flags: Vec::new(),
            last_updated: current_timestamp(),
            version: REPUTATION_VERSION,
        };
        
        assert!(score.score > 0.0 && score.score <= 1.0);
        assert_eq!(score.version, REPUTATION_VERSION);
    }

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
        
        // Perfect scores should give 1.0
        assert!((breakdown.weighted_base_score() - 1.0).abs() < 0.001);
        assert!((breakdown.final_score() - 1.0).abs() < 0.001);
    }

    #[test]
    fn test_anti_gaming_sybil_detection() {
        let mut detector = AntiGamingDetector::new();
        let ip = "192.168.1.100";
        
        // Create multiple wallets on same IP
        let mut flags = Vec::new();
        for i in 0..5 {
            let wallet = WalletAddress::new(format!("RTC1Wallet{}", i));
            flags.extend(detector.record_ip(&wallet, ip));
        }
        
        // Should flag after exceeding threshold
        assert!(!flags.is_empty());
        assert!(flags.iter().any(|f| f.flag_type == RiskType::SybilCluster));
    }

    #[test]
    fn test_anti_gaming_hardware_sharing() {
        let mut detector = AntiGamingDetector::new();
        let hw_hash = "abc123def456";
        
        let wallet1 = WalletAddress::new("RTC1Miner1");
        let wallet2 = WalletAddress::new("RTC1Miner2");
        
        detector.record_hardware(&wallet1, hw_hash);
        let flags = detector.record_hardware(&wallet2, hw_hash);
        
        assert!(!flags.is_empty());
        assert!(flags.iter().any(|f| f.flag_type == RiskType::HardwareInconsistency));
    }

    #[test]
    fn test_reputation_manager_attestation() {
        let store = Box::new(InMemoryReputationStore::default());
        let mut manager = ReputationManager::new(store);
        
        let wallet = WalletAddress::new("RTC1TestMiner");
        
        // Process successful attestation
        let score = manager.process_attestation(
            &wallet,
            "192.168.1.1",
            "hw_hash_123",
            true,
        );
        
        assert!(score.score >= 0.5); // Should start neutral or better
        assert!(score.breakdown.uptime_score > 0.0);
    }

    #[test]
    fn test_reputation_decay() {
        let store = Box::new(InMemoryReputationStore::default());
        let mut manager = ReputationManager::new(store);
        
        let wallet = WalletAddress::new("RTC1TestMiner");
        
        // Initial attestation
        manager.process_attestation(&wallet, "192.168.1.1", "hw_hash_123", true);
        
        // Apply decay (simulates inactivity)
        manager.apply_decay();
        
        let score = manager.get_score(&wallet).unwrap();
        assert!(score.breakdown.decay_factor <= 1.0);
    }

    #[test]
    fn test_challenge_response() {
        let store = Box::new(InMemoryReputationStore::default());
        let mut manager = ReputationManager::new(store);
        
        let wallet = WalletAddress::new("RTC1TestMiner");
        
        // Successful challenge
        let score = manager.process_challenge(&wallet, 5.0, true);
        assert!(score.score >= 0.5);
        
        // Failed challenge
        let score = manager.process_challenge(&wallet, 10.0, false);
        assert!(score.risk_flags.iter().any(|f| f.flag_type == RiskType::ChallengeFailure));
    }

    #[test]
    fn test_top_wallets() {
        let store = Box::new(InMemoryReputationStore::default());
        let mut manager = ReputationManager::new(store);
        
        // Create multiple wallets with different scores
        for i in 0..5 {
            let wallet = WalletAddress::new(format!("RTC1Miner{}", i));
            manager.process_attestation(&wallet, &format!("192.168.1.{}", i), &format!("hw_{}", i), true);
        }
        
        let top = manager.get_top_wallets(3);
        assert_eq!(top.len(), 3);
    }

    #[test]
    fn test_score_history() {
        let mut history = ScoreHistory::new();
        let timestamp = current_timestamp();
        
        history.add_snapshot(timestamp, 0.5);
        history.add_snapshot(timestamp + 86400, 0.6);
        history.add_snapshot(timestamp + 2 * 86400, 0.7);
        
        assert!((history.avg_30d - 0.6).abs() < 0.01);
        assert!((history.trend_7d - 0.2).abs() < 0.01);
        assert!((history.peak_score - 0.7).abs() < 0.01);
    }

    #[test]
    fn test_fleet_correlation() {
        let mut detector = AntiGamingDetector::new();

        let ip = "10.0.0.1";
        let wallets: Vec<_> = (0..12)
            .map(|i| WalletAddress::new(format!("RTC1Bot{}", i)))
            .collect();

        for wallet in &wallets {
            detector.record_ip(wallet, ip);
        }

        let correlation = detector.calculate_fleet_correlation(&wallets[0]);
        assert!(correlation > FLEET_CORRELATION_THRESHOLD);
    }
}
