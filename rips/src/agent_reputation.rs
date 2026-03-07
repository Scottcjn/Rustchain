// RIP-006: Agent Reputation Score - Integrated with RustChain Data Flow
// ======================================================================
// Agent reputation scoring tied to actual RustChain interfaces:
// - Proof of Antiquity (mining attestations)
// - NFT Badges (achievement tracking)
// - Governance (voting participation)
//
// Status: IMPLEMENTED
// Author: Flamekeeper Scott
// Created: 2026-03-07
// Reworked: 2026-03-07 (aligned to real project data flow)

use std::collections::{HashMap, HashSet, VecDeque};
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use sha2::{Sha256, Digest};
use serde::{Serialize, Deserialize};

// Import from RIP-001 (core types)
use crate::core_types::{WalletAddress, TokenAmount};

// Import from RIP-004 (NFT Badges)
use crate::nft_badges::{BadgeType, BadgeTier as NFTBadgeTier};

// Mock Vote struct for when governance module is disabled
#[cfg(not(feature = "governance"))]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Vote {
    pub voter: WalletAddress,
    pub support: bool,
    pub weight: TokenAmount,
    pub timestamp: u64,
}

// Import from RIP-005 (Governance)
#[cfg(feature = "governance")]
use crate::governance::Vote;

// =============================================================================
// Constants
// =============================================================================

/// Reputation score version for schema tracking
pub const REPUTATION_VERSION: u32 = 1;

/// Minimum reputation score required for certain operations (e.g., governance proposals)
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

/// Reputation decay half-life in days
pub const REPUTATION_HALF_LIFE_DAYS: f64 = 14.0;

/// Weight for mining activity in reputation calculation (40%)
pub const MINING_WEIGHT: f64 = 0.40;

/// Weight for badge achievements (25%)
pub const BADGE_WEIGHT: f64 = 0.25;

/// Weight for governance participation (20%)
pub const GOVERNANCE_WEIGHT: f64 = 0.20;

/// Weight for hardware consistency (15%)
pub const HARDWARE_WEIGHT: f64 = 0.15;

// =============================================================================
// Data Structures
// =============================================================================

