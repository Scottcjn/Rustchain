pub mod models;

use models::{BonusType, Claim, ClaimResult, WalletId};
use std::collections::HashSet;

/// Represents the bonus program state.
pub struct BonusProgram {
    /// Set of wallets that have already claimed a non-stackable bonus.
    claimed_non_stackable: HashSet<WalletId>,
    /// Simulated database for past claims.
    claims: Vec<ClaimResult>,
}

impl BonusProgram {
    pub fn new() -> Self {
        BonusProgram {
            claimed_non_stackable: HashSet::new(),
            claims: Vec::new(),
        }
    }

    /// Process a single claim.
    pub fn process_claim(&mut self, claim: Claim) -> ClaimResult {
        let base = claim.bonus_type.base_amount();

        // Check for duplicate non-stackable bonuses per wallet
        if !claim.bonus_type.stackable() {
            if self.claimed_non_stackable.contains(&claim.wallet_id) {
                return ClaimResult {
                    wallet_id: claim.wallet_id.clone(),
                    bonus_type: claim.bonus_type.clone(),
                    amount: 0,
                    success: false,
                    message: format!("Non-stackable bonus {:?} already claimed for wallet {}", claim.bonus_type, claim.wallet_id),
                };
            }
            self.claimed_non_stackable.insert(claim.wallet_id.clone());
        }

        // Validate proof (simplified - real implementation would check attestation or PR)
        if claim.proof.is_empty() {
            return ClaimResult {
                wallet_id: claim.wallet_id.clone(),
                bonus_type: claim.bonus_type.clone(),
                amount: 0,
                success: false,
                message: "Proof is required".to_string(),
            };
        }

        // Applicable only for vintage/hardware bonuses: require miner_id
        match &claim.bonus_type {
            BonusType::RealHardware | BonusType::VintageHardware => {
                if claim.miner_id.is_none() {
                    return ClaimResult {
                        wallet_id: claim.wallet_id.clone(),
                        bonus_type: claim.bonus_type.clone(),
                        amount: 0,
                        success: false,
                        message: "Miner ID required for this bonus".to_string(),
                    };
                }
            }
            _ => {}
        }

        // All checks passed, reward
        let result = ClaimResult {
            wallet_id: claim.wallet_id.clone(),
            bonus_type: claim.bonus_type.clone(),
            amount: base,
            success: true,
            message: format!("Awarded {} RTC for {:?}", base, claim.bonus_type),
        };
        self.claims.push(result.clone());
        result
    }

    /// Calculate total bonus for a wallet (stacking allowed).
    pub fn total_for_wallet(&self, wallet: &WalletId) -> u64 {
        self.claims.iter()
            .filter(|c| c.wallet_id == *wallet && c.success)
            .map(|c| c.amount)
            .sum()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_first_attestation_bonus() {
        let mut program = BonusProgram::new();
        let claim = Claim {
            wallet_id: "wallet1".to_string(),
            miner_id: Some("miner1".to_string()),
            bonus_type: BonusType::FirstAttestation,
            proof: "attestation_hash".to_string(),
        };
        let result = program.process_claim(claim);
        assert!(result.success);
        assert_eq!(result.amount, 10);
    }

    #[test]
    fn test_vintage_hardware_bonus() {
        let mut program = BonusProgram::new();
        let claim = Claim {
            wallet_id: "wallet2".to_string(),
            miner_id: Some("miner2".to_string()),
            bonus_type: BonusType::VintageHardware,
            proof: "vintage".to_string(),
        };
        let result = program.process_claim(claim);
        assert!(result.success);
        assert_eq!(result.amount, 10);
    }

    #[test]
    fn test_duplicate_non_stackable() {
        let mut program = BonusProgram::new();
        let claim1 = Claim {
            wallet_id: "wallet3".to_string(),
            miner_id: None,
            bonus_type: BonusType::FirstPrMerged,
            proof: "pr_url".to_string(),
        };
        let claim2 = Claim {
            wallet_id: "wallet3".to_string(),
            miner_id: None,
            bonus_type: BonusType::FirstPrMerged,
            proof: "pr_url2".to_string(),
        };
        let r1 = program.process_claim(claim1);
        assert!(r1.success);
        let r2 = program.process_claim(claim2);
        assert!(!r2.success);
    }

    #[test]
    fn test_stacking() {
        let mut program = BonusProgram::new();
        let claim1 = Claim {
            wallet_id: "wallet4".to_string(),
            miner_id: Some("miner4".to_string()),
            bonus_type: BonusType::FirstAttestation,
            proof: "attest1".to_string(),
        };
        let claim2 = Claim {
            wallet_id: "wallet4".to_string(),
            miner_id: Some("miner4".to_string()),
            bonus_type: BonusType::VintageHardware,
            proof: "vintage".to_string(),
        };
        program.process_claim(claim1);
        program.process_claim(claim2);
        assert_eq!(program.total_for_wallet(&"wallet4".to_string()), 20); // 10 + 10
    }
}
