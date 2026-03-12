//! Verification pipeline for cross-chain airdrop claims

use crate::chain_adapter::ChainAdapter;
use crate::error::{AirdropError, Result};
use crate::github_verifier::GitHubVerifier;
use crate::models::{
    ClaimRecord, ClaimRequest, ClaimResponse, ClaimStatus, EligibilityResult, TargetChain,
};
use chrono::Utc;
use std::collections::HashSet;
use std::sync::{Arc, Mutex};
use uuid::Uuid;

/// Verification pipeline for processing airdrop claims
pub struct VerificationPipeline {
    github_verifier: GitHubVerifier,
    chain_adapters: Vec<Arc<dyn ChainAdapter>>,
    /// In-memory claim store (would be database in production)
    claims: Arc<Mutex<Vec<ClaimRecord>>>,
    /// Track claimed GitHub accounts to prevent duplicates
    claimed_github_ids: Arc<Mutex<HashSet<u64>>>,
    /// Track claimed wallet addresses to prevent duplicates
    claimed_wallets: Arc<Mutex<HashSet<String>>>,
}

impl VerificationPipeline {
    pub fn new(
        github_verifier: GitHubVerifier,
        chain_adapters: Vec<Arc<dyn ChainAdapter>>,
    ) -> Self {
        Self {
            github_verifier,
            chain_adapters,
            claims: Arc::new(Mutex::new(Vec::new())),
            claimed_github_ids: Arc::new(Mutex::new(HashSet::new())),
            claimed_wallets: Arc::new(Mutex::new(HashSet::new())),
        }
    }

    /// Process a complete airdrop claim
    pub async fn process_claim(&self, request: ClaimRequest) -> Result<ClaimResponse> {
        let claim_id = Uuid::new_v4().to_string();
        let now = Utc::now();

        // Step 1: Verify GitHub account
        let github_verification = self
            .github_verifier
            .verify(&request.github_token)
            .await
            .map_err(|e| AirdropError::Claim(format!("GitHub verification failed: {}", e)))?;

        // Step 2: Check for duplicate GitHub account
        {
            let mut claimed = self.claimed_github_ids.lock().map_err(|e| {
                AirdropError::Claim(format!("Lock poisoning: {}", e))
            })?;
            if claimed.contains(&github_verification.profile.id) {
                return Err(AirdropError::Claim(format!(
                    "GitHub account {} has already claimed airdrop",
                    github_verification.profile.login
                )));
            }
        }

        // Step 3: Find appropriate chain adapter
        let chain_adapter = self
            .chain_adapters
            .iter()
            .find(|a| a.chain() == request.target_chain)
            .ok_or_else(|| {
                AirdropError::Claim(format!("No adapter for chain: {}", request.target_chain))
            })?;

        // Step 4: Verify wallet
        let wallet_verification = chain_adapter
            .verify_wallet(&request.target_address)
            .await
            .map_err(|e| AirdropError::Claim(format!("Wallet verification failed: {}", e)))?;

        // Step 5: Check for duplicate wallet
        {
            let claimed = self.claimed_wallets.lock().map_err(|e| {
                AirdropError::Claim(format!("Lock poisoning: {}", e))
            })?;
            let wallet_key = format!("{}:{}", request.target_chain, request.target_address);
            if claimed.contains(&wallet_key) {
                return Err(AirdropError::Claim(format!(
                    "Wallet {} on {} has already claimed airdrop",
                    request.target_address, request.target_chain
                )));
            }
        }

        // Step 6: Calculate eligibility
        let eligibility = EligibilityResult::new(
            Some(github_verification.clone()),
            Some(wallet_verification.clone()),
        );

        if !eligibility.eligible {
            return Err(AirdropError::Eligibility(format!(
                "Claim ineligible: {}",
                eligibility.rejection_reasons.join(", ")
            )));
        }

        // Step 7: Record the claim as pending
        let claim_record = ClaimRecord {
            claim_id: claim_id.clone(),
            github_login: github_verification.profile.login.clone(),
            github_id: github_verification.profile.id,
            rtc_wallet: request.rtc_wallet.clone(),
            target_chain: request.target_chain.clone(),
            target_address: request.target_address.clone(),
            status: ClaimStatus::Pending,
            base_allocation: github_verification.tier.base_allocation(),
            multiplier: wallet_verification.tier.multiplier(),
            final_allocation: eligibility.final_allocation,
            lock_id: None,
            bridge_tx_hash: None,
            rejection_reason: None,
            created_at: now,
            updated_at: now,
        };

        // Store claim and mark as claimed
        {
            let mut claims = self.claims.lock().map_err(|e| {
                AirdropError::Claim(format!("Lock poisoning: {}", e))
            })?;
            claims.push(claim_record.clone());
        }

        {
            let mut claimed_github = self.claimed_github_ids.lock().map_err(|e| {
                AirdropError::Claim(format!("Lock poisoning: {}", e))
            })?;
            claimed_github.insert(github_verification.profile.id);
        }

        {
            let mut claimed_wallets = self.claimed_wallets.lock().map_err(|e| {
                AirdropError::Claim(format!("Lock poisoning: {}", e))
            })?;
            claimed_wallets.insert(format!(
                "{}:{}",
                request.target_chain, request.target_address
            ));
        }

        let target_chain_str = request.target_chain.to_string();
        
        Ok(ClaimResponse {
            claim_id,
            status: ClaimStatus::Pending,
            github_login: github_verification.profile.login,
            target_chain: request.target_chain,
            target_address: request.target_address,
            allocation: eligibility.final_allocation,
            lock_id: None,
            message: format!(
                "Claim submitted successfully. Eligible for {} wRTC on {}",
                eligibility.final_allocation, target_chain_str
            ),
            created_at: now,
        })
    }

