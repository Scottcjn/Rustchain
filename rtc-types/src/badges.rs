//! Badge and NFT-related types

use serde::{Deserialize, Serialize};

/// Badge information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Badge {
    /// Badge ID
    #[serde(rename = "nftId")]
    pub nft_id: String,
    /// Badge title
    pub title: String,
    /// Badge class (CPU, GPU, IO, Display, etc.)
    pub class: String,
    /// Badge description
    pub description: String,
    /// Emotional resonance data
    #[serde(rename = "emotionalResonance")]
    pub emotional_resonance: Option<EmotionalResonance>,
    /// Emoji symbol
    pub symbol: Option<String>,
    /// Visual anchor description
    #[serde(rename = "visualAnchor")]
    pub visual_anchor: Option<String>,
    /// Rarity level
    pub rarity: String,
    /// Is soulbound (non-transferable)
    #[serde(rename = "soulbound")]
    pub soulbound: bool,
}

/// Emotional resonance metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EmotionalResonance {
    /// Emotional state
    pub state: String,
    /// Trigger condition
    pub trigger: String,
    /// Timestamp
    pub timestamp: String,
}

/// Badge holder information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BadgeHolder {
    /// Holder address
    pub address: String,
    /// Badges held
    pub badges: Vec<String>,
    /// Total count
    pub count: u32,
}

/// Relic badge set
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RelicBadgeSet {
    /// Array of badges
    pub badges: Vec<Badge>,
}

/// User badges response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UserBadges {
    /// User address
    pub address: String,
    /// Earned badges
    pub badges: Vec<Badge>,
    /// Total earned
    pub total: u32,
    /// Rarest badge
    pub rarest: Option<String>,
}

/// Badge mint request
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MintBadgeRequest {
    /// Recipient address
    pub to: String,
    /// Badge ID to mint
    #[serde(rename = "badgeId")]
    pub badge_id: String,
    /// Metadata URI (optional)
    #[serde(rename = "metadataUri")]
    pub metadata_uri: Option<String>,
}

/// Badge mint response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MintBadgeResponse {
    /// Transaction hash
    pub hash: String,
    /// Token ID
    #[serde(rename = "tokenId")]
    pub token_id: String,
    /// Badge ID
    #[serde(rename = "badgeId")]
    pub badge_id: String,
}
