//! Core data models for RIP-305 Cross-Chain Airdrop

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

/// Target blockchain for airdrop
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum TargetChain {
    Solana,
    Base,
}

impl std::fmt::Display for TargetChain {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            TargetChain::Solana => write!(f, "solana"),
            TargetChain::Base => write!(f, "base"),
        }
    }
}

impl std::str::FromStr for TargetChain {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_lowercase().as_str() {
            "solana" => Ok(TargetChain::Solana),
            "base" => Ok(TargetChain::Base),
            _ => Err(format!("Invalid chain: {}. Must be 'solana' or 'base'", s)),
        }
    }
}

/// GitHub contribution tier for airdrop eligibility
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum GitHubTier {
    Stargazer,    // 10+ repos starred
    Contributor,  // 1+ merged PR
    Builder,      // 3+ merged PRs
    Security,     // Verified vulnerability
    Core,         // 5+ merged PRs or Star King badge
    Miner,        // Active attestation history
}

impl GitHubTier {
    /// Base wRTC allocation for each tier
    pub fn base_allocation(&self) -> u64 {
        match self {
            GitHubTier::Stargazer => 25,
            GitHubTier::Contributor => 50,
            GitHubTier::Builder => 100,
            GitHubTier::Security => 150,
            GitHubTier::Core => 200,
            GitHubTier::Miner => 100,
        }
    }

    /// Human-readable description
    pub fn description(&self) -> &'static str {
        match self {
            GitHubTier::Stargazer => "10+ repos starred",
            GitHubTier::Contributor => "1+ merged PR",
            GitHubTier::Builder => "3+ merged PRs",
            GitHubTier::Security => "Verified vulnerability found",
            GitHubTier::Core => "5+ merged PRs or Star King badge",
            GitHubTier::Miner => "Active attestation history",
        }
    }
}

/// Wallet balance tier for multiplier calculation
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum WalletTier {
    Minimum, // 0.1-1 SOL or 0.01-0.1 ETH
    Mid,     // 1-10 SOL or 0.1-1 ETH
    High,    // 10+ SOL or 1+ ETH
}

impl WalletTier {
    /// Multiplier for wallet tier
    pub fn multiplier(&self) -> f64 {
        match self {
            WalletTier::Minimum => 1.0,
            WalletTier::Mid => 1.5,
            WalletTier::High => 2.0,
        }
    }
}

/// GitHub user profile for eligibility verification
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GitHubProfile {
    pub login: String,
    pub id: u64,
    pub created_at: DateTime<Utc>,
    pub public_repos: u64,
    pub followers: u64,
}

/// GitHub contribution verification result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GitHubVerification {
    pub profile: GitHubProfile,
    pub tier: GitHubTier,
    pub starred_repos_count: u64,
    pub merged_prs_count: u64,
    pub has_star_king_badge: bool,
    pub is_miner: bool,
    pub account_age_days: u64,
}

/// Wallet verification result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WalletVerification {
    pub address: String,
    pub chain: TargetChain,
    pub balance_base_units: u64,
    pub wallet_age_seconds: u64,
    pub first_tx_timestamp: Option<DateTime<Utc>>,
    pub meets_minimum_balance: bool,
    pub meets_age_requirement: bool,
    pub tier: WalletTier,
}

/// Complete eligibility check result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EligibilityResult {
    pub eligible: bool,
    pub github: Option<GitHubVerification>,
    pub wallet: Option<WalletVerification>,
    pub base_allocation: u64,
    pub multiplier: f64,
    pub final_allocation: u64,
    pub rejection_reasons: Vec<String>,
}

impl EligibilityResult {
    /// Create a new eligibility result
    pub fn new(
        github: Option<GitHubVerification>,
        wallet: Option<WalletVerification>,
    ) -> Self {
        let mut rejection_reasons = Vec::new();
        let mut base_allocation = 0u64;
        let mut multiplier = 1.0f64;

        // Check GitHub eligibility
        if let Some(ref gh) = github {
            if gh.account_age_days < 30 {
                rejection_reasons.push(format!(
                    "GitHub account too young: {} days (minimum 30)",
                    gh.account_age_days
                ));
            } else {
                base_allocation = gh.tier.base_allocation();
            }
        } else {
            rejection_reasons.push("GitHub verification failed or not provided".to_string());
        }

        // Check wallet eligibility
        if let Some(ref w) = wallet {
            if !w.meets_minimum_balance {
                rejection_reasons.push(format!(
                    "Wallet balance too low: {} (minimum required)",
                    match w.chain {
                        TargetChain::Solana => "0.1 SOL",
                        TargetChain::Base => "0.01 ETH",
                    }
                ));
            }
            if !w.meets_age_requirement {
                rejection_reasons.push(format!(
                    "Wallet too young: {} days (minimum 7)",
                    w.wallet_age_seconds / 86400
                ));
            }
            if w.meets_minimum_balance && w.meets_age_requirement {
                multiplier = w.tier.multiplier();
            }
        } else {
            rejection_reasons.push("Wallet verification failed or not provided".to_string());
        }

        let final_allocation = (base_allocation as f64 * multiplier) as u64;
        let eligible = rejection_reasons.is_empty();

        EligibilityResult {
            eligible,
            github,
            wallet,
            base_allocation,
            multiplier,
            final_allocation,
            rejection_reasons,
        }
    }
}

