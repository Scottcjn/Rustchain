use serde::{Deserialize, Serialize};

/// Represents a wallet address or miner ID.
pub type WalletId = String;
pub type MinerId = String;

/// Types of bonuses available.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum BonusType {
    FirstAttestation,
    RealHardware,
    VintageHardware,
    FirstPrMerged,
    FirstBountyCompleted,
    ReferMiner,
    ReferDev,
}

/// A claim submitted by a user.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Claim {
    pub wallet_id: WalletId,
    pub miner_id: Option<MinerId>,
    pub bonus_type: BonusType,
    pub proof: String, // e.g., PR URL, attestation hash
}

/// Result of processing a claim.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClaimResult {
    pub wallet_id: WalletId,
    pub bonus_type: BonusType,
    pub amount: u64,
    pub success: bool,
    pub message: String,
}

impl BonusType {
    /// Returns the base reward amount for this bonus type.
    pub fn base_amount(&self) -> u64 {
        match self {
            BonusType::FirstAttestation => 10,
            BonusType::RealHardware => 5,
            BonusType::VintageHardware => 10,
            BonusType::FirstPrMerged => 25,
            BonusType::FirstBountyCompleted => 10,
            BonusType::ReferMiner => 10,
            BonusType::ReferDev => 15,
        }
    }

    /// Indicates if the bonus can stack with others.
    pub fn stackable(&self) -> bool {
        !matches!(self, BonusType::FirstAttestation | BonusType::FirstPrMerged)
    }
}