    /// Verify eligibility without submitting claim
    pub async fn check_eligibility(
        &self,
        github_token: &str,
        target_chain: TargetChain,
        target_address: &str,
    ) -> Result<EligibilityResult> {
        // Verify GitHub
        let github_verification = match self.github_verifier.verify(github_token).await {
            Ok(v) => Some(v),
            Err(_) => None,
        };

        // Find chain adapter
        let chain_adapter = self
            .chain_adapters
            .iter()
            .find(|a| a.chain() == target_chain)
            .ok_or_else(|| {
                AirdropError::Claim(format!("No adapter for chain: {}", target_chain))
            })?;

        // Verify wallet
        let wallet_verification = match chain_adapter.verify_wallet(target_address).await {
            Ok(v) => Some(v),
            Err(_) => None,
        };

        Ok(EligibilityResult::new(
            github_verification,
            wallet_verification,
        ))
    }

    /// Get all claims
    pub fn get_claims(&self) -> Result<Vec<ClaimRecord>> {
        let claims = self
            .claims
            .lock()
            .map_err(|e| AirdropError::Claim(format!("Lock poisoning: {}", e)))?;
        Ok(claims.clone())
    }

    /// Get claim by ID
    pub fn get_claim(&self, claim_id: &str) -> Result<Option<ClaimRecord>> {
        let claims = self
            .claims
            .lock()
            .map_err(|e| AirdropError::Claim(format!("Lock poisoning: {}", e)))?;
        Ok(claims.iter().find(|c| c.claim_id == claim_id).cloned())
    }

    /// Update claim status
    pub fn update_claim_status(
        &self,
        claim_id: &str,
        status: ClaimStatus,
        lock_id: Option<String>,
        rejection_reason: Option<String>,
    ) -> Result<()> {
        let mut claims = self
            .claims
            .lock()
            .map_err(|e| AirdropError::Claim(format!("Lock poisoning: {}", e)))?;

        if let Some(claim) = claims.iter_mut().find(|c| c.claim_id == claim_id) {
            claim.status = status;
            claim.updated_at = Utc::now();
            if let Some(lid) = lock_id {
                claim.lock_id = Some(lid);
            }
            claim.rejection_reason = rejection_reason;
            Ok(())
        } else {
            Err(AirdropError::Claim(format!("Claim not found: {}", claim_id)))
        }
    }

    /// Get statistics
    pub fn get_stats(&self) -> Result<AirdropStats> {
        let claims = self
            .claims
            .lock()
            .map_err(|e| AirdropError::Claim(format!("Lock poisoning: {}", e)))?;

        let total_claims = claims.len() as u64;
        let total_distributed: u64 = claims
            .iter()
            .filter(|c| c.status == ClaimStatus::Complete)
            .map(|c| c.final_allocation)
            .sum();

        let solana_claims = claims
            .iter()
            .filter(|c| c.target_chain == TargetChain::Solana)
            .count() as u64;
        let base_claims = claims
            .iter()
            .filter(|c| c.target_chain == TargetChain::Base)
            .count() as u64;

        Ok(AirdropStats {
            total_claims,
            total_distributed,
            claims_by_chain: ClaimsByChain {
                solana: solana_claims,
                base: base_claims,
            },
            claims_by_tier: ClaimsByTier::default(), // Would need tier tracking
        })
    }
}

/// Airdrop statistics
#[derive(Debug, Clone)]
pub struct AirdropStats {
    pub total_claims: u64,
    pub total_distributed: u64,
    pub claims_by_chain: ClaimsByChain,
    pub claims_by_tier: ClaimsByTier,
}

#[derive(Debug, Clone, Default)]
pub struct ClaimsByChain {
    pub solana: u64,
    pub base: u64,
}

#[derive(Debug, Clone, Default)]
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
    use crate::chain_adapter::{SolanaAdapter, BaseAdapter};
    use std::sync::Arc;

    #[tokio::test]
    async fn test_pipeline_creation() {
        let github_verifier = GitHubVerifier::with_defaults(None);
        let solana_adapter = Arc::new(SolanaAdapter::with_defaults(
            "https://api.mainnet-beta.solana.com".to_string(),
        ));
        let base_adapter = Arc::new(BaseAdapter::with_defaults(
            "https://mainnet.base.org".to_string(),
        ));

        let pipeline = VerificationPipeline::new(
            github_verifier,
            vec![solana_adapter, base_adapter],
        );

        let stats = pipeline.get_stats().unwrap();
        assert_eq!(stats.total_claims, 0);
    }
}
