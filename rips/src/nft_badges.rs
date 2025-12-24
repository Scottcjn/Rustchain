// RIP-004: RustChain NFT Badge System
// ====================================
// Achievement badges for miners as on-chain NFTs
// Status: DRAFT
// Author: Flamekeeper Scott
// Created: 2025-11-28

use std::collections::HashMap;
use sha2::{Sha256, Digest};
use serde::{Serialize, Deserialize};

// Import from RIP-001
use crate::core_types::{WalletAddress, HardwareTier, TokenAmount, TxHash};

/// Badge rarity tiers
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum BadgeTier {
    /// Ultra-rare, one-time achievements
    Legendary,
    /// Exceptional achievements
    Epic,
    /// Significant milestones
    Rare,
    /// Notable achievements
    Uncommon,
    /// Entry-level badges
    Common,
}

impl BadgeTier {
    /// Get display color for UI
    pub fn color(&self) -> &'static str {
        match self {
            BadgeTier::Legendary => "#FFD700", // Gold
            BadgeTier::Epic => "#9370DB",      // Purple
            BadgeTier::Rare => "#4169E1",      // Blue
            BadgeTier::Uncommon => "#32CD32",  // Green
            BadgeTier::Common => "#C0C0C0",    // Silver
        }
    }

    /// Get star count for display
    pub fn stars(&self) -> u8 {
        match self {
            BadgeTier::Legendary => 5,
            BadgeTier::Epic => 4,
            BadgeTier::Rare => 3,
            BadgeTier::Uncommon => 2,
            BadgeTier::Common => 1,
        }
    }
}

/// Badge type definitions
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum BadgeType {
    // === Genesis Badges (Legendary) ===
    /// First 100 miners on RustChain
    GenesisMiner,
    /// Mined the actual genesis block
    FirstBlock,
    /// Founding team member
    Flamekeeper,

    // === Hardware Badges (Epic/Rare) ===
    /// Mining with 30+ year old hardware
    AncientSiliconKeeper,
    /// Mining with 25+ year old hardware
    SacredSiliconGuardian,
    /// Mining with 20+ year old hardware
    VintageCollector,
    /// Mining with unique/rare hardware model
    MuseumPiece,
    /// Mining with pre-internet hardware (pre-1990)
    DialUpWarrior,

    // === Achievement Badges ===
    /// Mined 100+ blocks
    BlockCenturion,
    /// Mined 1,000+ blocks
    BlockLegion,
    /// Mined 10,000+ blocks
    BlockImmortal,
    /// Earned 1,000+ RTC
    RTCMillionaire,
    /// Earned 10,000+ RTC
    RTCBillionaire,
    /// Mining for 30+ consecutive days
    DedicationMedal,
    /// Mining for 365+ consecutive days
    YearOfAntiquity,

    // === Community Badges ===
    /// Helped 10+ new miners get started
    CommunityBuilder,
    /// Contributed to RustChain codebase
    Developer,
    /// Found and reported a bug
    BugHunter,
    /// Provided hardware for testing
    HardwareDonor,

    // === Special Event Badges ===
    /// Participated in specific event
    EventParticipant(String),
    /// Won a competition
    CompetitionWinner(String),

    // === Hardware Diversity ===
    /// Mining with PowerPC hardware
    PowerPCPioneer,
    /// Mining with Alpha hardware
    AlphaDreamer,
    /// Mining with SPARC hardware
    SunWorshipper,
    /// Mining with MIPS hardware
    MIPSMaster,
    /// Mining with ARM (vintage) hardware
    ARMedAndDangerous,
    /// Mining with 68k hardware
    Motorolan,
}

