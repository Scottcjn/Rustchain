//! RIP-305 Cross-Chain Airdrop CLI
//!
//! Command-line interface for verifying eligibility and submitting airdrop claims.

use clap::{Parser, Subcommand};
use cross_chain_airdrop::chain_adapter::{BaseAdapter, SolanaAdapter};
use cross_chain_airdrop::config::AirdropConfig;
use cross_chain_airdrop::github_verifier::GitHubVerifier;
use cross_chain_airdrop::models::{ClaimRequest, TargetChain};
use cross_chain_airdrop::pipeline::VerificationPipeline;
use cross_chain_airdrop::Result;
use std::sync::Arc;
use tracing::{info, Level};
use tracing_subscriber::FmtSubscriber;

#[derive(Parser)]
#[command(name = "airdrop-cli")]
#[command(author = "RustChain Contributors")]
#[command(version = cross_chain_airdrop::VERSION)]
#[command(about = "RIP-305 Cross-Chain Airdrop CLI", long_about = None)]
struct Cli {
    /// Enable verbose output
    #[arg(short, long, env = "VERBOSE")]
    verbose: bool,

    /// Dry-run mode (no actual claims submitted)
    #[arg(short, long, env = "DRY_RUN")]
    dry_run: bool,

    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Check airdrop eligibility
    Check {
        /// GitHub OAuth token
        #[arg(short, long, env = "GITHUB_TOKEN")]
        github_token: String,

        /// Target chain (solana or base)
        #[arg(short, long)]
        chain: String,

        /// Target wallet address
        #[arg(short, long)]
        address: String,
    },

    /// Submit an airdrop claim
    Claim {
        /// GitHub OAuth token
        #[arg(short, long, env = "GITHUB_TOKEN")]
        github_token: String,

        /// RustChain wallet name
        #[arg(short, long)]
        rtc_wallet: String,

        /// Target chain (solana or base)
        #[arg(short, long)]
        chain: String,

        /// Target wallet address
        #[arg(short, long)]
        address: String,
    },

    /// Show airdrop statistics
    Stats,

    /// Verify wallet address format
    VerifyAddress {
        /// Target chain (solana or base)
        #[arg(short, long)]
        chain: String,

        /// Wallet address to verify
        #[arg(short, long)]
        address: String,
    },
}

