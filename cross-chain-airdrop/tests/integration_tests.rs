//! Integration tests for RIP-305 Cross-Chain Airdrop

use cross_chain_airdrop::chain_adapter::{BaseAdapter, ChainAdapter, SolanaAdapter};
use cross_chain_airdrop::config::AirdropConfig;
use cross_chain_airdrop::github_verifier::GitHubVerifier;
use cross_chain_airdrop::models::{
    ClaimRequest, EligibilityResult, GitHubProfile, GitHubTier, GitHubVerification, TargetChain,
    WalletTier, WalletVerification,
};
use cross_chain_airdrop::pipeline::VerificationPipeline;
use std::sync::Arc;

/// Test helper: Create a mock GitHub verification
fn mock_github_verification(tier: GitHubTier, account_age_days: u64) -> GitHubVerification {
    let tier_clone = tier.clone();
    GitHubVerification {
        profile: GitHubProfile {
            login: "testuser".to_string(),
            id: 12345,
            created_at: chrono::Utc::now(),
            public_repos: 10,
            followers: 5,
        },
        tier,
        starred_repos_count: match tier_clone {
            GitHubTier::Stargazer => 15,
            _ => 5,
        },
        merged_prs_count: match tier_clone {
            GitHubTier::Contributor => 1,
            GitHubTier::Builder => 3,
            GitHubTier::Core => 5,
            _ => 0,
        },
        has_star_king_badge: false,
        is_miner: false,
        account_age_days,
    }
}

/// Test helper: Create a mock wallet verification
fn mock_wallet_verification(
    chain: TargetChain,
    balance_base_units: u64,
    age_seconds: u64,
) -> WalletVerification {
    let meets_balance = match chain {
        TargetChain::Solana => balance_base_units >= 100_000_000, // 0.1 SOL
        TargetChain::Base => balance_base_units >= 10_000_000_000_000_000, // 0.01 ETH
    };
    let meets_age = age_seconds >= 7 * 24 * 60 * 60; // 7 days

    let tier = match chain {
        TargetChain::Solana => {
            if balance_base_units >= 10_000_000_000 {
                WalletTier::High
            } else if balance_base_units >= 1_000_000_000 {
                WalletTier::Mid
            } else {
                WalletTier::Minimum
            }
        }
        TargetChain::Base => {
            if balance_base_units >= 1_000_000_000_000_000_000 {
                WalletTier::High
            } else if balance_base_units >= 100_000_000_000_000_000 {
                WalletTier::Mid
            } else {
                WalletTier::Minimum
            }
        }
    };

    WalletVerification {
        address: "test_address".to_string(),
        chain: chain.clone(),
        balance_base_units,
        wallet_age_seconds: age_seconds,
        first_tx_timestamp: None,
        meets_minimum_balance: meets_balance,
        meets_age_requirement: meets_age,
        tier,
    }
}

#[test]
fn test_eligibility_both_chains_eligible() {
    // Test Solana eligibility
    let github = mock_github_verification(GitHubTier::Contributor, 60);
    let wallet = mock_wallet_verification(TargetChain::Solana, 200_000_000, 10 * 86400);

    let result = EligibilityResult::new(Some(github.clone()), Some(wallet));
    assert!(result.eligible);
    assert_eq!(result.base_allocation, 50);
    assert_eq!(result.multiplier, 1.0);
    assert_eq!(result.final_allocation, 50);

    // Test Base eligibility
    let wallet_base = mock_wallet_verification(TargetChain::Base, 20_000_000_000_000_000, 14 * 86400);
    let result_base = EligibilityResult::new(Some(github), Some(wallet_base));
    assert!(result_base.eligible);
    assert_eq!(result_base.final_allocation, 50);
}

#[test]
fn test_eligibility_young_github_account() {
    let github = mock_github_verification(GitHubTier::Contributor, 15); // Too young
    let wallet = mock_wallet_verification(TargetChain::Solana, 200_000_000, 10 * 86400);

    let result = EligibilityResult::new(Some(github), Some(wallet));
    assert!(!result.eligible);
    assert!(result
        .rejection_reasons
        .iter()
        .any(|r| r.contains("GitHub account too young")));
}

#[test]
fn test_eligibility_low_wallet_balance() {
    let github = mock_github_verification(GitHubTier::Contributor, 60);
    let wallet = mock_wallet_verification(TargetChain::Solana, 50_000_000, 10 * 86400); // 0.05 SOL, too low

    let result = EligibilityResult::new(Some(github), Some(wallet));
    assert!(!result.eligible);
    assert!(result
        .rejection_reasons
        .iter()
        .any(|r| r.contains("Wallet balance too low")));
}

#[test]
fn test_eligibility_young_wallet() {
    let github = mock_github_verification(GitHubTier::Contributor, 60);
    let wallet = mock_wallet_verification(TargetChain::Base, 20_000_000_000_000_000, 3 * 86400); // 3 days, too young

    let result = EligibilityResult::new(Some(github), Some(wallet));
    assert!(!result.eligible);
    assert!(result
        .rejection_reasons
        .iter()
        .any(|r| r.contains("Wallet too young")));
}

