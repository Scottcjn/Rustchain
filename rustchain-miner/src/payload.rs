//! Attestation payload construction.
//!
//! Builds the JSON payload matching the RustChain attestation schema.

use crate::fingerprint::FingerprintResult;
use crate::hardware::HardwareInfo;
use rand::RngCore;

/// Build the attestation payload as a serde_json::Value.
///
/// This matches the exact schema required by POST /attest/submit.
///
/// `node_url` is included in the payload so the receiving node can verify
/// the attestation was intended for it and reject cross-node replay attacks.
pub fn build_payload(
    wallet: &str,
    nonce: &str,
    node_url: &str,
    hw: &HardwareInfo,
    fp: &FingerprintResult,
) -> serde_json::Value {
    use sha2::{Digest, Sha256};

    // Convert fingerprint checks to the expected nested format
    let mut checks = serde_json::Map::new();
    for (name, result) in &fp.checks {
        checks.insert(
            name.clone(),
            serde_json::json!({
                "passed": result.passed,
                "data": result.data,
            }),
        );
    }

    // Commitment binds the nonce to the specific target node so a payload
    // captured from one node cannot be replayed to a different node.
    let commitment_input = format!("{}{}{}", nonce, wallet, node_url);
    let commitment = hex::encode(Sha256::digest(commitment_input.as_bytes()));

    serde_json::json!({
        "miner": wallet,
        "miner_id": wallet,
        "nonce": nonce,
        "node_url": node_url,
        "commitment": commitment,
        "report": {
            "cpu_model": hw.cpu_model,
            "cpu_cores": hw.cpu_cores,
            "ram_gb": hw.ram_gb,
            "os": hw.os,
        },
        "device": {
            "device_family": hw.device_family,
            "device_arch": hw.device_arch,
            "device_model": hw.device_model,
        },
        "signals": {
            "macs": hw.macs,
            "uptime": hw.uptime,
        },
        "fingerprint": {
            "all_passed": fp.all_passed,
            "checks": checks,
        },
    })
}

/// Generate a random 32-character hex nonce (used as fallback if server nonce is unavailable).
pub fn generate_local_nonce() -> String {
    let mut bytes = [0u8; 16];
    rand::thread_rng().fill_bytes(&mut bytes);
    hex::encode(bytes)
}
