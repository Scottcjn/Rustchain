// SPDX-License-Identifier: Apache-2.0
use clap::Parser;

/// Native Rust miner for RustChain — full RIP-PoA hardware fingerprinting.
#[derive(Parser, Debug)]
#[command(
    name = "rustchain-miner",
    version,
    about = "Native Rust miner for the RustChain Proof-of-Antiquity blockchain"
)]
pub struct Cli {
    /// Wallet / miner ID to mine with.
    #[arg(long)]
    pub wallet: Option<String>,

    /// RustChain node URL.
    #[arg(long, default_value = "https://50.28.86.131")]
    pub node: String,

    /// Build and display the attestation payload without submitting.
    #[arg(long)]
    pub dry_run: bool,

    /// Print the exact JSON payload that would be sent.
    #[arg(long)]
    pub show_payload: bool,

    /// Run fingerprint checks only (no attestation).
    #[arg(long)]
    pub test_only: bool,
}
