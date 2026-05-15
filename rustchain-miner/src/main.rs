//! RustChain Miner CLI
//!
//! Production-ready Rust miner with hardware attestation and RIP-PoA support.

use clap::Parser;
use std::path::PathBuf;
use std::sync::atomic::Ordering;
use tracing_subscriber::{fmt, prelude::*, EnvFilter};

use rustchain_miner::{export_state, import_state, Config, Miner};

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

    /// Export local miner state to a portable JSON backup and exit
    #[arg(
        long = "export-state",
        conflicts_with = "import_state",
        requires = "output"
    )]
    export_state: bool,

    /// Backup file to write when using --export-state
    #[arg(long = "output", value_name = "FILE")]
    output: Option<PathBuf>,

    /// Import miner state from a JSON backup before starting
    #[arg(
        long = "import-state",
        conflicts_with = "export_state",
        requires = "input"
    )]
    import_state: bool,

    /// Backup file to read when using --import-state
    #[arg(long = "input", value_name = "FILE")]
    input: Option<PathBuf>,
}

#[cfg(unix)]
async fn wait_for_shutdown_signal() -> anyhow::Result<&'static str> {
    let mut sigterm = tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())?;

    tokio::select! {
        result = tokio::signal::ctrl_c() => {
            result?;
            Ok("Ctrl+C")
        }
        _ = sigterm.recv() => Ok("SIGTERM"),
    }
}

#[cfg(not(unix))]
async fn wait_for_shutdown_signal() -> anyhow::Result<&'static str> {
    tokio::signal::ctrl_c().await?;
    Ok("Ctrl+C")
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

    if args.import_state {
        let input = args
            .input
            .as_ref()
            .expect("--input is required by clap when --import-state is set");
        let backup = import_state(input)?;
        backup.apply_to_config(&mut config)?;
        println!(
            "Imported miner state for miner_id={} wallet={}",
            backup.miner_id, backup.wallet
        );
    }

    if args.export_state {
        let output = args
            .output
            .as_ref()
            .expect("--output is required by clap when --export-state is set");
        let backup = export_state(output, &config)?;
        println!(
            "Exported miner state for miner_id={} wallet={} to {}",
            backup.miner_id,
            backup.wallet,
            output.display()
        );
        return Ok(());
    }

    // Create miner (async)
    let miner = Miner::new(config).await?;

    // Wire process signals into the miner's shutdown flag so SIGTERM and Ctrl+C
    // both follow the same graceful shutdown path.
    let shutdown_flag = miner.shutdown_flag();
    let signal_task = tokio::spawn(async move {
        match wait_for_shutdown_signal().await {
            Ok(signal_name) => {
                println!("\n\nShutdown signal received ({signal_name}); stopping miner...");
                shutdown_flag.store(true, Ordering::Relaxed);
            }
            Err(e) => {
                eprintln!("Error setting up shutdown handler: {}", e);
            }
        }
    });

    // Run miner
    let run_result = miner.run().await;
    signal_task.abort();

    if let Err(e) = run_result {
        eprintln!("Miner error: {}", e);
        std::process::exit(1);
    }

    Ok(())
}
