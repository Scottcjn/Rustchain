// RIP-001: RustChain Core Types
// ================================
// Defines the fundamental types for RustChain blockchain
// Status: DRAFT
// Author: Flamekeeper Scott
// Created: 2025-11-28

use std::collections::HashMap;
use sha2::{Sha256, Digest};
use serde::{Serialize, Deserialize};

/// Total supply of RustChain tokens: 2^23 = 8,388,608 RTC
pub const TOTAL_SUPPLY: u64 = 8_388_608;

/// Block time in seconds (2 minutes)
pub const BLOCK_TIME_SECONDS: u64 = 120;

/// Chain ID for RustChain mainnet
pub const CHAIN_ID: u64 = 2718;

/// Hardware tiers based on age
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum HardwareTier {
    /// 30+ years - Legendary ancient silicon (3.5x multiplier)
    Ancient,
    /// 25-29 years - Sacred silicon guardians (3.0x multiplier)
    Sacred,
    /// 20-24 years - Classic era hardware (2.5x multiplier)
    Vintage,
    /// 15-19 years - Retro tech (2.0x multiplier)
    Classic,
    /// 10-14 years - Starting to age (1.5x multiplier)
    Retro,
    /// 5-9 years - Still young (1.0x multiplier)
    Modern,
    /// 0-4 years - Too new, penalized (0.5x multiplier)
    Recent,
}

impl HardwareTier {
    /// Get the mining multiplier for this tier
    pub fn multiplier(&self) -> f64 {
        match self {
            HardwareTier::Ancient => 3.5,
            HardwareTier::Sacred => 3.0,
            HardwareTier::Vintage => 2.5,
            HardwareTier::Classic => 2.0,
            HardwareTier::Retro => 1.5,
            HardwareTier::Modern => 1.0,
            HardwareTier::Recent => 0.5,
        }
    }

    /// Determine tier from hardware age in years
    pub fn from_age(years: u32) -> Self {
        match years {
            30.. => HardwareTier::Ancient,
            25..=29 => HardwareTier::Sacred,
            20..=24 => HardwareTier::Vintage,
            15..=19 => HardwareTier::Classic,
            10..=14 => HardwareTier::Retro,
            5..=9 => HardwareTier::Modern,
            _ => HardwareTier::Recent,
        }
    }

    /// Get tier display name
    pub fn name(&self) -> &'static str {
        match self {
            HardwareTier::Ancient => "Ancient Silicon",
            HardwareTier::Sacred => "Sacred Silicon",
            HardwareTier::Vintage => "Vintage Era",
            HardwareTier::Classic => "Classic Era",
            HardwareTier::Retro => "Retro Tech",
            HardwareTier::Modern => "Modern Hardware",
            HardwareTier::Recent => "Recent Hardware",
        }
    }
}

/// A RustChain wallet address
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct WalletAddress(pub String);

impl WalletAddress {
    /// Create a new wallet address
    pub fn new(address: impl Into<String>) -> Self {
        WalletAddress(address.into())
    }

    /// Validate address format (RTC prefix)
    pub fn is_valid(&self) -> bool {
        self.0.starts_with("RTC") && self.0.len() >= 20
    }

    /// Generate address from public key
    pub fn from_public_key(public_key: &[u8]) -> Self {
        let mut hasher = Sha256::new();
        hasher.update(public_key);
        let hash = hasher.finalize();
        let hex = hex::encode(&hash[..20]);
        WalletAddress(format!("RTC{}", hex))
    }
}

/// Block hash type
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct BlockHash(pub [u8; 32]);

impl BlockHash {
    pub fn from_bytes(bytes: [u8; 32]) -> Self {
        BlockHash(bytes)
    }

    pub fn to_hex(&self) -> String {
        hex::encode(self.0)
    }

    pub fn genesis() -> Self {
        let mut hasher = Sha256::new();
        hasher.update(b"RustChain Genesis - Proof of Antiquity");
        hasher.update(b"Every vintage machine has quantum potential");
        let result = hasher.finalize();
        BlockHash(result.into())
    }
}

/// Transaction hash type
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct TxHash(pub [u8; 32]);

/// Hardware characteristics for anti-emulation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HardwareCharacteristics {
    /// CPU model string
    pub cpu_model: String,
    /// CPU family number
    pub cpu_family: u32,
    /// CPU flags/features
    pub cpu_flags: Vec<String>,
    /// Cache sizes in KB
    pub cache_sizes: CacheSizes,
    /// Instruction timing measurements
    pub instruction_timings: HashMap<String, u64>,
    /// Unique hardware identifier
    pub unique_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CacheSizes {
    pub l1_data: u32,
    pub l1_instruction: u32,
    pub l2: u32,
    pub l3: Option<u32>,
}

/// A miner's proof of work/antiquity
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MiningProof {
    /// Miner's wallet address
    pub wallet: WalletAddress,
    /// Hardware description
    pub hardware: HardwareInfo,
    /// Anti-emulation hash
    pub anti_emulation_hash: [u8; 32],
    /// Timestamp of proof creation
    pub timestamp: u64,
    /// Nonce for uniqueness
    pub nonce: u64,
}

