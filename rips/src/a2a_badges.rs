// RIP-004 Extension: A2A Transaction Badge System
// ================================================
// Agent-to-Agent transaction badges for RustChain
// Status: IMPLEMENTED
// Author: Bounty #693 Implementation
// Created: 2026-03-07

use std::collections::{HashMap, HashSet};
use sha2::{Sha256, Digest};
use serde::{Serialize, Deserialize};
use chrono::{DateTime, Utc};

// Import from core NFT badges
use crate::nft_badges::{BadgeTier, BadgeId, BadgeMetadata};

/// A2A Transaction types
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum A2ATransactionType {
    /// Standard x402 payment
    X402Payment,
    /// Service request payment
    ServiceRequest,
    /// Data exchange payment
    DataExchange,
    /// Skill/API call payment
    SkillCall,
    /// Other protocol
    Other(String),
}

/// A2A Transaction record
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct A2ATransaction {
    /// Unique transaction hash
    pub tx_hash: String,
    /// Sender wallet address
    pub from_wallet: String,
    /// Receiver wallet address
    pub to_wallet: String,
    /// Transaction amount in RTC
    pub amount: f64,
    /// Transaction timestamp
    pub timestamp: u64,
    /// Protocol used (x402, etc.)
    pub protocol: String,
    /// Block height
    pub block_height: u64,
    /// Transaction type
    pub tx_type: A2ATransactionType,
    /// Verified status
    pub verified: bool,
}

/// Wallet statistics for A2A activity
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct WalletA2AStats {
    /// Wallet address
    pub wallet: String,
    /// Total A2A transactions
    pub total_transactions: u64,
    /// Total volume in RTC
    pub total_volume: f64,
    /// Unique counterparties transacted with
    pub unique_counterparties: u64,
    /// Set of counterparty addresses
    pub counterparties: HashSet<String>,
    /// First transaction timestamp
    pub first_transaction: Option<u64>,
    /// Last transaction timestamp
    pub last_transaction: Option<u64>,
    /// Protocols used
    pub protocols_used: HashSet<String>,
    /// Monthly volume tracking (YYYY-MM -> volume)
    pub monthly_volume: HashMap<String, f64>,
    /// Is this wallet an agent (vs human)
    pub is_agent: bool,
}

impl WalletA2AStats {
    /// Create new wallet stats
    pub fn new(wallet: String) -> Self {
        WalletA2AStats {
            wallet,
            ..Default::default()
        }
    }
    
    /// Update stats with a new transaction
    pub fn update_with_transaction(&mut self, tx: &A2ATransaction, is_sender: bool) {
        self.total_transactions += 1;
        self.total_volume += tx.amount;
        
        // Track counterparty
        let counterparty = if is_sender {
            tx.to_wallet.clone()
        } else {
            tx.from_wallet.clone()
        };
        
        if !self.counterparties.contains(&counterparty) {
            self.counterparties.insert(counterparty);
            self.unique_counterparties = self.counterparties.len() as u64;
        }
        
        // Track timestamps
        if self.first_transaction.is_none() || Some(tx.timestamp) < self.first_transaction {
            self.first_transaction = Some(tx.timestamp);
        }
        if self.last_transaction.is_none() || Some(tx.timestamp) > self.last_transaction {
            self.last_transaction = Some(tx.timestamp);
        }
        
        // Track protocols
        self.protocols_used.insert(tx.protocol.clone());
        
        // Track monthly volume
        let datetime = DateTime::from_timestamp(tx.timestamp as i64, 0)
            .unwrap_or_else(|| DateTime::from_timestamp(0, 0).unwrap());
        let month_key = datetime.format("%Y-%m").to_string();
        
        *self.monthly_volume.entry(month_key).or_insert(0.0) += tx.amount;
    }
}