/// Agent reputation score with detailed breakdown tied to RustChain data
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReputationScore {
    /// Wallet address this score belongs to
    pub wallet: WalletAddress,
    
    /// Overall reputation score (0.0 - 1.0)
    pub score: f64,
    
    /// Detailed score breakdown tied to actual RustChain activities
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

/// Detailed breakdown of reputation components tied to RustChain data
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScoreBreakdown {
    /// Mining/attestation score from Proof of Antiquity (0.0 - 1.0) - 40% weight
    pub mining_score: f64,
    
    /// Badge achievement score from NFT system (0.0 - 1.0) - 25% weight
    pub badge_score: f64,
    
    /// Governance participation score (0.0 - 1.0) - 20% weight
    pub governance_score: f64,
    
    /// Hardware consistency score from PoA hardware tracking (0.0 - 1.0) - 15% weight
    pub hardware_score: f64,
    
    /// Anti-gaming penalty multiplier (0.0 - 1.0)
    pub anti_gaming_multiplier: f64,
    
    /// Time decay factor (0.0 - 1.0)
    pub decay_factor: f64,
}

impl ScoreBreakdown {
    /// Calculate weighted base score before penalties
    pub fn weighted_base_score(&self) -> f64 {
        self.mining_score * MINING_WEIGHT +
        self.badge_score * BADGE_WEIGHT +
        self.governance_score * GOVERNANCE_WEIGHT +
        self.hardware_score * HARDWARE_WEIGHT
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
        
        self.days_tracked = self.days_tracked.max(1);
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

impl Default for ScoreHistory {
    fn default() -> Self {
        Self::new()
    }
}

/// Risk flag types for anti-gaming
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum RiskType {
    /// Multiple wallets on same IP (Sybil cluster)
    SybilCluster,
    /// Same hardware claimed by multiple wallets
    HardwareInconsistency,
    /// Unusual attestation patterns
    AttestationAnomaly,
    /// Failed challenge response
    ChallengeFailure,
    /// Attempted score manipulation
    ScoreManipulation,
    /// Governance spam or abuse
    GovernanceAbuse,
    /// Badge farming detection
    BadgeFarming,
}

/// Risk flag on an agent's reputation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RiskFlag {
    /// Type of risk detected
    pub flag_type: RiskType,
    /// Severity (0.0 - 1.0)
    pub severity: f64,
    /// Human-readable description
    pub description: String,
    /// Whether the flag has been resolved
    pub resolved: bool,
    /// Timestamp when flag was raised
    pub raised_at: u64,
}

impl RiskFlag {
    pub fn new(flag_type: RiskType, severity: f64, description: String) -> Self {
        RiskFlag {
            flag_type,
            severity,
            description,
            resolved: false,
            raised_at: current_timestamp(),
        }
    }
}

/// Activity record tied to RustChain events
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ActivityRecord {
    /// Timestamp of activity
    pub timestamp: u64,
    /// Type of activity
    pub activity_type: ActivityType,
    /// Associated metadata
    pub metadata: ActivityMetadata,
    /// Outcome score (0.0 - 1.0)
    pub outcome: f64,
}

/// Types of activities tracked for reputation
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum ActivityType {
    /// Mining/attestation via Proof of Antiquity
    Mining,
    /// Badge earned via NFT system
    BadgeEarned,
    /// Vote cast in governance
    GovernanceVote,
    /// Proposal created
    ProposalCreated,
    /// Hardware registered
    HardwareRegistered,
}

/// Metadata for activity records
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ActivityMetadata {
    /// Hardware hash (for mining/hardware activities)
    pub hardware_hash: Option<String>,
    /// Badge type (for badge activities)
    pub badge_type: Option<String>,
    /// Proposal ID (for governance activities)
    pub proposal_id: Option<u64>,
    /// Block height (for mining activities)
    pub block_height: Option<u64>,
    /// Additional metadata
    pub extra: HashMap<String, String>,
}

/// Behavioral fingerprint for anti-gaming
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BehavioralFingerprint {
    /// Average time between attestations (seconds)
    pub avg_attestation_interval: f64,
    /// Active hours (0-23)
    pub active_hours: HashSet<u8>,
    /// Primary hardware hash
    pub primary_hardware: Option<String>,
    /// Total attestations
    pub total_attestations: u64,
    /// Total governance actions
    pub total_governance_actions: u64,
}

impl BehavioralFingerprint {
    pub fn new() -> Self {
        BehavioralFingerprint {
            avg_attestation_interval: 0.0,
            active_hours: HashSet::new(),
            primary_hardware: None,
            total_attestations: 0,
            total_governance_actions: 0,
        }
    }
}

impl Default for BehavioralFingerprint {
    fn default() -> Self {
        Self::new()
    }
}

/// Challenge record for anti-gaming
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChallengeRecord {
    /// Last challenge timestamp
    pub last_challenge: u64,
    /// Total challenges issued
    pub total_challenges: u64,
    /// Successful responses
    pub successful_responses: u64,
    /// Failed responses
    pub failed_responses: u64,
    /// Average response time (seconds)
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

impl Default for ChallengeRecord {
    fn default() -> Self {
        Self::new()
    }
}

// =============================================================================
// Anti-Gaming Detector
// =============================================================================

/// Detects and flags gaming behavior
pub struct AntiGamingDetector {
    /// IP address tracking: wallet -> set of IPs
    wallet_ip_map: HashMap<WalletAddress, HashSet<String>>,
    /// Reverse IP tracking: IP -> set of wallets
    ip_wallet_map: HashMap<String, HashSet<WalletAddress>>,
    /// Hardware sharing detection: hw_hash -> set of wallets
    hardware_wallet_map: HashMap<String, HashSet<WalletAddress>>,
    /// Attestation patterns: wallet -> timestamps
    attestation_patterns: HashMap<WalletAddress, VecDeque<u64>>,
    /// Behavioral fingerprints
    behavioral_fingerprints: HashMap<WalletAddress, BehavioralFingerprint>,
    /// Challenge tracker
    challenge_tracker: HashMap<WalletAddress, ChallengeRecord>,
}

impl AntiGamingDetector {
    pub fn new() -> Self {
        AntiGamingDetector {
            wallet_ip_map: HashMap::new(),
            ip_wallet_map: HashMap::new(),
            hardware_wallet_map: HashMap::new(),
            attestation_patterns: HashMap::new(),
            behavioral_fingerprints: HashMap::new(),
            challenge_tracker: HashMap::new(),
        }
    }
    
    /// Record IP for wallet, returns flags if suspicious
    pub fn record_ip(&mut self, wallet: &WalletAddress, ip: &str) -> Vec<RiskFlag> {
        let mut flags = Vec::new();
        
        let ip_set = self.wallet_ip_map.entry(wallet.clone()).or_insert_with(HashSet::new);
        
        // Check if too many IPs for this wallet
        if ip_set.len() >= MAX_IPS_PER_WALLET && !ip_set.contains(ip) {
            flags.push(RiskFlag::new(
                RiskType::SybilCluster,
                0.6,
                format!("Wallet using {} different IPs", ip_set.len() + 1),
            ));
        }
        
        ip_set.insert(ip.to_string());
        
        // Update reverse mapping
        let wallet_set = self.ip_wallet_map.entry(ip.to_string()).or_insert_with(HashSet::new);
        
        // Check if too many wallets on this IP
        if wallet_set.len() >= MAX_WALLETS_PER_IP as usize {
            flags.push(RiskFlag::new(
                RiskType::SybilCluster,
                0.8,
                format!("IP {} has {} wallets", ip, wallet_set.len() + 1),
            ));
        }
        
        wallet_set.insert(wallet.clone());
        
        flags
    }
    
    /// Record hardware usage, returns flags if shared
    pub fn record_hardware(&mut self, wallet: &WalletAddress, hw_hash: &str) -> Vec<RiskFlag> {
        let mut flags = Vec::new();
        
        let wallet_set = self.hardware_wallet_map.entry(hw_hash.to_string()).or_insert_with(HashSet::new);
        
        if !wallet_set.is_empty() && !wallet_set.contains(wallet) {
            flags.push(RiskFlag::new(
                RiskType::HardwareInconsistency,
                0.7,
                format!("Hardware {} shared by {} wallets", hw_hash, wallet_set.len() + 1),
            ));
        }
        
        wallet_set.insert(wallet.clone());
        
        flags
    }
    
    /// Record attestation, returns flags if anomalous
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
        record.avg_response_time = (record.avg_response_time * (record.successful_responses.saturating_sub(1)) as f64 + response_time)
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

impl Default for AntiGamingDetector {
    fn default() -> Self {
        Self::new()
    }
}

// =============================================================================
// Reputation Store
// =============================================================================

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

// =============================================================================
// Reputation Manager - Integrated with RustChain Data Flow
// =============================================================================

/// Reputation manager that integrates with actual RustChain data flows
pub struct ReputationManager {
    /// Reputation storage
    store: Box<dyn ReputationStore>,
    
    /// Anti-gaming detector
    anti_gaming: AntiGamingDetector,
    
    /// Activity log per wallet
    activity_log: HashMap<WalletAddress, VecDeque<ActivityRecord>>,
    
    /// Badge holdings per wallet (from NFT system)
    badge_holdings: HashMap<WalletAddress, HashSet<BadgeType>>,
    
    /// Governance participation per wallet
    governance_actions: HashMap<WalletAddress, Vec<Vote>>,
    
    /// Hardware registrations per wallet (from PoA)
    hardware_registrations: HashMap<WalletAddress, HashSet<String>>,
}

impl ReputationManager {
    pub fn new(store: Box<dyn ReputationStore>) -> Self {
        ReputationManager {
            store,
            anti_gaming: AntiGamingDetector::new(),
            activity_log: HashMap::new(),
            badge_holdings: HashMap::new(),
            governance_actions: HashMap::new(),
            hardware_registrations: HashMap::new(),
        }
    }
    
    /// Process mining event from Proof of Antiquity
    /// This is the PRIMARY reputation source (40% weight)
    pub fn process_mining_event(
        &mut self,
        wallet: &WalletAddress,
        ip: &str,
        hw_hash: &str,
        block_height: u64,
        _reward: TokenAmount,
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
        fingerprint.total_attestations += 1;
        if fingerprint.primary_hardware.is_none() {
            fingerprint.primary_hardware = Some(hw_hash.to_string());
        }
        
        // Track hardware registration
        self.hardware_registrations
            .entry(wallet.clone())
            .or_insert_with(HashSet::new)
            .insert(hw_hash.to_string());
        
        // Record activity
        self.record_activity(wallet, ActivityRecord {
            timestamp,
            activity_type: ActivityType::Mining,
            metadata: ActivityMetadata {
                hardware_hash: Some(hw_hash.to_string()),
                badge_type: None,
                proposal_id: None,
                block_height: Some(block_height),
                extra: HashMap::new(),
            },
            outcome: 1.0,
        });
        
        // Calculate new score
        let score = self.calculate_score(wallet, flags);
        self.store.update_score(score.clone());
        
        score
    }
    
    /// Process badge earned from NFT system
    /// This contributes to badge_score (25% weight)
    pub fn process_badge_earned(
        &mut self,
        wallet: &WalletAddress,
        badge_type: BadgeType,
        badge_tier: NFTBadgeTier,
    ) -> ReputationScore {
        let timestamp = current_timestamp();
        
        // Track badge holdings
        self.badge_holdings
            .entry(wallet.clone())
            .or_insert_with(HashSet::new)
            .insert(badge_type.clone());
        
        // Record activity
        self.record_activity(wallet, ActivityRecord {
            timestamp,
            activity_type: ActivityType::BadgeEarned,
            metadata: ActivityMetadata {
                hardware_hash: None,
                badge_type: Some(format!("{:?}:{:?}", badge_type, badge_tier)),
                proposal_id: None,
                block_height: None,
                extra: HashMap::new(),
            },
            outcome: Self::badge_tier_score(badge_tier),
        });
        
        let score = self.calculate_score(wallet, Vec::new());
        self.store.update_score(score.clone());
        
        score
    }
    
    /// Process governance vote
    /// This contributes to governance_score (20% weight)
    pub fn process_governance_vote(
        &mut self,
        wallet: &WalletAddress,
        vote: Vote,
        proposal_id: u64,
    ) -> ReputationScore {
        let timestamp = current_timestamp();
        
        // Track governance actions
        self.governance_actions
            .entry(wallet.clone())
            .or_insert_with(Vec::new)
            .push(vote.clone());
        
        // Record activity
        self.record_activity(wallet, ActivityRecord {
            timestamp,
            activity_type: ActivityType::GovernanceVote,
            metadata: ActivityMetadata {
                hardware_hash: None,
                badge_type: None,
                proposal_id: Some(proposal_id),
                block_height: None,
                extra: HashMap::new(),
            },
            outcome: 1.0,
        });
        
        let score = self.calculate_score(wallet, Vec::new());
        self.store.update_score(score.clone());
        
        score
    }
    
    /// Process proposal creation
    pub fn process_proposal_created(
        &mut self,
        wallet: &WalletAddress,
        proposal_id: u64,
    ) -> ReputationScore {
        let timestamp = current_timestamp();
        
        // Record activity
        self.record_activity(wallet, ActivityRecord {
            timestamp,
            activity_type: ActivityType::ProposalCreated,
            metadata: ActivityMetadata {
                hardware_hash: None,
                badge_type: None,
                proposal_id: Some(proposal_id),
                block_height: None,
                extra: HashMap::new(),
            },
            outcome: 1.0,
        });
        
        let score = self.calculate_score(wallet, Vec::new());
        self.store.update_score(score.clone());
        
        score
    }
    
    /// Process challenge response
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
            activity_type: ActivityType::Mining, // Treat as mining-related
            metadata: ActivityMetadata {
                hardware_hash: None,
                badge_type: None,
                proposal_id: None,
                block_height: None,
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
                    mining_score: 0.5,
                    badge_score: 0.5,
                    governance_score: 0.5,
                    hardware_score: 0.5,
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
        
        let mining_score = self.calculate_mining_score(activity);
        let badge_score = self.calculate_badge_score(wallet);
        let governance_score = self.calculate_governance_score(wallet);
        let hardware_score = self.calculate_hardware_score(wallet);
        
        // Calculate anti-gaming multiplier
        let anti_gaming_multiplier = self.anti_gaming.calculate_multiplier(wallet, &flags);
        
        // Calculate decay factor
        let decay_factor = base_score.breakdown.decay_factor;
        
        let breakdown = ScoreBreakdown {
            mining_score,
            badge_score,
            governance_score,
            hardware_score,
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
    
    fn calculate_mining_score(&self, activity: Option<&VecDeque<ActivityRecord>>) -> f64 {
        let Some(log) = activity else { return 0.5 };
        
        if log.is_empty() {
            return 0.5;
        }
        
        let timestamp = current_timestamp();
        let window_start = timestamp.saturating_sub(ACTIVITY_WINDOW_DAYS * 86400);
        
        let mining_activities: Vec<_> = log
            .iter()
            .filter(|r| r.activity_type == ActivityType::Mining && r.timestamp >= window_start)
            .collect();
        
        if mining_activities.is_empty() {
            return 0.3;
        }
        
        // Score based on regularity and recency
        let last_mining = mining_activities.iter().map(|r| r.timestamp).max().unwrap_or(0);
        let recency_score = (1.0 - (timestamp - last_mining) as f64 / (7 * 86400) as f64).max(0.0);
        
        // Expected ~2 attestations per day
        let expected = ACTIVITY_WINDOW_DAYS * 2;
        let actual = mining_activities.len() as u64;
        let frequency_score = (actual as f64 / expected as f64).min(1.0);
        
        // Success rate
        let success_rate: f64 = mining_activities.iter().map(|r| r.outcome).sum();
        let success_rate = success_rate / mining_activities.len() as f64;
        
        recency_score * 0.4 + frequency_score * 0.3 + success_rate * 0.3
    }
    
    fn calculate_badge_score(&self, wallet: &WalletAddress) -> f64 {
        let badges = self.badge_holdings.get(wallet);
        
        let Some(badges) = badges else { return 0.5 };
        
        if badges.is_empty() {
            return 0.5;
        }
        
        // Score based on badge diversity and tier
        let mut score = 0.0;
        for badge in badges {
            score += Self::badge_type_score(badge.clone());
        }
        
        // Normalize: 10+ diverse badges = max score
        (score / badges.len() as f64).min(1.0)
    }
    
    fn badge_type_score(badge_type: BadgeType) -> f64 {
        match badge_type {
            // Legendary badges
            BadgeType::GenesisMiner | BadgeType::FirstBlock | BadgeType::Flamekeeper => 1.0,
            // Epic badges
            BadgeType::AncientSiliconKeeper | BadgeType::BlockLegion | BadgeType::YearOfAntiquity => 0.9,
            // Rare badges
            BadgeType::SacredSiliconGuardian | BadgeType::BlockCenturion | BadgeType::RTCMillionaire => 0.8,
            // Uncommon badges
            BadgeType::VintageCollector | BadgeType::DedicationMedal | BadgeType::CommunityBuilder => 0.7,
            // Common badges
            _ => 0.6,
        }
    }
    
    fn badge_tier_score(tier: NFTBadgeTier) -> f64 {
        match tier {
            NFTBadgeTier::Legendary => 1.0,
            NFTBadgeTier::Epic => 0.9,
            NFTBadgeTier::Rare => 0.8,
            NFTBadgeTier::Uncommon => 0.7,
            NFTBadgeTier::Common => 0.6,
        }
    }
    
    fn calculate_governance_score(&self, wallet: &WalletAddress) -> f64 {
        let actions = self.governance_actions.get(wallet);

        let Some(actions) = actions else { return 0.5 };

        if actions.is_empty() {
            return 0.5;
        }

        // Score based on participation (1 vote = 0.5, 5+ votes = 1.0)
        let participation_score = (actions.len() as f64 / 5.0).min(1.0);

        // Bonus for diverse participation (voting on multiple proposals)
        let unique_proposals: HashSet<_> = actions.iter().map(|v| v.timestamp).collect();
        let diversity_bonus = (unique_proposals.len() as f64 / 3.0).min(0.2);

        (participation_score * 0.8 + diversity_bonus + 0.2).min(1.0)
    }
    
    fn calculate_hardware_score(&self, wallet: &WalletAddress) -> f64 {
        let hardware = self.hardware_registrations.get(wallet);
        
        let Some(hardware) = hardware else { return 0.5 };
        
        if hardware.is_empty() {
            return 0.5;
        }
        
        // Single consistent hardware = best score
        if hardware.len() == 1 {
            1.0
        } else if hardware.len() <= 3 {
            0.7
        } else {
            0.4
        }
    }
}

impl Default for ReputationManager {
    fn default() -> Self {
        Self::new(Box::new(InMemoryReputationStore::default()))
    }
}

/// Helper to get current Unix timestamp
fn current_timestamp() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or(Duration::ZERO)
        .as_secs()
}

// =============================================================================
// Tests
// =============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_reputation_score_creation() {
        let wallet = WalletAddress::new("RTC1TestAgent123");
        let breakdown = ScoreBreakdown {
            mining_score: 0.8,
            badge_score: 0.9,
            governance_score: 0.7,
            hardware_score: 1.0,
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
            mining_score: 1.0,
            badge_score: 1.0,
            governance_score: 1.0,
            hardware_score: 1.0,
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
    fn test_reputation_manager_mining_event() {
        let store = Box::new(InMemoryReputationStore::default());
        let mut manager = ReputationManager::new(store);
        
        let wallet = WalletAddress::new("RTC1TestMiner");
        
        // Process mining event
        let score = manager.process_mining_event(
            &wallet,
            "192.168.1.1",
            "hw_hash_123",
            1000,
            TokenAmount(100_000_000),
        );
        
        assert!(score.score >= 0.5); // Should start neutral or better
        assert!(score.breakdown.mining_score > 0.0);
    }

    #[test]
    fn test_reputation_manager_badge_earned() {
        let store = Box::new(InMemoryReputationStore::default());
        let mut manager = ReputationManager::new(store);
        
        let wallet = WalletAddress::new("RTC1BadgeMiner");
        
        // Process badge earned
        let score = manager.process_badge_earned(
            &wallet,
            BadgeType::GenesisMiner,
            NFTBadgeTier::Legendary,
        );
        
        assert!(score.breakdown.badge_score >= 0.6);
    }

    #[test]
    fn test_reputation_manager_governance_vote() {
        let store = Box::new(InMemoryReputationStore::default());
        let mut manager = ReputationManager::new(store);
        
        let wallet = WalletAddress::new("RTC1Voter");
        
        // Create a mock vote
        let vote = Vote {
            voter: wallet.clone(),
            support: true,
            weight: TokenAmount(1000),
            timestamp: current_timestamp(),
        };
        
        // Process governance vote
        let score = manager.process_governance_vote(&wallet, vote, 1);
        
        assert!(score.breakdown.governance_score >= 0.5);
    }

    #[test]
    fn test_reputation_decay() {
        let store = Box::new(InMemoryReputationStore::default());
        let mut manager = ReputationManager::new(store);
        
        let wallet = WalletAddress::new("RTC1TestMiner");
        
        // Initial mining event
        manager.process_mining_event(&wallet, "192.168.1.1", "hw_hash_123", 1000, TokenAmount(100_000_000));
        
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
        
        // Create multiple wallets with different activities
        for i in 0..5 {
            let wallet = WalletAddress::new(format!("RTC1Miner{}", i));
            manager.process_mining_event(&wallet, &format!("192.168.1.{}", i), &format!("hw_{}", i), 1000 + i as u64, TokenAmount(100_000_000));
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
    
    #[test]
    fn test_integrated_reputation_flow() {
        let store = Box::new(InMemoryReputationStore::default());
        let mut manager = ReputationManager::new(store);
        
        let wallet = WalletAddress::new("RTC1IntegratedMiner");
        
        // 1. Start with mining
        manager.process_mining_event(&wallet, "192.168.1.1", "hw_main", 1000, TokenAmount(100_000_000));
        let score1 = manager.get_score(&wallet).unwrap();
        
        // 2. Earn a badge
        manager.process_badge_earned(&wallet, BadgeType::BlockCenturion, NFTBadgeTier::Rare);
        let score2 = manager.get_score(&wallet).unwrap();
        
        // 3. Participate in governance
        let vote = Vote {
            voter: wallet.clone(),
            support: true,
            weight: TokenAmount(1000),
            timestamp: current_timestamp(),
        };
        manager.process_governance_vote(&wallet, vote, 1);
        let score3 = manager.get_score(&wallet).unwrap();
        
        // Scores should improve with diverse activity
        assert!(score3.score >= score1.score);
        assert!(score3.breakdown.governance_score > 0.5);
    }
}
