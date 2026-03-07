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

// ═══════════════════════════════════════════════════════════
// RIP-0683: Console CPU Families
// ═══════════════════════════════════════════════════════════

/// Console-specific CPU families with release year and base multiplier
/// Format: (arch_alias, release_year, base_multiplier)
pub const CONSOLE_CPU_FAMILIES: &[(&str, u32, f64)] = &[
    // Nintendo consoles
    ("nes_6502", 1983, 2.8),        // Ricoh 2A03 (6502 derivative) - NES/Famicom
    ("snes_65c816", 1990, 2.7),     // Ricoh 5A22 (65C816) - SNES/Super Famicom
    ("n64_mips", 1996, 2.5),        // NEC VR4300 (MIPS R4300i) - Nintendo 64
    ("gameboy_z80", 1989, 2.6),     // Sharp LR35902 (Z80 derivative) - Game Boy
    ("gba_arm7", 2001, 2.3),        // ARM7TDMI - Game Boy Advance
    
    // Sega consoles
    ("genesis_68000", 1988, 2.5),   // Motorola 68000 - Genesis/Mega Drive
    ("sms_z80", 1986, 2.6),         // Zilog Z80 - Sega Master System
    ("saturn_sh2", 1994, 2.6),      // Hitachi SH-2 (dual) - Sega Saturn
    
    // Sony consoles
    ("ps1_mips", 1994, 2.8),        // MIPS R3000A - PlayStation 1
    
    // Generic CPU families (used across multiple platforms)
    ("6502", 1975, 2.8),            // MOS 6502 - NES, Apple II, Commodore 64
    ("65c816", 1983, 2.7),          // WDC 65C816 - SNES, Apple IIGS
    ("z80", 1976, 2.6),             // Zilog Z80 - Game Boy, SMS, MSX, ZX Spectrum
    ("sh2", 1994, 2.6),             // Hitachi SH-2 - Saturn, 32X
];

/// Get console CPU info by architecture alias
pub fn get_console_cpu_info(arch: &str) -> Option<(&str, u32, f64)> {
    let arch_lower = arch.to_lowercase();
    CONSOLE_CPU_FAMILIES
        .iter()
        .find(|(name, _, _)| name.to_lowercase() == arch_lower)
        .copied()
}

/// Check if an architecture is a console CPU
pub fn is_console_arch(arch: &str) -> bool {
    get_console_cpu_info(arch).is_some()
}

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

    // ═══════════════════════════════════════════════════════════
    // RIP-0683: Console CPU Tests
    // ═══════════════════════════════════════════════════════════

    #[test]
    fn test_console_cpu_families_exist() {
        // Verify console CPU families are defined
        assert!(!CONSOLE_CPU_FAMILIES.is_empty());
        assert!(CONSOLE_CPU_FAMILIES.len() >= 12); // At least 12 console CPUs
    }

    #[test]
    fn test_console_cpu_lookup() {
        // Test Nintendo consoles
        let nes = get_console_cpu_info("nes_6502");
        assert!(nes.is_some());
        let (name, year, mult) = nes.unwrap();
        assert_eq!(name, "nes_6502");
        assert_eq!(year, 1983);
        assert!((mult - 2.8).abs() < 0.01);

        let n64 = get_console_cpu_info("n64_mips");
        assert!(n64.is_some());
        let (_, year, _) = n64.unwrap();
        assert_eq!(year, 1996);

        // Test Sega consoles
        let genesis = get_console_cpu_info("genesis_68000");
        assert!(genesis.is_some());
        let (_, year, _) = genesis.unwrap();
        assert_eq!(year, 1988);

        // Test Sony consoles
        let ps1 = get_console_cpu_info("ps1_mips");
        assert!(ps1.is_some());
        let (_, year, _) = ps1.unwrap();
        assert_eq!(year, 1994);
    }

    #[test]
    fn test_console_cpu_case_insensitive() {
        // Lookup should be case-insensitive
        let upper = get_console_cpu_info("NES_6502");
        let lower = get_console_cpu_info("nes_6502");
        assert_eq!(upper, lower);

        let mixed = get_console_cpu_info("N64_MiPs");
        assert!(mixed.is_some());
    }

    #[test]
    fn test_console_arch_detection() {
        // Valid console arches
        assert!(is_console_arch("nes_6502"));
        assert!(is_console_arch("n64_mips"));
        assert!(is_console_arch("genesis_68000"));
        assert!(is_console_arch("ps1_mips"));
        assert!(is_console_arch("6502"));
        assert!(is_console_arch("z80"));

        // Invalid console arches
        assert!(!is_console_arch("pentium"));
        assert!(!is_console_arch("modern"));
        assert!(!is_console_arch("x86_64"));
        assert!(!is_console_arch(""));
    }

    #[test]
    fn test_console_cpu_multipliers() {
        // Verify multipliers are in expected range (2.3x - 2.8x)
        for (_, _, mult) in CONSOLE_CPU_FAMILIES {
            assert!(*mult >= 2.3 && *mult <= 2.8, 
                "Multiplier {} out of range for console CPU", mult);
        }

        // NES should have highest multiplier (oldest)
        let nes = get_console_cpu_info("nes_6502").unwrap();
        let gba = get_console_cpu_info("gba_arm7").unwrap();
        assert!(nes.2 > gba.2); // NES multiplier > GBA multiplier
    }

    #[test]
    fn test_console_vs_modern_multiplier() {
        // Console CPUs should have better multipliers than modern hardware
        let modern_mult = HardwareTier::Modern.multiplier(); // 1.0x
        for (_, _, console_mult) in CONSOLE_CPU_FAMILIES {
            assert!(*console_mult > modern_mult,
                "Console multiplier {} should exceed modern {}", 
                console_mult, modern_mult);
        }
    }
}