/// A2A Badge types
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum A2ABadgeType {
    // === Transaction Volume Badges ===
    /// First 100 A2A transactions
    A2APioneer,
    /// 100+ A2A transactions
    A2ATrader,
    /// 1,000+ A2A transactions
    A2AMerchant,
    /// 10,000+ A2A transactions
    A2AWhale,
    
    // === Network Badges ===
    /// Transacted with 10+ unique agents
    A2AConnector,
    /// Transacted with 100+ unique agents
    A2AHub,
    
    // === Protocol Badges ===
    /// Exclusively uses x402 protocol
    X402Native,
    /// Uses 3+ different protocols
    MultiProtocol,
    
    // === Genesis Badges ===
    /// First A2A transaction on network
    FirstA2APayment,
    
    // === Leaderboard Badges ===
    /// Highest monthly volume
    A2AVolumeKing,
}

impl A2ABadgeType {
    /// Get badge name for display
    pub fn name(&self) -> &'static str {
        match self {
            A2ABadgeType::A2APioneer => "A2A Pioneer",
            A2ABadgeType::A2ATrader => "A2A Trader",
            A2ABadgeType::A2AMerchant => "A2A Merchant",
            A2ABadgeType::A2AWhale => "A2A Whale",
            A2ABadgeType::A2AConnector => "A2A Connector",
            A2ABadgeType::A2AHub => "A2A Hub",
            A2ABadgeType::X402Native => "x402 Native",
            A2ABadgeType::MultiProtocol => "Multi-Protocol Agent",
            A2ABadgeType::FirstA2APayment => "First A2A Payment",
            A2ABadgeType::A2AVolumeKing => "A2A Volume King",
        }
    }
    
    /// Get badge description
    pub fn description(&self) -> &'static str {
        match self {
            A2ABadgeType::A2APioneer => "Among the first 100 to complete A2A transactions",
            A2ABadgeType::A2ATrader => "Completed 100+ A2A transactions",
            A2ABadgeType::A2AMerchant => "Completed 1,000+ A2A transactions",
            A2ABadgeType::A2AWhale => "Completed 10,000+ A2A transactions",
            A2ABadgeType::A2AConnector => "Transacted with 10+ unique agents",
            A2ABadgeType::A2AHub => "Transacted with 100+ unique agents",
            A2ABadgeType::X402Native => "Exclusively uses x402 protocol",
            A2ABadgeType::MultiProtocol => "Uses 3+ different payment protocols",
            A2ABadgeType::FirstA2APayment => "Participated in first network A2A transaction",
            A2ABadgeType::A2AVolumeKing => "Highest monthly A2A volume",
        }
    }
    
    /// Get badge tier
    pub fn tier(&self) -> BadgeTier {
        match self {
            A2ABadgeType::A2APioneer => BadgeTier::Legendary,
            A2ABadgeType::A2ATrader => BadgeTier::Epic,
            A2ABadgeType::A2AMerchant => BadgeTier::Epic,
            A2ABadgeType::A2AWhale => BadgeTier::Legendary,
            A2ABadgeType::A2AConnector => BadgeTier::Rare,
            A2ABadgeType::A2AHub => BadgeTier::Legendary,
            A2ABadgeType::X402Native => BadgeTier::Rare,
            A2ABadgeType::MultiProtocol => BadgeTier::Uncommon,
            A2ABadgeType::FirstA2APayment => BadgeTier::Mythic,
            A2ABadgeType::A2AVolumeKing => BadgeTier::Legendary,
        }
    }
    
    /// Get emoji icon
    pub fn icon(&self) -> &'static str {
        match self {
            A2ABadgeType::A2APioneer => "🤖💸🏆",
            A2ABadgeType::A2ATrader => "🤖💱📊",
            A2ABadgeType::A2AMerchant => "🤖🏪💎",
            A2ABadgeType::A2AWhale => "🤖🐋💰",
            A2ABadgeType::A2AConnector => "🤖🔗🌐",
            A2ABadgeType::A2AHub => "🤖🕸️👑",
            A2ABadgeType::X402Native => "🤖⚡402",
            A2ABadgeType::MultiProtocol => "🤖🔄🔀",
            A2ABadgeType::FirstA2APayment => "🤖1️⃣🎯",
            A2ABadgeType::A2AVolumeKing => "🤖👑📈",
        }
    }
    
    /// Get NFT ID
    pub fn nft_id(&self) -> String {
        match self {
            A2ABadgeType::A2APioneer => "badge_a2a_pioneer".to_string(),
            A2ABadgeType::A2ATrader => "badge_a2a_trader".to_string(),
            A2ABadgeType::A2AMerchant => "badge_a2a_merchant".to_string(),
            A2ABadgeType::A2AWhale => "badge_a2a_whale".to_string(),
            A2ABadgeType::A2AConnector => "badge_a2a_connector".to_string(),
            A2ABadgeType::A2AHub => "badge_a2a_hub".to_string(),
            A2ABadgeType::X402Native => "badge_x402_native".to_string(),
            A2ABadgeType::MultiProtocol => "badge_multi_protocol".to_string(),
            A2ABadgeType::FirstA2APayment => "badge_first_a2a_payment".to_string(),
            A2ABadgeType::A2AVolumeKing => "badge_a2a_volume_king".to_string(),
        }
    }
}

