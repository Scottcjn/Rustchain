//! RustChain Miner CLI
//!
//! Production-ready Rust miner with hardware attestation and RIP-PoA support.

use clap::Parser;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use tracing_subscriber::{fmt, prelude::*, EnvFilter};

use rustchain_miner::{Config, Miner};

/// RustChain Miner - Production-ready CLI with hardware attestation
#[derive(Parser, Debug)]
#[command(name = "rustchain-miner")]
#[command(author = "RustChain Contributors")]
#[command(version = env!("CARGO_PKG_VERSION"))]
#[command(about = "RustChain Miner with RIP-PoA hardware attestation", long_about = None)]
struct Args {
    /// Wallet address (auto-generated if not provided)
    #[arg(short = 'w', long = "wallet", env = "RUSTCHAIN_WALLET")]
    wallet: Option<String>,

    /// Custom miner ID (auto-generated if not provided)
    #[arg(short = 'm', long = "miner-id", env = "RUSTCHAIN_MINER_ID")]
    miner_id: Option<String>,

    /// Node URL
    #[arg(
        short = 'n',
        long = "node",
        env = "RUSTCHAIN_NODE_URL",
        default_value = "https://50.28.86.131"
    )]
    node: String,

    /// HTTP proxy URL for legacy systems
    #[arg(short = 'p', long = "proxy", env = "RUSTCHAIN_PROXY_URL")]
    proxy: Option<String>,

    /// Test mode: run preflight checks and output hardware fingerprint without actual mining
    #[arg(long = "dry-run", env = "RUSTCHAIN_DRY_RUN")]
    dry_run: bool,

    /// Enable verbose logging
    #[arg(short = 'v', long = "verbose", env = "RUSTCHAIN_VERBOSE")]
    verbose: bool,

    /// Block time in seconds
    #[arg(
        long = "block-time",
        env = "RUSTCHAIN_BLOCK_TIME",
        default_value = "600"
    )]
    block_time: u64,

    /// Attestation TTL in seconds
    #[arg(
        long = "attestation-ttl",
        env = "RUSTCHAIN_ATTESTATION_TTL",
        default_value = "580"
    )]
    attestation_ttl: u64,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();

    // Initialize logging
    let log_level = if args.verbose { "debug" } else { "info" };
    tracing_subscriber::registry()
        .with(fmt::layer())
        .with(EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new(log_level)))
        .init();

    // Load configuration from environment
    let mut config = Config::from_env()?;

    // Override with CLI args
    if let Some(wallet) = &args.wallet {
        config.wallet = Some(wallet.clone());
    }
    if let Some(miner_id) = &args.miner_id {
        config.miner_id = Some(miner_id.clone());
    }
    config.node_url = args.node;
    config.proxy_url = args.proxy;
    config.dry_run = args.dry_run;
    config.verbose = args.verbose;
    config.block_time_secs = args.block_time;
    config.attestation_ttl_secs = args.attestation_ttl;

    // Create miner (async)
    let miner = Miner::new(config).await?;

    // Setup Ctrl+C handler
    let shutdown_flag = Arc::new(AtomicBool::new(false));
    let shutdown_flag_clone = shutdown_flag.clone();

    tokio::spawn(async move {
        match tokio::signal::ctrl_c().await {
            Ok(()) => {
                println!("\n\n🛑 Shutdown signal received...");
                shutdown_flag_clone.store(true, Ordering::Relaxed);
            }
            Err(e) => {
                eprintln!("Error setting up Ctrl+C handler: {}", e);
            }
        }
    });

    // Store shutdown flag in miner (we need to modify Miner to support this)
    // For now, we'll just run the miner and let it handle signals internally

    // Run miner
    if let Err(e) = miner.run().await {
        eprintln!("❌ Miner error: {}", e);
        std::process::exit(1);
    }

    Ok(())
}