/// Airdrop claim request
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClaimRequest {
    pub github_token: String,
    pub rtc_wallet: String,
    pub target_chain: TargetChain,
    pub target_address: String,
}

/// Airdrop claim response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClaimResponse {
    pub claim_id: String,
    pub status: ClaimStatus,
    pub github_login: String,
    pub target_chain: TargetChain,
    pub target_address: String,
    pub allocation: u64,
    pub lock_id: Option<String>,
    pub message: String,
    pub created_at: DateTime<Utc>,
}

/// Claim status
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum ClaimStatus {
    Pending,      // Awaiting admin review
    Verified,     // Eligibility verified, ready for bridge
    Bridging,     // Bridge lock in progress
    Complete,     // wRTC minted on target chain
    Rejected,     // Claim rejected
    Failed,       // Claim failed during processing
}

impl std::fmt::Display for ClaimStatus {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ClaimStatus::Pending => write!(f, "pending"),
            ClaimStatus::Verified => write!(f, "verified"),
            ClaimStatus::Bridging => write!(f, "bridging"),
            ClaimStatus::Complete => write!(f, "complete"),
            ClaimStatus::Rejected => write!(f, "rejected"),
            ClaimStatus::Failed => write!(f, "failed"),
        }
    }
}

/// Claim record stored in database
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClaimRecord {
    pub claim_id: String,
    pub github_login: String,
    pub github_id: u64,
    pub rtc_wallet: String,
    pub target_chain: TargetChain,
    pub target_address: String,
    pub status: ClaimStatus,
    pub base_allocation: u64,
    pub multiplier: f64,
    pub final_allocation: u64,
    pub lock_id: Option<String>,
    pub bridge_tx_hash: Option<String>,
    pub rejection_reason: Option<String>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

/// Airdrop statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AirdropStats {
    pub total_claims: u64,
    pub total_distributed: u64,
    pub claims_by_chain: ClaimsByChain,
    pub claims_by_tier: ClaimsByTier,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClaimsByChain {
    pub solana: u64,
    pub base: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClaimsByTier {
    pub stargazer: u64,
    pub contributor: u64,
    pub builder: u64,
    pub security: u64,
    pub core: u64,
    pub miner: u64,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_target_chain_from_str() {
        assert_eq!("solana".parse::<TargetChain>().unwrap(), TargetChain::Solana);
        assert_eq!("SOLANA".parse::<TargetChain>().unwrap(), TargetChain::Solana);
        assert_eq!("base".parse::<TargetChain>().unwrap(), TargetChain::Base);
        assert_eq!("BASE".parse::<TargetChain>().unwrap(), TargetChain::Base);
        assert!("ethereum".parse::<TargetChain>().is_err());
    }

    #[test]
    fn test_github_tier_allocation() {
        assert_eq!(GitHubTier::Stargazer.base_allocation(), 25);
        assert_eq!(GitHubTier::Contributor.base_allocation(), 50);
        assert_eq!(GitHubTier::Builder.base_allocation(), 100);
        assert_eq!(GitHubTier::Security.base_allocation(), 150);
        assert_eq!(GitHubTier::Core.base_allocation(), 200);
        assert_eq!(GitHubTier::Miner.base_allocation(), 100);
    }

    #[test]
    fn test_wallet_tier_multiplier() {
        assert_eq!(WalletTier::Minimum.multiplier(), 1.0);
        assert_eq!(WalletTier::Mid.multiplier(), 1.5);
        assert_eq!(WalletTier::High.multiplier(), 2.0);
    }

    #[test]
    fn test_eligibility_result_eligible() {
        let github = GitHubVerification {
            profile: GitHubProfile {
                login: "testuser".to_string(),
                id: 12345,
                created_at: Utc::now(),
                public_repos: 10,
                followers: 5,
            },
            tier: GitHubTier::Contributor,
            starred_repos_count: 15,
            merged_prs_count: 2,
            has_star_king_badge: false,
            is_miner: false,
            account_age_days: 60,
        };

        let wallet = WalletVerification {
            address: "test_address".to_string(),
            chain: TargetChain::Solana,
            balance_base_units: 200_000_000, // 0.2 SOL
            wallet_age_seconds: 10 * 86400,  // 10 days
            first_tx_timestamp: Some(Utc::now()),
            meets_minimum_balance: true,
            meets_age_requirement: true,
            tier: WalletTier::Minimum,
        };

        let result = EligibilityResult::new(Some(github), Some(wallet));
        assert!(result.eligible);
        assert_eq!(result.base_allocation, 50);
        assert_eq!(result.multiplier, 1.0);
        assert_eq!(result.final_allocation, 50);
        assert!(result.rejection_reasons.is_empty());
    }

    #[test]
    fn test_eligibility_result_ineligible() {
        let github = GitHubVerification {
            profile: GitHubProfile {
                login: "newuser".to_string(),
                id: 67890,
                created_at: Utc::now(),
                public_repos: 1,
                followers: 0,
            },
            tier: GitHubTier::Stargazer,
            starred_repos_count: 10,
            merged_prs_count: 0,
            has_star_king_badge: false,
            is_miner: false,
            account_age_days: 10, // Too young
        };

        let result = EligibilityResult::new(Some(github), None);
        assert!(!result.eligible);
        assert!(!result.rejection_reasons.is_empty());
    }
}