/// A2A Badge criteria checker
#[derive(Debug)]
pub struct A2ABadgeCriteriaChecker {
    /// Genesis block cutoff for pioneer badge
    pub pioneer_cutoff_block: u64,
    /// First A2A transaction block
    pub first_a2a_block: Option<u64>,
}

impl A2ABadgeCriteriaChecker {
    /// Create new criteria checker
    pub fn new() -> Self {
        A2ABadgeCriteriaChecker {
            pioneer_cutoff_block: 1000,
            first_a2a_block: None,
        }
    }
    
    /// Check all badges a wallet qualifies for
    pub fn check_all_badges(&self, stats: &WalletA2AStats) -> Vec<A2ABadgeType> {
        let mut earned = Vec::new();
        
        // Transaction volume badges
        if stats.total_transactions >= 10000 {
            earned.push(A2ABadgeType::A2AWhale);
        } else if stats.total_transactions >= 1000 {
            earned.push(A2ABadgeType::A2AMerchant);
        } else if stats.total_transactions >= 100 {
            earned.push(A2ABadgeType::A2ATrader);
        }
        
        // Pioneer badge (early adopter)
        if let Some(first_tx) = stats.first_transaction {
            // Convert timestamp to approximate block height
            // Assuming ~1 block per minute from epoch
            let approx_block = first_tx / 60;
            if approx_block < self.pioneer_cutoff_block && stats.total_transactions >= 10 {
                earned.push(A2ABadgeType::A2APioneer);
            }
        }
        
        // Network badges
        if stats.unique_counterparties >= 100 {
            earned.push(A2ABadgeType::A2AHub);
        } else if stats.unique_counterparties >= 10 {
            earned.push(A2ABadgeType::A2AConnector);
        }
        
        // Protocol badges
        if stats.protocols_used.len() >= 3 {
            earned.push(A2ABadgeType::MultiProtocol);
        }
        
        if stats.protocols_used.len() == 1 && stats.protocols_used.contains("x402") {
            if stats.total_transactions >= 50 {
                earned.push(A2ABadgeType::X402Native);
            }
        }
        
        // First A2A payment (special case)
        if let Some(first_block) = self.first_a2a_block {
            if let Some(first_tx) = stats.first_transaction {
                let approx_block = first_tx / 60;
                if approx_block == first_block {
                    earned.push(A2ABadgeType::FirstA2APayment);
                }
            }
        }
        
        earned
    }
    
