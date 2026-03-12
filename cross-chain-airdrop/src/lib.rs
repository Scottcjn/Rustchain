//! RIP-305 Cross-Chain Airdrop Library
//!
//! This crate implements the core logic for the RIP-305 Cross-Chain Airdrop Protocol,
//! enabling wRTC distribution on Solana and Base L2 with anti-Sybil verification.
//!
//! # Features
//!
//! - **GitHub Verification**: Verify contributor tier based on stars, PRs, and badges
//! - **Wallet Verification**: Check balance and age requirements on Solana/Base
//! - **Chain Adapters**: Pluggable adapters for different blockchain RPCs
//! - **Bridge Integration**: Lock RTC and mint wRTC on target chains
//! - **Anti-Sybil**: Prevent duplicate claims and bot farms
//!
//! # Example
//!
//! ```rust,no_run
//! use cross_chain_airdrop::{Config, GitHubVerifier, VerificationPipeline};
//! use cross_chain_airdrop::chain_adapter::{SolanaAdapter, BaseAdapter};
//! use cross_chain_airdrop::models::TargetChain;
//! use std::sync::Arc;
//!
//! #[tokio::main]
//! async fn main() -> cross_chain_airdrop::Result<()> {
//!     // Load configuration
//!     let config = Config::from_env()?;
//!
//!     // Initialize verifiers
//!     let github_verifier = GitHubVerifier::with_defaults(config.github_token.clone());
//!     let solana_adapter = Arc::new(SolanaAdapter::with_defaults(config.solana_rpc_url.clone()));
//!     let base_adapter = Arc::new(BaseAdapter::with_defaults(config.base_rpc_url.clone()));
//!
//!     // Create verification pipeline
//!     let pipeline = VerificationPipeline::new(
//!         github_verifier,
//!         vec![solana_adapter, base_adapter],
//!     );
//!
//!     // Check eligibility (you would provide actual tokens and addresses)
//!     let github_oauth_token = "gho_...";
//!     let solana_wallet_address = "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU";
//!     
//!     let eligibility = pipeline.check_eligibility(
//!         &github_oauth_token,
//!         TargetChain::Solana,
//!         &solana_wallet_address,
//!     ).await?;
//!
//!     if eligibility.eligible {
//!         println!("Eligible for {} wRTC!", eligibility.final_allocation);
//!     }
//!
//!     Ok(())
//! }
//! ```

pub mod bridge_client;
pub mod chain_adapter;
pub mod config;
pub mod error;
pub mod github_verifier;
pub mod models;
pub mod pipeline;

// Re-export commonly used types
pub use config::AirdropConfig as Config;
pub use error::{AirdropError, Result};
pub use github_verifier::GitHubVerifier;
pub use models::{
    ClaimRecord, ClaimRequest, ClaimResponse, ClaimStatus, EligibilityResult, GitHubProfile,
    GitHubTier, GitHubVerification, TargetChain, WalletTier, WalletVerification,
};
pub use pipeline::VerificationPipeline;

/// Library version
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// RIP-305 specification reference
pub const RIP_305_SPEC: &str = "https://github.com/Scottcjn/Rustchain/blob/main/docs/RIP-305-cross-chain-airdrop.md";