#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();

    // Initialize logging
    let log_level = if cli.verbose {
        Level::DEBUG
    } else {
        Level::INFO
    };
    let subscriber = FmtSubscriber::builder()
        .with_max_level(log_level)
        .with_target(false)
        .without_time()
        .finish();
    tracing::subscriber::set_global_default(subscriber)
        .expect("Failed to set tracing subscriber");

    // Load configuration
    let mut config = AirdropConfig::from_env()?;
    if cli.dry_run {
        config.dry_run = true;
    }
    if cli.verbose {
        config.verbose = true;
    }

    // Initialize components
    let github_verifier = GitHubVerifier::with_defaults(config.github_token.clone());
    let solana_adapter = Arc::new(SolanaAdapter::with_defaults(config.solana_rpc_url.clone()));
    let base_adapter = Arc::new(BaseAdapter::with_defaults(config.base_rpc_url.clone()));

    let pipeline = VerificationPipeline::new(
        github_verifier,
        vec![solana_adapter.clone(), base_adapter.clone()],
    );

    match cli.command {
        Commands::Check {
            github_token,
            chain,
            address,
        } => {
            let target_chain = parse_chain(&chain)?;
            info!("Checking eligibility for {} on {}", address, chain);

            let eligibility = pipeline
                .check_eligibility(&github_token, target_chain.clone(), &address)
                .await?;

            if eligibility.eligible {
                println!("✅ ELIGIBLE for airdrop!");
                println!(
                    "   Base allocation: {} wRTC",
                    eligibility.base_allocation
                );
                println!("   Wallet multiplier: {:.1}x", eligibility.multiplier);
                println!(
                    "   Final allocation: {} wRTC",
                    eligibility.final_allocation
                );

                if let Some(ref gh) = eligibility.github {
                    println!("   GitHub tier: {:?}", gh.tier);
                    println!("   Merged PRs: {}", gh.merged_prs_count);
                    println!("   Starred repos: {}", gh.starred_repos_count);
                }

                if let Some(ref w) = eligibility.wallet {
                    println!("   Wallet tier: {:?}", w.tier);
                    println!(
                        "   Balance: {} {}",
                        format_balance(&w.balance_base_units, &target_chain),
                        chain.to_uppercase()
                    );
                }
            } else {
                println!("❌ NOT ELIGIBLE for airdrop");
                println!("   Reasons:");
                for reason in &eligibility.rejection_reasons {
                    println!("   - {}", reason);
                }
            }
        }

        Commands::Claim {
            github_token,
            rtc_wallet,
            chain,
            address,
        } => {
            let target_chain = parse_chain(&chain)?;
            info!("Submitting claim for {} on {}", address, chain);

            if config.dry_run {
                println!("🔍 DRY RUN MODE - No claim will be submitted");
            }

            let request = ClaimRequest {
                github_token,
                rtc_wallet,
                target_chain,
                target_address: address,
            };

            match pipeline.process_claim(request).await {
                Ok(response) => {
                    println!("✅ Claim submitted successfully!");
                    println!("   Claim ID: {}", response.claim_id);
                    println!("   Status: {}", response.status);
                    println!(
                        "   Allocation: {} wRTC on {}",
                        response.allocation, response.target_chain
                    );
                    println!("   Message: {}", response.message);

                    if config.dry_run {
                        println!("\n⚠️  Dry run: Claim was not actually submitted");
                    }
                }
                Err(e) => {
                    println!("❌ Claim failed: {}", e);
                    return Err(e.into());
                }
            }
        }

        Commands::Stats => {
            let stats = pipeline.get_stats()?;
            println!("📊 Airdrop Statistics");
            println!("   Total claims: {}", stats.total_claims);
            println!("   Total distributed: {} wRTC", stats.total_distributed);
            println!("   Solana claims: {}", stats.claims_by_chain.solana);
            println!("   Base claims: {}", stats.claims_by_chain.base);
        }

        Commands::VerifyAddress { chain, address } => {
            let target_chain = parse_chain(&chain)?;
            let adapter = match target_chain {
                TargetChain::Solana => solana_adapter.as_ref() as &dyn cross_chain_airdrop::chain_adapter::ChainAdapter,
                TargetChain::Base => base_adapter.as_ref() as &dyn cross_chain_airdrop::chain_adapter::ChainAdapter,
            };

            match adapter.validate_address(&address) {
                Ok(_) => {
                    println!("✅ Valid {} address: {}", chain, address);

                    // Also check balance and age
                    match adapter.verify_wallet(&address).await {
                        Ok(verification) => {
                            println!("   Balance: {} {}",
                                format_balance(&verification.balance_base_units, &target_chain),
                                chain.to_uppercase());
                            println!("   Wallet age: {} days", verification.wallet_age_seconds / 86400);
                            println!("   Meets minimum balance: {}", verification.meets_minimum_balance);
                            println!("   Meets age requirement: {}", verification.meets_age_requirement);
                            println!("   Wallet tier: {:?}", verification.tier);
                        }
                        Err(e) => {
                            println!("⚠️  Could not verify wallet details: {}", e);
                        }
                    }
                }
                Err(e) => {
                    println!("❌ Invalid {} address: {}", chain, address);
                    println!("   Error: {}", e);
                }
            }
        }
    }

    Ok(())
}

fn parse_chain(chain: &str) -> Result<TargetChain> {
    chain.parse::<TargetChain>().map_err(|e| {
        cross_chain_airdrop::AirdropError::Parse(format!("Invalid chain: {}", e))
    })
}

fn format_balance(balance_base_units: &u64, chain: &TargetChain) -> String {
    match chain {
        TargetChain::Solana => {
            // SOL has 9 decimals
            format!("{:.9}", *balance_base_units as f64 / 1_000_000_000.0)
        }
        TargetChain::Base => {
            // ETH has 18 decimals
            format!("{:.18}", *balance_base_units as f64 / 1_000_000_000_000_000_000.0)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_chain() {
        assert_eq!(parse_chain("solana").unwrap(), TargetChain::Solana);
        assert_eq!(parse_chain("SOLANA").unwrap(), TargetChain::Solana);
        assert_eq!(parse_chain("base").unwrap(), TargetChain::Base);
        assert_eq!(parse_chain("BASE").unwrap(), TargetChain::Base);
        assert!(parse_chain("ethereum").is_err());
    }

    #[test]
    fn test_format_balance_solana() {
        let chain = TargetChain::Solana;
        assert_eq!(format_balance(&100_000_000, &chain), "0.100000000");
        assert_eq!(format_balance(&1_000_000_000, &chain), "1.000000000");
    }

    #[test]
    fn test_format_balance_base() {
        let chain = TargetChain::Base;
        assert_eq!(
            format_balance(&10_000_000_000_000_000, &chain),
            "0.010000000000000000"
        );
        assert_eq!(
            format_balance(&1_000_000_000_000_000_000, &chain),
            "1.000000000000000000"
        );
    }
}