    /// Get progress toward a specific badge
    pub fn get_progress(&self, stats: &WalletA2AStats, badge: &A2ABadgeType) -> (u64, u64) {
        match badge {
            A2ABadgeType::A2APioneer => {
                let current = if stats.total_transactions >= 10 { 10 } else { stats.total_transactions };
                (current, 10)
            },
            A2ABadgeType::A2ATrader => (stats.total_transactions, 100),
            A2ABadgeType::A2AMerchant => (stats.total_transactions, 1000),
            A2ABadgeType::A2AWhale => (stats.total_transactions, 10000),
            A2ABadgeType::A2AConnector => (stats.unique_counterparties, 10),
            A2ABadgeType::A2AHub => (stats.unique_counterparties, 100),
            A2ABadgeType::X402Native => {
                if stats.protocols_used.len() == 1 && stats.protocols_used.contains("x402") {
                    (stats.total_transactions, 50)
                } else {
                    (0, 50)
                }
            },
            A2ABadgeType::MultiProtocol => (stats.protocols_used.len() as u64, 3),
            A2ABadgeType::FirstA2APayment => {
                if stats.total_transactions > 0 { (1, 1) } else { (0, 1) }
            },
            A2ABadgeType::A2AVolumeKing => {
                // Would need network-wide comparison
                (0, 1)
            },
        }
    }
}

/// A2A Badge minter
#[derive(Debug)]
pub struct A2ABadgeMinter {
    /// Already minted badges (wallet, badge_type) -> badge_id
    minted_badges: HashMap<(String, A2ABadgeType), BadgeId>,
    /// Criteria checker
    checker: A2ABadgeCriteriaChecker,
    /// Wallet statistics tracker
    wallet_stats: HashMap<String, WalletA2AStats>,
}

impl A2ABadgeMinter {
    /// Create new badge minter
    pub fn new() -> Self {
        A2ABadgeMinter {
            minted_badges: HashMap::new(),
            checker: A2ABadgeCriteriaChecker::new(),
            wallet_stats: HashMap::new(),
        }
    }
    
    /// Record an A2A transaction
    pub fn record_transaction(&mut self, tx: A2ATransaction) {
        // Update sender stats
        self.wallet_stats
            .entry(tx.from_wallet.clone())
            .or_insert_with(|| WalletA2AStats::new(tx.from_wallet.clone()))
            .update_with_transaction(&tx, true);
        
        // Update receiver stats
        self.wallet_stats
            .entry(tx.to_wallet.clone())
            .or_insert_with(|| WalletA2AStats::new(tx.to_wallet.clone()))
            .update_with_transaction(&tx, false);
        
        // Track first A2A transaction
        if self.checker.first_a2a_block.is_none() {
            self.checker.first_a2a_block = Some(tx.block_height);
        }
    }
    
    /// Check and mint all eligible badges for a wallet
    pub fn check_and_mint(
        &mut self,
        wallet: &str,
        current_block: u64,
        timestamp: u64,
    ) -> Vec<A2ABadge> {
        let stats = match self.wallet_stats.get(wallet) {
            Some(s) => s,
            None => return Vec::new(),
        };
        
        let eligible = self.checker.check_all_badges(stats);
        let mut minted = Vec::new();
        
        for badge_type in eligible {
            match self.mint_badge(badge_type, wallet.to_string(), current_block, timestamp) {
                Ok(badge) => minted.push(badge),
                Err(MintError::AlreadyMinted(_)) => continue,
            }
        }
        
        minted
    }
    
    /// Mint a specific badge
    pub fn mint_badge(
        &mut self,
        badge_type: A2ABadgeType,
        owner: String,
        block: u64,
        timestamp: u64,
    ) -> Result<A2ABadge, MintError> {
        // Check if already minted
        let key = (owner.clone(), badge_type.clone());
        if let Some(existing_id) = self.minted_badges.get(&key) {
            return Err(MintError::AlreadyMinted(existing_id.clone()));
        }
        
        // Generate badge ID
        let id = BadgeId::generate_a2a(&badge_type, &owner, block);
        
        // Generate badge hash
        let badge_data = format!("{}:{}:{:?}:{}", id.0, owner, badge_type, block);
        let mut hasher = Sha256::new();
        hasher.update(badge_data.as_bytes());
        let badge_hash: [u8; 32] = hasher.finalize().into();
        
        let badge = A2ABadge {
            id,
            badge_type: badge_type.clone(),
            owner: owner.clone(),
            earned_block: block,
            earned_timestamp: timestamp,
            badge_hash,
            ipfs_hash: None,
            metadata: BadgeMetadata {
                hardware_model: None,
                hardware_age: None,
                achievement_data: HashMap::new(),
                svg_data: None,
            },
        };
        
        // Record as minted
        self.minted_badges.insert(key, BadgeId::new(badge.id.0.clone()));
        
        Ok(badge)
    }
    
