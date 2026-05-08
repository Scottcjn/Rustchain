//! Verification pipeline for cross-chain airdrop claims

use crate::chain_adapter::ChainAdapter;
use crate::claim_store::{ClaimStore, InMemoryClaimStore};
use crate::error::{AirdropError, Result};
use crate::github_verifier::GitHubVerifier;
use crate::models::{
    ClaimRecord, ClaimRequest, ClaimResponse, ClaimStatus, EligibilityResult, TargetChain,
};
use chrono::Utc;
use std::sync::Arc;
use uuid::Uuid;

/// Verification pipeline for processing airdrop claims.
///
/// The `S` type parameter controls where deduplication state is stored.
/// By default an [`InMemoryClaimStore`] is used (volatile — state is lost
/// on restart).  For production deployments pass a durable store such as
/// [`SqliteClaimStore`](crate::SqliteClaimStore) so that duplicate claims
/// are rejected even after the process restarts.
pub struct VerificationPipeline<S = InMemoryClaimStore> {
    github_verifier: GitHubVerifier,
    chain_adapters: Vec<Arc<dyn ChainAdapter>>,
    store: S,
}

impl VerificationPipeline<InMemoryClaimStore> {
    /// Create a pipeline with the default in-memory claim store.
    ///
    /// **Warning:** the in-memory store loses all deduplication state on
    /// process restart, allowing the same GitHub account or wallet to
    /// claim again.  Use [`VerificationPipeline::with_store`] with a
    /// persistent [`ClaimStore`] for production use.
    pub fn new(
        github_verifier: GitHubVerifier,
        chain_adapters: Vec<Arc<dyn ChainAdapter>>,
    ) -> Self {
        Self::with_store(github_verifier, chain_adapters, InMemoryClaimStore::new())
    }
}

impl<S: ClaimStore> VerificationPipeline<S> {
    /// Create a pipeline with a custom claim store.
    ///
    /// Use this to plug in a persistent store (e.g. SQLite) so that
    /// duplicate-claim prevention survives process restarts.
    pub fn with_store(
        github_verifier: GitHubVerifier,
        chain_adapters: Vec<Arc<dyn ChainAdapter>>,
        store: S,
    ) -> Self {
        Self {
            github_verifier,
            chain_adapters,
            store,
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

        // Step 2: Check for duplicate GitHub account (via store)
        if self
            .store
            .is_github_claimed(github_verification.profile.id)?
        {
            return Err(AirdropError::Claim(format!(
                "GitHub account {} has already claimed airdrop",
                github_verification.profile.login
            )));
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

        // Step 5: Check for duplicate wallet (via store)
        let chain_str = request.target_chain.to_string();
        if self
            .store
            .is_wallet_claimed(&chain_str, &request.target_address)?
        {
            return Err(AirdropError::Claim(format!(
                "Wallet {} on {} has already claimed airdrop",
                request.target_address, request.target_chain
            )));
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

        // Step 7: Record the claim as pending (atomically checks + inserts)
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

        self.store.record_claim(
            github_verification.profile.id,
            &chain_str,
            &request.target_address,
            claim_record.clone(),
        )?;

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
        self.store.get_claims()
    }

    /// Get claim by ID
    pub fn get_claim(&self, claim_id: &str) -> Result<Option<ClaimRecord>> {
        self.store.get_claim(claim_id)
    }

    /// Update claim status
    pub fn update_claim_status(
        &self,
        claim_id: &str,
        status: ClaimStatus,
        lock_id: Option<String>,
        rejection_reason: Option<String>,
    ) -> Result<()> {
        self.store
            .update_claim(claim_id, status, lock_id, rejection_reason)
    }

    /// Get statistics
    pub fn get_stats(&self) -> Result<AirdropStats> {
        let claims = self.store.get_claims()?;

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
            claims_by_tier: ClaimsByTier::default(),
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
    use crate::chain_adapter::{BaseAdapter, SolanaAdapter};
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

        let pipeline =
            VerificationPipeline::new(github_verifier, vec![solana_adapter, base_adapter]);

        let stats = pipeline.get_stats().unwrap();
        assert_eq!(stats.total_claims, 0);
    }
}
