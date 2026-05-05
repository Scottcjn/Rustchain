// SPDX-License-Identifier: Apache-2.0
mod cli;
mod config;
mod hardware;
mod fingerprint;
mod network;
mod payload;
mod attestation;

use clap::Parser;

fn main() {
    // Initialize logging (controlled via RUST_LOG env var)
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info"))
        .format_timestamp_secs()
        .init();

    let cli = cli::Cli::parse();

    if let Err(e) = attestation::run(&cli) {
        eprintln!("Fatal error: {}", e);
        std::process::exit(1);
    }
}