    /// Get wallet statistics
    pub fn get_wallet_stats(&self, wallet: &str) -> Option<&WalletA2AStats> {
        self.wallet_stats.get(wallet)
    }
    
    /// Get progress toward a badge
    pub fn get_badge_progress(&self, wallet: &str, badge_type: &A2ABadgeType) -> Option<(u64, u64)> {
        self.wallet_stats.get(wallet).map(|stats| {
            self.checker.get_progress(stats, badge_type)
        })
    }
}

/// A2A Badge NFT
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct A2ABadge {
    /// Unique badge ID
    pub id: BadgeId,
    /// Badge type
    pub badge_type: A2ABadgeType,
    /// Owner wallet
    pub owner: String,
    /// Block when earned
    pub earned_block: u64,
    /// Timestamp when earned
    pub earned_timestamp: u64,
    /// On-chain hash
    pub badge_hash: [u8; 32],
    /// IPFS hash for metadata
    pub ipfs_hash: Option<String>,
    /// Additional metadata
    pub metadata: BadgeMetadata,
}

/// Minting errors
#[derive(Debug)]
pub enum MintError {
    AlreadyMinted(BadgeId),
    InvalidCriteria(String),
}

/// x402 Header validator
pub struct X402Validator;

impl X402Validator {
    /// Validate x402 payment headers
    pub fn validate_headers(headers: &HashMap<String, String>) -> Result<(), String> {
        let required = [
            "X-Payment-Amount",
            "X-Payment-From",
            "X-Payment-To",
            "X-Payment-TxHash",
        ];
        
        for header in required {
            if !headers.contains_key(header) {
                return Err(format!("Missing required header: {}", header));
            }
        }
        
        // Validate wallet addresses (Base/Ethereum format)
        let from_addr = headers.get("X-Payment-From").unwrap();
        let to_addr = headers.get("X-Payment-To").unwrap();
        
        if !Self::is_valid_address(from_addr) {
            return Err("Invalid X-Payment-From address".to_string());
        }
        
        if !Self::is_valid_address(to_addr) {
            return Err("Invalid X-Payment-To address".to_string());
        }
        
        // Validate amount
        let amount = headers.get("X-Payment-Amount").unwrap();
        if amount.parse::<f64>().map_or(true, |a| a <= 0.0) {
            return Err("Invalid payment amount".to_string());
        }
        
        // Validate tx hash
        let tx_hash = headers.get("X-Payment-TxHash").unwrap();
        if !Self::is_valid_tx_hash(tx_hash) {
            return Err("Invalid transaction hash".to_string());
        }
        
        Ok(())
    }
    
    fn is_valid_address(addr: &str) -> bool {
        if !addr.starts_with("0x") || addr.len() != 42 {
            return false;
        }
        addr[2..].chars().all(|c| c.is_ascii_hexdigit())
    }
    
    fn is_valid_tx_hash(hash: &str) -> bool {
        if !hash.starts_with("0x") || hash.len() != 66 {
            return false;
        }
        hash[2..].chars().all(|c| c.is_ascii_hexdigit())
    }
    