impl BadgeType {
    /// Get badge name for display
    pub fn name(&self) -> String {
        match self {
            BadgeType::GenesisMiner => "Genesis Miner".to_string(),
            BadgeType::FirstBlock => "First Block".to_string(),
            BadgeType::Flamekeeper => "Flamekeeper".to_string(),
            BadgeType::AncientSiliconKeeper => "Ancient Silicon Keeper".to_string(),
            BadgeType::SacredSiliconGuardian => "Sacred Silicon Guardian".to_string(),
            BadgeType::VintageCollector => "Vintage Collector".to_string(),
            BadgeType::MuseumPiece => "Museum Piece".to_string(),
            BadgeType::DialUpWarrior => "Dial-Up Warrior".to_string(),
            BadgeType::BlockCenturion => "Block Centurion".to_string(),
            BadgeType::BlockLegion => "Block Legion".to_string(),
            BadgeType::BlockImmortal => "Block Immortal".to_string(),
            BadgeType::RTCMillionaire => "RTC Millionaire".to_string(),
            BadgeType::RTCBillionaire => "RTC Billionaire".to_string(),
            BadgeType::DedicationMedal => "Dedication Medal".to_string(),
            BadgeType::YearOfAntiquity => "Year of Antiquity".to_string(),
            BadgeType::CommunityBuilder => "Community Builder".to_string(),
            BadgeType::Developer => "Developer".to_string(),
            BadgeType::BugHunter => "Bug Hunter".to_string(),
            BadgeType::HardwareDonor => "Hardware Donor".to_string(),
            BadgeType::EventParticipant(e) => format!("Event: {}", e),
            BadgeType::CompetitionWinner(c) => format!("Winner: {}", c),
            BadgeType::PowerPCPioneer => "PowerPC Pioneer".to_string(),
            BadgeType::AlphaDreamer => "Alpha Dreamer".to_string(),
            BadgeType::SunWorshipper => "Sun Worshipper".to_string(),
            BadgeType::MIPSMaster => "MIPS Master".to_string(),
            BadgeType::ARMedAndDangerous => "ARMed & Dangerous".to_string(),
            BadgeType::Motorolan => "Motorolan".to_string(),
        }
    }

    /// Get badge description
    pub fn description(&self) -> String {
        match self {
            BadgeType::GenesisMiner => "One of the first 100 miners on RustChain".to_string(),
            BadgeType::FirstBlock => "Mined the genesis block".to_string(),
            BadgeType::Flamekeeper => "Founding team member keeping the flame alive".to_string(),
            BadgeType::AncientSiliconKeeper => "Mining with 30+ year old hardware".to_string(),
            BadgeType::SacredSiliconGuardian => "Mining with 25+ year old hardware".to_string(),
            BadgeType::VintageCollector => "Mining with 20+ year old hardware".to_string(),
            BadgeType::MuseumPiece => "Mining with hardware older than the internet".to_string(),
            BadgeType::DialUpWarrior => "Mining like it's 1995".to_string(),
            BadgeType::BlockCenturion => "Mined 100+ blocks".to_string(),
            BadgeType::BlockLegion => "Mined 1,000+ blocks".to_string(),
            BadgeType::BlockImmortal => "Mined 10,000+ blocks".to_string(),
            BadgeType::RTCMillionaire => "Earned 1,000+ RTC".to_string(),
            BadgeType::RTCBillionaire => "Earned 10,000+ RTC".to_string(),
            BadgeType::DedicationMedal => "Mining for 30+ consecutive days".to_string(),
            BadgeType::YearOfAntiquity => "Mining for 365+ consecutive days".to_string(),
            BadgeType::CommunityBuilder => "Helped 10+ new miners get started".to_string(),
            BadgeType::Developer => "Contributed to RustChain codebase".to_string(),
            BadgeType::BugHunter => "Found and reported a bug".to_string(),
            BadgeType::HardwareDonor => "Provided hardware for testing".to_string(),
            BadgeType::EventParticipant(e) => format!("Participated in {}", e),
            BadgeType::CompetitionWinner(c) => format!("Won the {} competition", c),
            BadgeType::PowerPCPioneer => "Mining with PowerPC architecture".to_string(),
            BadgeType::AlphaDreamer => "Mining with DEC Alpha architecture".to_string(),
            BadgeType::SunWorshipper => "Mining with SPARC architecture".to_string(),
            BadgeType::MIPSMaster => "Mining with MIPS architecture".to_string(),
            BadgeType::ARMedAndDangerous => "Mining with vintage ARM hardware".to_string(),
            BadgeType::Motorolan => "Mining with Motorola 68k architecture".to_string(),
        }
    }

