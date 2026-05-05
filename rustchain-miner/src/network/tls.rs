// SPDX-License-Identifier: Apache-2.0
//! TLS configuration for connecting to RustChain nodes with self-signed certificates.

use reqwest::blocking::Client;
use std::time::Duration;

/// Build an HTTP client that accepts self-signed certificates.
///
/// The RustChain node at 50.28.86.131 uses a self-signed cert, so we
/// must disable certificate verification (matching the Python miner's
/// `verify=False` behavior).
pub fn build_client() -> Result<Client, Box<dyn std::error::Error>> {
    let client = Client::builder()
        .danger_accept_invalid_certs(true)
        .timeout(Duration::from_secs(30))
        .connect_timeout(Duration::from_secs(10))
        .user_agent("rustchain-miner/0.1.0")
        .build()?;
    Ok(client)
}