/// Hardware information for mining
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HardwareInfo {
    /// Model name
    pub model: String,
    /// Generation/family
    pub generation: String,
    /// Age in years
    pub age_years: u32,
    /// Hardware tier
    pub tier: HardwareTier,
    /// Mining multiplier (calculated from tier)
    pub multiplier: f64,
    /// Optional detailed characteristics
    pub characteristics: Option<HardwareCharacteristics>,
}

impl HardwareInfo {
    /// Create new hardware info with automatic tier calculation
    pub fn new(model: String, generation: String, age_years: u32) -> Self {
        let tier = HardwareTier::from_age(age_years);
        HardwareInfo {
            model,
            generation,
            age_years,
            tier,
            multiplier: tier.multiplier(),
            characteristics: None,
        }
    }

    /// Apply founder bonus multiplier
    pub fn with_founder_bonus(mut self) -> Self {
        self.multiplier *= 1.1;
        self
    }
}

/// A RustChain block
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Block {
    /// Block height (0 = genesis)
    pub height: u64,
    /// Block hash
    pub hash: BlockHash,
    /// Previous block hash
    pub previous_hash: BlockHash,
    /// Block timestamp
    pub timestamp: u64,
    /// Miners who contributed proofs for this block
    pub miners: Vec<BlockMiner>,
    /// Total reward distributed
    pub total_reward: u64,
    /// Merkle root of transactions
    pub merkle_root: [u8; 32],
    /// State root hash
    pub state_root: [u8; 32],
}

/// A miner's entry in a block
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BlockMiner {
    /// Wallet address
    pub wallet: WalletAddress,
    /// Hardware used
    pub hardware: String,
    /// Multiplier earned
    pub multiplier: f64,
    /// Reward earned (in smallest unit)
    pub reward: u64,
}

/// Token amount in smallest unit (8 decimals like Satoshi)
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub struct TokenAmount(pub u64);

impl TokenAmount {
    /// One full RTC token (100,000,000 smallest units)
    pub const ONE_RTC: u64 = 100_000_000;

    /// Create from RTC amount
    pub fn from_rtc(rtc: f64) -> Self {
        TokenAmount((rtc * Self::ONE_RTC as f64) as u64)
    }

    /// Convert to RTC
    pub fn to_rtc(&self) -> f64 {
        self.0 as f64 / Self::ONE_RTC as f64
    }

    /// Checked addition
    pub fn checked_add(self, other: Self) -> Option<Self> {
        self.0.checked_add(other.0).map(TokenAmount)
    }

    /// Checked subtraction
    pub fn checked_sub(self, other: Self) -> Option<Self> {
        self.0.checked_sub(other.0).map(TokenAmount)
    }
}

/// Transaction types
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TransactionType {
    /// Standard token transfer
    Transfer {
        from: WalletAddress,
        to: WalletAddress,
        amount: TokenAmount,
    },
    /// Mining reward
    MiningReward {
        miner: WalletAddress,
        amount: TokenAmount,
        block_height: u64,
    },
    /// NFT badge award
    BadgeAward {
        recipient: WalletAddress,
        badge_type: String,
        badge_id: String,
    },
    /// Stake tokens (future feature)
    Stake {
        wallet: WalletAddress,
        amount: TokenAmount,
    },
}

/// A RustChain transaction
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Transaction {
    /// Transaction hash
    pub hash: TxHash,
    /// Transaction type and data
    pub tx_type: TransactionType,
    /// Timestamp
    pub timestamp: u64,
    /// Signature
    pub signature: Vec<u8>,
    /// Fee paid (if applicable)
    pub fee: TokenAmount,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_hardware_tier_from_age() {
        assert_eq!(HardwareTier::from_age(35), HardwareTier::Ancient);
        assert_eq!(HardwareTier::from_age(27), HardwareTier::Sacred);
        assert_eq!(HardwareTier::from_age(22), HardwareTier::Vintage);
        assert_eq!(HardwareTier::from_age(17), HardwareTier::Classic);
        assert_eq!(HardwareTier::from_age(12), HardwareTier::Retro);
        assert_eq!(HardwareTier::from_age(7), HardwareTier::Modern);
        assert_eq!(HardwareTier::from_age(2), HardwareTier::Recent);
    }

    #[test]
    fn test_tier_multipliers() {
        assert_eq!(HardwareTier::Ancient.multiplier(), 3.5);
        assert_eq!(HardwareTier::Recent.multiplier(), 0.5);
    }

    #[test]
    fn test_token_amount_conversion() {
        let amount = TokenAmount::from_rtc(100.5);
        assert!((amount.to_rtc() - 100.5).abs() < 0.000001);
    }

    #[test]
    fn test_wallet_address_validation() {
        let valid = WalletAddress::new("RTC1FlamekeeperScottEternalGuardian0x00");
        assert!(valid.is_valid());

        let invalid = WalletAddress::new("BTC123");
        assert!(!invalid.is_valid());
    }
}