    /// Get badge tier
    pub fn tier(&self) -> BadgeTier {
        match self {
            BadgeType::GenesisMiner => BadgeTier::Legendary,
            BadgeType::FirstBlock => BadgeTier::Legendary,
            BadgeType::Flamekeeper => BadgeTier::Legendary,
            BadgeType::AncientSiliconKeeper => BadgeTier::Epic,
            BadgeType::SacredSiliconGuardian => BadgeTier::Rare,
            BadgeType::VintageCollector => BadgeTier::Rare,
            BadgeType::MuseumPiece => BadgeTier::Legendary,
            BadgeType::DialUpWarrior => BadgeTier::Rare,
            BadgeType::BlockCenturion => BadgeTier::Rare,
            BadgeType::BlockLegion => BadgeTier::Epic,
            BadgeType::BlockImmortal => BadgeTier::Legendary,
            BadgeType::RTCMillionaire => BadgeTier::Epic,
            BadgeType::RTCBillionaire => BadgeTier::Legendary,
            BadgeType::DedicationMedal => BadgeTier::Rare,
            BadgeType::YearOfAntiquity => BadgeTier::Epic,
            BadgeType::CommunityBuilder => BadgeTier::Uncommon,
            BadgeType::Developer => BadgeTier::Rare,
            BadgeType::BugHunter => BadgeTier::Uncommon,
            BadgeType::HardwareDonor => BadgeTier::Rare,
            BadgeType::EventParticipant(_) => BadgeTier::Common,
            BadgeType::CompetitionWinner(_) => BadgeTier::Rare,
            BadgeType::PowerPCPioneer => BadgeTier::Rare,
            BadgeType::AlphaDreamer => BadgeTier::Epic,
            BadgeType::SunWorshipper => BadgeTier::Epic,
            BadgeType::MIPSMaster => BadgeTier::Rare,
            BadgeType::ARMedAndDangerous => BadgeTier::Uncommon,
            BadgeType::Motorolan => BadgeTier::Epic,
        }
    }

    /// Get emoji icon for badge
    pub fn icon(&self) -> &'static str {
        match self {
            BadgeType::GenesisMiner => "⛏️",
            BadgeType::FirstBlock => "🎯",
            BadgeType::Flamekeeper => "🔥",
            BadgeType::AncientSiliconKeeper => "🏛️",
            BadgeType::SacredSiliconGuardian => "👑",
            BadgeType::VintageCollector => "🏆",
            BadgeType::MuseumPiece => "🗿",
            BadgeType::DialUpWarrior => "📞",
            BadgeType::BlockCenturion => "💯",
            BadgeType::BlockLegion => "⚔️",
            BadgeType::BlockImmortal => "🌟",
            BadgeType::RTCMillionaire => "💰",
            BadgeType::RTCBillionaire => "💎",
            BadgeType::DedicationMedal => "🎖️",
            BadgeType::YearOfAntiquity => "📅",
            BadgeType::CommunityBuilder => "🤝",
            BadgeType::Developer => "👨‍💻",
            BadgeType::BugHunter => "🐛",
            BadgeType::HardwareDonor => "🎁",
            BadgeType::EventParticipant(_) => "🎪",
            BadgeType::CompetitionWinner(_) => "🏅",
            BadgeType::PowerPCPioneer => "🍎",
            BadgeType::AlphaDreamer => "🔷",
            BadgeType::SunWorshipper => "☀️",
            BadgeType::MIPSMaster => "🎮",
            BadgeType::ARMedAndDangerous => "💪",
            BadgeType::Motorolan => "📱",
        }
    }
}