    /// Parse transaction from headers
    pub fn parse_transaction(
        headers: &HashMap<String, String>,
        block_height: u64,
        timestamp: u64,
    ) -> Result<A2ATransaction, String> {
        Self::validate_headers(headers)?;
        
        let amount = headers
            .get("X-Payment-Amount")
            .unwrap()
            .parse::<f64>()
            .map_err(|_| "Failed to parse amount")?;
        
        Ok(A2ATransaction {
            tx_hash: headers.get("X-Payment-TxHash").unwrap().clone(),
            from_wallet: headers.get("X-Payment-From").unwrap().clone(),
            to_wallet: headers.get("X-Payment-To").unwrap().clone(),
            amount,
            timestamp,
            protocol: "x402".to_string(),
            block_height,
            tx_type: A2ATransactionType::X402Payment,
            verified: true,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_badge_tier_colors() {
        assert_eq!(A2ABadgeType::A2APioneer.tier(), BadgeTier::Legendary);
        assert_eq!(A2ABadgeType::A2ATrader.tier(), BadgeTier::Epic);
        assert_eq!(A2ABadgeType::A2AConnector.tier(), BadgeTier::Rare);
    }
    
    #[test]
    fn test_wallet_stats_update() {
        let mut stats = WalletA2AStats::new("0x1234567890abcdef1234567890abcdef12345678".to_string());
        
        let tx = A2ATransaction {
            tx_hash: "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890".to_string(),
            from_wallet: "0x1234567890abcdef1234567890abcdef12345678".to_string(),
            to_wallet: "0x9876543210fedcba9876543210fedcba98765432".to_string(),
            amount: 100.0,
            timestamp: 1700000000,
            protocol: "x402".to_string(),
            block_height: 1000,
            tx_type: A2ATransactionType::X402Payment,
            verified: true,
        };
        
        stats.update_with_transaction(&tx, true);
        
        assert_eq!(stats.total_transactions, 1);
        assert_eq!(stats.total_volume, 100.0);
        assert_eq!(stats.unique_counterparties, 1);
        assert!(stats.protocols_used.contains("x402"));
    }
    
    #[test]
    fn test_criteria_checker() {
        let checker = A2ABadgeCriteriaChecker::new();
        
        let mut stats = WalletA2AStats::new("0x1234567890abcdef1234567890abcdef12345678".to_string());
        stats.total_transactions = 150;
        stats.unique_counterparties = 15;
        stats.protocols_used.insert("x402".to_string());
        
        let badges = checker.check_all_badges(&stats);
        
        assert!(badges.contains(&A2ABadgeType::A2ATrader));
        assert!(badges.contains(&A2ABadgeType::A2AConnector));
    }
    
    #[test]
    fn test_x402_validation() {
        let mut headers = HashMap::new();
        headers.insert("X-Payment-Amount".to_string(), "100.5".to_string());
        headers.insert("X-Payment-From".to_string(), "0x1234567890abcdef1234567890abcdef12345678".to_string());
        headers.insert("X-Payment-To".to_string(), "0x9876543210fedcba9876543210fedcba98765432".to_string());
        headers.insert("X-Payment-TxHash".to_string(), "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890".to_string());
        
        assert!(X402Validator::validate_headers(&headers).is_ok());
        
        // Test missing header
        headers.remove("X-Payment-Amount");
        assert!(X402Validator::validate_headers(&headers).is_err());
    }
    
    #[test]
    fn test_badge_minting() {
        let mut minter = A2ABadgeMinter::new();
        
        // Record some transactions
        let tx = A2ATransaction {
            tx_hash: "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890".to_string(),
            from_wallet: "0x1234567890abcdef1234567890abcdef12345678".to_string(),
            to_wallet: "0x9876543210fedcba9876543210fedcba98765432".to_string(),
            amount: 100.0,
            timestamp: 1700000000,
            protocol: "x402".to_string(),
            block_height: 100,
            tx_type: A2ATransactionType::X402Payment,
            verified: true,
        };
        
        minter.record_transaction(tx);
        
        // Check and mint badges
        let badges = minter.check_and_mint("0x1234567890abcdef1234567890abcdef12345678", 100, 1700000000);
        
        // Should have pioneer badge (early block + 1+ transactions, need 10)
        // For this test, we need more transactions
        assert!(badges.is_empty()); // Need 10 transactions for pioneer
    }
}