#[test]
fn test_wallet_multiplier_mid_tier() {
    let github = mock_github_verification(GitHubTier::Builder, 60);
    // 5 SOL = mid tier
    let wallet = mock_wallet_verification(TargetChain::Solana, 5_000_000_000, 10 * 86400);

    let result = EligibilityResult::new(Some(github), Some(wallet));
    assert!(result.eligible);
    assert_eq!(result.base_allocation, 100);
    assert_eq!(result.multiplier, 1.5);
    assert_eq!(result.final_allocation, 150);
}

#[test]
fn test_wallet_multiplier_high_tier() {
    let github = mock_github_verification(GitHubTier::Core, 60);
    // 50 SOL = high tier
    let wallet = mock_wallet_verification(TargetChain::Solana, 50_000_000_000, 10 * 86400);

    let result = EligibilityResult::new(Some(github), Some(wallet));
    assert!(result.eligible);
    assert_eq!(result.base_allocation, 200);
    assert_eq!(result.multiplier, 2.0);
    assert_eq!(result.final_allocation, 400);
}

#[tokio::test]
async fn test_chain_adapters_validate_addresses() {
    let solana_adapter = SolanaAdapter::with_defaults("https://api.mainnet-beta.solana.com".to_string());
    let base_adapter = BaseAdapter::with_defaults("https://mainnet.base.org".to_string());

    // Valid addresses
    assert!(solana_adapter
        .validate_address("7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU")
        .is_ok());
    assert!(base_adapter
        .validate_address("0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1")
        .is_ok());

    // Invalid addresses
    assert!(solana_adapter.validate_address("invalid").is_err());
    assert!(base_adapter.validate_address("invalid").is_err());
    assert!(base_adapter.validate_address("0xGGGG").is_err());
}

#[tokio::test]
async fn test_chain_adapters_calculate_tiers() {
    let solana_adapter = SolanaAdapter::with_defaults("https://api.mainnet-beta.solana.com".to_string());
    let base_adapter = BaseAdapter::with_defaults("https://mainnet.base.org".to_string());

    // Solana tiers
    assert_eq!(
        solana_adapter.calculate_tier(50_000_000),
        WalletTier::Minimum
    );
    assert_eq!(
        solana_adapter.calculate_tier(500_000_000),
        WalletTier::Minimum
    );
    assert_eq!(solana_adapter.calculate_tier(5_000_000_000), WalletTier::Mid);
    assert_eq!(
        solana_adapter.calculate_tier(50_000_000_000),
        WalletTier::High
    );

    // Base tiers
    assert_eq!(
        base_adapter.calculate_tier(5_000_000_000_000_000),
        WalletTier::Minimum
    );
    assert_eq!(
        base_adapter.calculate_tier(50_000_000_000_000_000),
        WalletTier::Minimum
    );
    assert_eq!(
        base_adapter.calculate_tier(500_000_000_000_000_000),
        WalletTier::Mid
    );
    assert_eq!(
        base_adapter.calculate_tier(5_000_000_000_000_000_000),
        WalletTier::High
    );
}

#[test]
fn test_github_tier_allocations() {
    assert_eq!(GitHubTier::Stargazer.base_allocation(), 25);
    assert_eq!(GitHubTier::Contributor.base_allocation(), 50);
    assert_eq!(GitHubTier::Builder.base_allocation(), 100);
    assert_eq!(GitHubTier::Security.base_allocation(), 150);
    assert_eq!(GitHubTier::Core.base_allocation(), 200);
    assert_eq!(GitHubTier::Miner.base_allocation(), 100);
}

#[test]
fn test_target_chain_parsing() {
    assert_eq!("solana".parse::<TargetChain>().unwrap(), TargetChain::Solana);
    assert_eq!("SOLANA".parse::<TargetChain>().unwrap(), TargetChain::Solana);
    assert_eq!("Solana".parse::<TargetChain>().unwrap(), TargetChain::Solana);
    assert_eq!("base".parse::<TargetChain>().unwrap(), TargetChain::Base);
    assert_eq!("BASE".parse::<TargetChain>().unwrap(), TargetChain::Base);
    assert_eq!("Base".parse::<TargetChain>().unwrap(), TargetChain::Base);
    assert!("ethereum".parse::<TargetChain>().is_err());
    assert!("btc".parse::<TargetChain>().is_err());
}

#[test]
fn test_config_defaults() {
    let config = AirdropConfig::default();
    assert_eq!(config.min_wallet_age_seconds, 7 * 24 * 60 * 60);
    assert_eq!(config.min_github_age_seconds, 30 * 24 * 60 * 60);
    assert_eq!(config.min_sol_lamports, 100_000_000);
    assert_eq!(config.min_eth_wei, 10_000_000_000_000_000);
    assert!(!config.dry_run);
    assert!(!config.verbose);
}

#[tokio::test]
async fn test_pipeline_initialization() {
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
    assert_eq!(stats.total_distributed, 0);
}