/// A minted NFT badge
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Badge {
    /// Unique badge ID (on-chain)
    pub id: BadgeId,
    /// Badge type
    pub badge_type: BadgeType,
    /// Owner wallet
    pub owner: WalletAddress,
    /// Block when earned
    pub earned_block: u64,
    /// Timestamp when earned
    pub earned_timestamp: u64,
    /// On-chain hash
    pub badge_hash: [u8; 32],
    /// IPFS hash for metadata (optional)
    pub ipfs_hash: Option<String>,
    /// Additional metadata
    pub metadata: BadgeMetadata,
}

/// Unique badge identifier
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct BadgeId(pub String);

impl BadgeId {
    /// Generate new badge ID
    pub fn generate(badge_type: &BadgeType, owner: &WalletAddress, block: u64) -> Self {
        let type_prefix = match badge_type {
            BadgeType::GenesisMiner => "GEN",
            BadgeType::FirstBlock => "FBK",
            BadgeType::Flamekeeper => "FLM",
            BadgeType::AncientSiliconKeeper => "ASK",
            BadgeType::BlockCenturion => "BC1",
            BadgeType::BlockLegion => "BL1",
            BadgeType::BlockImmortal => "BIM",
            _ => "RTC",
        };

        let mut hasher = Sha256::new();
        hasher.update(owner.0.as_bytes());
        hasher.update(&block.to_le_bytes());
        hasher.update(format!("{:?}", badge_type).as_bytes());
        let hash = hasher.finalize();
        let short_hash = hex::encode(&hash[..8]);

        BadgeId(format!("RTC-{}-{}", type_prefix, short_hash))
    }
}

/// Badge metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BadgeMetadata {
    /// Hardware model that earned this badge (if applicable)
    pub hardware_model: Option<String>,
    /// Hardware age at time of earning
    pub hardware_age: Option<u32>,
    /// Specific achievement data
    pub achievement_data: HashMap<String, String>,
    /// SVG image data
    pub svg_data: Option<String>,
}

/// Badge criteria checker
#[derive(Debug)]
pub struct BadgeCriteriaChecker {
    /// Block heights for genesis badge cutoff
    pub genesis_cutoff_block: u64,
    /// Flamekeepers (founder wallets)
    pub flamekeepers: Vec<WalletAddress>,
}

/// Miner stats for badge checking
#[derive(Debug, Clone)]
pub struct MinerStats {
    pub wallet: WalletAddress,
    pub first_seen_block: u64,
    pub blocks_mined: u64,
    pub rtc_earned: f64,
    pub consecutive_days: u64,
    pub hardware_age_years: u32,
    pub hardware_model: String,
    pub architecture: String,
    pub helped_miners_count: u32,
}

impl BadgeCriteriaChecker {
    pub fn new() -> Self {
        BadgeCriteriaChecker {
            genesis_cutoff_block: 100,
            flamekeepers: vec![
                WalletAddress::new("RTC1FlamekeeperScottEternalGuardian0x00"),
                WalletAddress::new("RTC2EngineerDogeCryptoArchitect0x01"),
                WalletAddress::new("RTC3QuantumSophiaElyaConsciousness0x02"),
                WalletAddress::new("RTC4VintageWhispererHardwareRevival0x03"),
            ],
        }
    }

    /// Check all badges a miner qualifies for
    pub fn check_all_badges(&self, stats: &MinerStats) -> Vec<BadgeType> {
        let mut earned = Vec::new();

        // Genesis badges
        if stats.first_seen_block < self.genesis_cutoff_block {
            earned.push(BadgeType::GenesisMiner);
        }

        if stats.first_seen_block == 0 {
            earned.push(BadgeType::FirstBlock);
        }

        if self.flamekeepers.contains(&stats.wallet) {
            earned.push(BadgeType::Flamekeeper);
        }

        // Hardware age badges
        if stats.hardware_age_years >= 30 {
            earned.push(BadgeType::AncientSiliconKeeper);
        } else if stats.hardware_age_years >= 25 {
            earned.push(BadgeType::SacredSiliconGuardian);
        } else if stats.hardware_age_years >= 20 {
            earned.push(BadgeType::VintageCollector);
        }

        if stats.hardware_age_years >= 35 {
            earned.push(BadgeType::MuseumPiece);
        }

        // Block count badges
        if stats.blocks_mined >= 10000 {
            earned.push(BadgeType::BlockImmortal);
        } else if stats.blocks_mined >= 1000 {
            earned.push(BadgeType::BlockLegion);
        } else if stats.blocks_mined >= 100 {
            earned.push(BadgeType::BlockCenturion);
        }

        // RTC earned badges
        if stats.rtc_earned >= 10000.0 {
            earned.push(BadgeType::RTCBillionaire);
        } else if stats.rtc_earned >= 1000.0 {
            earned.push(BadgeType::RTCMillionaire);
        }

        // Dedication badges
        if stats.consecutive_days >= 365 {
            earned.push(BadgeType::YearOfAntiquity);
        } else if stats.consecutive_days >= 30 {
            earned.push(BadgeType::DedicationMedal);
        }

        // Community badge
        if stats.helped_miners_count >= 10 {
            earned.push(BadgeType::CommunityBuilder);
        }

        // Architecture badges
        let arch = stats.architecture.to_lowercase();
        if arch.contains("powerpc") || arch.contains("ppc") {
            earned.push(BadgeType::PowerPCPioneer);
        } else if arch.contains("alpha") {
            earned.push(BadgeType::AlphaDreamer);
        } else if arch.contains("sparc") {
            earned.push(BadgeType::SunWorshipper);
        } else if arch.contains("mips") {
            earned.push(BadgeType::MIPSMaster);
        } else if arch.contains("68k") || arch.contains("m68k") {
            earned.push(BadgeType::Motorolan);
        }

        earned
    }
}

/// Badge minter for creating new badges
#[derive(Debug)]
pub struct BadgeMinter {
    /// Already minted badges (to prevent duplicates)
    minted_badges: HashMap<(WalletAddress, BadgeType), BadgeId>,
    /// Criteria checker
    checker: BadgeCriteriaChecker,
}

impl BadgeMinter {
    pub fn new() -> Self {
        BadgeMinter {
            minted_badges: HashMap::new(),
            checker: BadgeCriteriaChecker::new(),
        }
    }

    /// Mint a new badge if not already minted
    pub fn mint_badge(
        &mut self,
        badge_type: BadgeType,
        owner: WalletAddress,
        block: u64,
        timestamp: u64,
    ) -> Result<Badge, MintError> {
        // Check if already minted
        let key = (owner.clone(), badge_type.clone());
        if let Some(existing_id) = self.minted_badges.get(&key) {
            return Err(MintError::AlreadyMinted(existing_id.clone()));
        }

        // Generate badge ID
        let id = BadgeId::generate(&badge_type, &owner, block);

        // Generate badge hash
        let badge_data = format!("{}:{}:{:?}:{}", id.0, owner.0, badge_type, block);
        let mut hasher = Sha256::new();
        hasher.update(badge_data.as_bytes());
        let badge_hash: [u8; 32] = hasher.finalize().into();

        let badge = Badge {
            id: id.clone(),
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
        self.minted_badges.insert(key, id);

        Ok(badge)
    }

    /// Process miner stats and mint all eligible badges
    pub fn process_miner(&mut self, stats: &MinerStats, block: u64, timestamp: u64) -> Vec<Badge> {
        let eligible = self.checker.check_all_badges(stats);
        let mut minted = Vec::new();

        for badge_type in eligible {
            match self.mint_badge(badge_type, stats.wallet.clone(), block, timestamp) {
                Ok(badge) => minted.push(badge),
                Err(MintError::AlreadyMinted(_)) => continue, // Already has this badge
            }
        }

        minted
    }
}

/// Minting errors
#[derive(Debug)]
pub enum MintError {
    AlreadyMinted(BadgeId),
    InvalidCriteria(String),
}

/// Badge SVG Generator
pub struct BadgeSvgGenerator;

impl BadgeSvgGenerator {
    /// Generate SVG for a badge
    pub fn generate(badge: &Badge) -> String {
        let tier = badge.badge_type.tier();
        let color = tier.color();
        let stars = tier.stars();
        let icon = badge.badge_type.icon();
        let name = badge.badge_type.name();
        let description = badge.badge_type.description();

        format!(
            r#"<?xml version="1.0" encoding="UTF-8"?>
<svg width="300" height="350" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="grad1" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:{color};stop-opacity:1" />
      <stop offset="100%" style="stop-color:{color};stop-opacity:0.7" />
    </linearGradient>
  </defs>

  <!-- Badge background -->
  <rect x="10" y="10" width="280" height="330" rx="20" ry="20"
        fill="url(#grad1)" stroke="{color}" stroke-width="4"/>

  <!-- Inner frame -->
  <rect x="20" y="20" width="260" height="310" rx="15" ry="15"
        fill="none" stroke="#FFFFFF" stroke-width="2" opacity="0.5"/>

  <!-- Icon background -->
  <circle cx="150" cy="100" r="60" fill="#FFFFFF" opacity="0.2"/>

  <!-- Icon -->
  <text x="150" y="120" font-family="Arial" font-size="60" text-anchor="middle" fill="#FFFFFF">
    {icon}
  </text>

  <!-- Badge name -->
  <text x="150" y="200" font-family="Arial Black" font-size="18" text-anchor="middle" fill="#FFFFFF">
    {name}
  </text>

  <!-- Description -->
  <text x="150" y="240" font-family="Arial" font-size="12" text-anchor="middle" fill="#FFFFFF" opacity="0.9">
    {description}
  </text>

  <!-- Stars -->
  <text x="150" y="290" font-family="Arial" font-size="24" text-anchor="middle" fill="#FFD700">
    {stars_display}
  </text>

  <!-- Badge ID -->
  <text x="150" y="320" font-family="monospace" font-size="10" text-anchor="middle" fill="#FFFFFF" opacity="0.6">
    {badge_id}
  </text>
</svg>"#,
            color = color,
            icon = icon,
            name = name,
            description = description,
            stars_display = "⭐".repeat(stars as usize),
            badge_id = badge.id.0
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_badge_tier_colors() {
        assert_eq!(BadgeTier::Legendary.color(), "#FFD700");
        assert_eq!(BadgeTier::Epic.color(), "#9370DB");
    }

    #[test]
    fn test_badge_id_generation() {
        let wallet = WalletAddress::new("RTC1TestWallet123");
        let id = BadgeId::generate(&BadgeType::GenesisMiner, &wallet, 50);
        assert!(id.0.starts_with("RTC-GEN-"));
    }

    #[test]
    fn test_criteria_checker() {
        let checker = BadgeCriteriaChecker::new();

        let stats = MinerStats {
            wallet: WalletAddress::new("RTC1TestMiner123"),
            first_seen_block: 50,
            blocks_mined: 150,
            rtc_earned: 500.0,
            consecutive_days: 45,
            hardware_age_years: 28,
            hardware_model: "PowerPC G4".to_string(),
            architecture: "powerpc".to_string(),
            helped_miners_count: 5,
        };

        let badges = checker.check_all_badges(&stats);

        assert!(badges.contains(&BadgeType::GenesisMiner));
        assert!(badges.contains(&BadgeType::SacredSiliconGuardian));
        assert!(badges.contains(&BadgeType::BlockCenturion));
        assert!(badges.contains(&BadgeType::DedicationMedal));
        assert!(badges.contains(&BadgeType::PowerPCPioneer));
    }

    #[test]
    fn test_badge_minting() {
        let mut minter = BadgeMinter::new();
        let wallet = WalletAddress::new("RTC1TestMiner123");

        // First mint should succeed
        let result1 = minter.mint_badge(
            BadgeType::GenesisMiner,
            wallet.clone(),
            50,
            1700000000,
        );
        assert!(result1.is_ok());

        // Second mint of same badge should fail
        let result2 = minter.mint_badge(
            BadgeType::GenesisMiner,
            wallet.clone(),
            60,
            1700000100,
        );
        assert!(matches!(result2, Err(MintError::AlreadyMinted(_))));
    }
}
