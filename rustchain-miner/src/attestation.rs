//! Hardware attestation with fingerprint and entropy collection

use ed25519_dalek::Signer;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use crate::hardware::HardwareInfo;
use crate::transport::NodeTransport;

/// Attestation report sent to the node
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AttestationReport {
    /// Miner wallet address
    pub miner: String,

    /// Miner ID
    pub miner_id: String,

    /// Challenge nonce from node
    pub nonce: String,

    /// Entropy report
    pub report: EntropyReport,

    /// Device information
    pub device: DeviceInfo,

    /// Network signals
    pub signals: NetworkSignals,

    /// Hardware fingerprint data (optional)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub fingerprint: Option<FingerprintData>,

    /// Miner version
    pub miner_version: String,

    /// Ed25519 signature over critical fields (miner, miner_id, nonce, commitment)
    /// Binds the report to the miner's keypair, preventing tampering and replay attacks
    pub signature: String,

    /// Public key used for verification (hex-encoded, 32 bytes)
    pub public_key: String,
}

/// Entropy report derived from timing measurements
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EntropyReport {
    /// Challenge nonce
    pub nonce: String,

    /// Commitment hash
    pub commitment: String,

    /// Derived entropy data
    pub derived: EntropyData,

    /// Entropy score (variance)
    pub entropy_score: f64,
}

/// Entropy data from timing measurements
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EntropyData {
    /// Mean duration in nanoseconds
    pub mean_ns: f64,

    /// Variance in nanoseconds
    pub variance_ns: f64,

    /// Minimum duration in nanoseconds
    pub min_ns: f64,

    /// Maximum duration in nanoseconds
    pub max_ns: f64,

    /// Number of samples
    pub sample_count: usize,

    /// Preview of first samples
    pub samples_preview: Vec<f64>,
}

/// Device information for attestation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeviceInfo {
    /// CPU family
    pub family: String,

    /// CPU architecture
    pub arch: String,

    /// Device model
    pub model: String,

    /// CPU brand string
    pub cpu: String,

    /// Number of cores
    pub cores: usize,

    /// Memory in GB
    pub memory_gb: u64,

    /// Hardware serial (if available)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub serial: Option<String>,
}

/// Network signals for attestation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NetworkSignals {
    /// MAC addresses
    pub macs: Vec<String>,

    /// Hostname
    pub hostname: String,
}

/// Hardware fingerprint data
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FingerprintData {
    /// Individual check results
    pub checks: std::collections::HashMap<String, CheckResult>,

    /// Whether all checks passed
    pub all_passed: bool,
}

/// Result of a single fingerprint check
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CheckResult {
    /// Whether the check passed
    pub passed: bool,

    /// Check-specific data
    pub data: serde_json::Value,
}

impl From<&HardwareInfo> for DeviceInfo {
    fn from(hw: &HardwareInfo) -> Self {
        Self {
            family: hw.family.clone(),
            arch: hw.arch.clone(),
            model: hw.machine.clone(),
            cpu: hw.cpu.clone(),
            cores: hw.cores,
            memory_gb: hw.memory_gb,
            serial: hw.serial.clone(),
        }
    }
}

impl From<&HardwareInfo> for NetworkSignals {
    fn from(hw: &HardwareInfo) -> Self {
        Self {
            macs: hw.macs.clone(),
            hostname: hw.hostname.clone(),
        }
    }
}

/// Collect entropy from CPU timing measurements
pub fn collect_entropy(cycles: usize, inner_loop: usize) -> EntropyData {
    use std::time::Instant;

    let mut samples = Vec::with_capacity(cycles);

    for _ in 0..cycles {
        let start = Instant::now();
        let mut _acc: u64 = 0;
        for j in 0..inner_loop {
            _acc ^= (j as u64 * 31) & 0xFFFFFFFF;
        }
        let duration = start.elapsed().as_nanos() as f64;
        samples.push(duration);
    }

    let mean_ns = samples.iter().sum::<f64>() / samples.len() as f64;
    let variance_ns = if samples.len() > 1 {
        samples.iter().map(|x| (x - mean_ns).powi(2)).sum::<f64>() / samples.len() as f64
    } else {
        0.0
    };

    let min_ns = samples.iter().cloned().fold(f64::INFINITY, f64::min);
    let max_ns = samples.iter().cloned().fold(f64::NEG_INFINITY, f64::max);

    EntropyData {
        mean_ns,
        variance_ns,
        min_ns,
        max_ns,
        sample_count: samples.len(),
        samples_preview: samples.iter().take(12).cloned().collect(),
    }
}

/// Perform hardware attestation with the node using a pre-generated signing key.
/// This allows the same keypair to be reused for enrollment signature verification.
pub async fn attest_with_key(
    transport: &NodeTransport,
    wallet: &str,
    miner_id: &str,
    hw_info: &HardwareInfo,
    signing_key: &ed25519_dalek::SigningKey,
    public_key_hex: &str,
    fingerprint_data: Option<FingerprintData>,
) -> crate::Result<bool> {
    tracing::info!("[ATTEST] Starting hardware attestation...");

    // Step 1: Get challenge nonce from node
    let response = transport
        .post_json("/attest/challenge", &serde_json::json!({}))
        .await?;

    if !response.status().is_success() {
        let status = response.status();
        let body = response.text().await.unwrap_or_default();
        return Err(crate::error::MinerError::Attestation(format!(
            "Challenge failed: HTTP {} - {}",
            status, body
        )));
    }

    let challenge: serde_json::Value = response.json().await?;
    let nonce = challenge
        .get("nonce")
        .and_then(|n| n.as_str())
        .unwrap_or("")
        .to_string();

    if nonce.is_empty() {
        return Err(crate::error::MinerError::Attestation(
            "No nonce in challenge response".to_string(),
        ));
    }

    tracing::info!(
        "[ATTEST] Got challenge nonce: {}...",
        &nonce[..nonce.len().min(16)]
    );

    // Step 2: Collect entropy
    let entropy = collect_entropy(48, 25000);

    // Step 3: Build commitment
    let entropy_json = serde_json::to_string(&entropy)?;
    let commitment_string = format!("{}{}{}", nonce, wallet, entropy_json);
    let commitment_hash = Sha256::digest(commitment_string.as_bytes());
    let commitment = hex::encode(commitment_hash);

    // Step 4: Sign critical fields using the provided keypair
    // The signature binds (miner, miner_id, nonce, commitment) to prevent:
    // - Wallet address tampering (attacker can't change miner field)
    // - Replay attacks (nonce is unique per attestation)
    // - Field modification (any change invalidates signature)
    let verifying_key = signing_key.verifying_key();
    let computed_pubkey_hex = hex::encode(verifying_key.as_bytes());

    // Verify the provided public_key_hex matches the signing key
    if computed_pubkey_hex != public_key_hex {
        return Err(crate::error::MinerError::Attestation(
            "Public key mismatch: provided key doesn't match signing key".to_string(),
        ));
    }

    // Sign the critical fields that must be authentic
    let message = format!("{}|{}|{}|{}", miner_id, wallet, nonce, commitment);
    let signature = signing_key.sign(message.as_bytes());
    let signature_hex = hex::encode(signature.to_bytes());

    // Step 5: Build attestation report with signature
    let report = AttestationReport {
        miner: wallet.to_string(),
        miner_id: miner_id.to_string(),
        nonce: nonce.clone(),
        report: EntropyReport {
            nonce,
            commitment,
            derived: entropy.clone(),
            entropy_score: entropy.variance_ns,
        },
        device: DeviceInfo::from(hw_info),
        signals: NetworkSignals::from(hw_info),
        fingerprint: fingerprint_data,
        miner_version: env!("CARGO_PKG_VERSION").to_string(),
        signature: signature_hex,
        public_key: public_key_hex.to_string(),
    };

    // Step 6: Submit attestation
    let response = transport.post_json("/attest/submit", &report).await?;

    if !response.status().is_success() {
        let status = response.status();
        let body = response.text().await.unwrap_or_default();
        return Err(crate::error::MinerError::Attestation(format!(
            "Submit failed: HTTP {} - {}",
            status, body
        )));
    }

    let result: serde_json::Value = response.json().await?;

    if result.get("ok").and_then(|v| v.as_bool()).unwrap_or(false) {
        tracing::info!("[ATTEST] Attestation accepted!");
        Ok(true)
    } else {
        Err(crate::error::MinerError::Attestation(format!(
            "Attestation rejected: {:?}",
            result
        )))
    }
}

/// Perform hardware attestation with the node (generates a fresh keypair).
/// Prefer `attest_with_key` when the same keypair should be reused for enrollment.
pub async fn attest(
    transport: &NodeTransport,
    wallet: &str,
    miner_id: &str,
    hw_info: &HardwareInfo,
    fingerprint_data: Option<FingerprintData>,
) -> crate::Result<bool> {
    tracing::info!("[ATTEST] Starting hardware attestation...");

    // Step 1: Get challenge nonce from node
    let response = transport
        .post_json("/attest/challenge", &serde_json::json!({}))
        .await?;

    if !response.status().is_success() {
        let status = response.status();
        let body = response.text().await.unwrap_or_default();
        return Err(crate::error::MinerError::Attestation(format!(
            "Challenge failed: HTTP {} - {}",
            status, body
        )));
    }

    let challenge: serde_json::Value = response.json().await?;
    let nonce = challenge
        .get("nonce")
        .and_then(|n| n.as_str())
        .unwrap_or("")
        .to_string();

    if nonce.is_empty() {
        return Err(crate::error::MinerError::Attestation(
            "No nonce in challenge response".to_string(),
        ));
    }

    tracing::info!(
        "[ATTEST] Got challenge nonce: {}...",
        &nonce[..nonce.len().min(16)]
    );

    // Step 2: Collect entropy
    let entropy = collect_entropy(48, 25000);

    // Step 3: Build commitment
    let entropy_json = serde_json::to_string(&entropy)?;
    let commitment_string = format!("{}{}{}", nonce, wallet, entropy_json);
    let commitment_hash = Sha256::digest(commitment_string.as_bytes());
    let commitment = hex::encode(commitment_hash);

    // Step 4: Generate Ed25519 keypair and sign critical fields
    // The signature binds (miner, miner_id, nonce, commitment) to prevent:
    // - Wallet address tampering (attacker can't change miner field)
    // - Replay attacks (nonce is unique per attestation)
    // - Field modification (any change invalidates signature)
    let signing_key = ed25519_dalek::SigningKey::generate(&mut rand::rngs::OsRng);
    let verifying_key = signing_key.verifying_key();
    let public_key_hex = hex::encode(verifying_key.as_bytes());

    // Sign the critical fields that must be authentic
    let message = format!("{}|{}|{}|{}", miner_id, wallet, nonce, commitment);
    let signature = signing_key.sign(message.as_bytes());
    let signature_hex = hex::encode(signature.to_bytes());

    // Step 5: Build attestation report with signature
    let report = AttestationReport {
        miner: wallet.to_string(),
        miner_id: miner_id.to_string(),
        nonce: nonce.clone(),
        report: EntropyReport {
            nonce,
            commitment,
            derived: entropy.clone(),
            entropy_score: entropy.variance_ns,
        },
        device: DeviceInfo::from(hw_info),
        signals: NetworkSignals::from(hw_info),
        fingerprint: fingerprint_data,
        miner_version: env!("CARGO_PKG_VERSION").to_string(),
        signature: signature_hex,
        public_key: public_key_hex,
    };

    // Step 6: Submit attestation
    let response = transport.post_json("/attest/submit", &report).await?;

    if !response.status().is_success() {
        let status = response.status();
        let body = response.text().await.unwrap_or_default();
        return Err(crate::error::MinerError::Attestation(format!(
            "Submit failed: HTTP {} - {}",
            status, body
        )));
    }

    let result: serde_json::Value = response.json().await?;

    if result.get("ok").and_then(|v| v.as_bool()).unwrap_or(false) {
        tracing::info!("[ATTEST] Attestation accepted!");
        Ok(true)
    } else {
        Err(crate::error::MinerError::Attestation(format!(
            "Attestation rejected: {:?}",
            result
        )))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_entropy_collection() {
        let entropy = collect_entropy(10, 1000);
        assert!(entropy.mean_ns > 0.0);
        assert!(entropy.sample_count == 10);
        assert!(!entropy.samples_preview.is_empty());
    }

    /// Helper: sign a message and return (signature_hex, public_key_hex)
    fn sign_message(
        miner_id: &str,
        wallet: &str,
        nonce: &str,
        commitment: &str,
    ) -> (String, String) {
        let signing_key = ed25519_dalek::SigningKey::generate(&mut rand::rngs::OsRng);
        let verifying_key = signing_key.verifying_key();
        let public_key_hex = hex::encode(verifying_key.as_bytes());

        let message = format!("{}|{}|{}|{}", miner_id, wallet, nonce, commitment);
        let signature = signing_key.sign(message.as_bytes());
        let signature_hex = hex::encode(signature.to_bytes());

        (signature_hex, public_key_hex)
    }

    /// Helper: verify a signature against the message
    fn verify_signature(public_key_hex: &str, signature_hex: &str, message: &str) -> bool {
        let public_key_bytes = match hex::decode(public_key_hex) {
            Ok(b) => b,
            Err(_) => return false,
        };
        let signature_bytes = match hex::decode(signature_hex) {
            Ok(b) => b,
            Err(_) => return false,
        };

        if public_key_bytes.len() != 32 || signature_bytes.len() != 64 {
            return false;
        }

        let verifying_key =
            match ed25519_dalek::VerifyingKey::from_bytes(&public_key_bytes.try_into().unwrap()) {
                Ok(k) => k,
                Err(_) => return false,
            };

        let signature = match ed25519_dalek::Signature::from_slice(&signature_bytes) {
            Ok(s) => s,
            Err(_) => return false,
        };

        verifying_key
            .verify_strict(message.as_bytes(), &signature)
            .is_ok()
    }

    #[test]
    fn test_signature_creation_and_verification() {
        let miner_id = "miner_123";
        let wallet = "RTC_abc123";
        let nonce = "nonce_456";
        let commitment = "commit_789";

        let (sig, pub_key) = sign_message(miner_id, wallet, nonce, commitment);

        // Valid signature should verify
        let message = format!("{}|{}|{}|{}", miner_id, wallet, nonce, commitment);
        assert!(verify_signature(&pub_key, &sig, &message));
    }

    #[test]
    fn test_tampered_wallet_rejected() {
        let miner_id = "miner_123";
        let original_wallet = "RTC_abc123";
        let tampered_wallet = "RTC_attacker_wallet";
        let nonce = "nonce_456";
        let commitment = "commit_789";

        let (sig, pub_key) = sign_message(miner_id, original_wallet, nonce, commitment);

        // Attempt to verify with tampered wallet should fail
        let tampered_message = format!("{}|{}|{}|{}", miner_id, tampered_wallet, nonce, commitment);
        assert!(!verify_signature(&pub_key, &sig, &tampered_message));
    }

    #[test]
    fn test_tampered_miner_id_rejected() {
        let original_miner_id = "miner_123";
        let tampered_miner_id = "miner_attacker";
        let wallet = "RTC_abc123";
        let nonce = "nonce_456";
        let commitment = "commit_789";

        let (sig, pub_key) = sign_message(original_miner_id, wallet, nonce, commitment);

        // Attempt to verify with tampered miner_id should fail
        let tampered_message = format!("{}|{}|{}|{}", tampered_miner_id, wallet, nonce, commitment);
        assert!(!verify_signature(&pub_key, &sig, &tampered_message));
    }

    #[test]
    fn test_tampered_nonce_rejected() {
        let miner_id = "miner_123";
        let wallet = "RTC_abc123";
        let original_nonce = "nonce_456";
        let tampered_nonce = "nonce_attacker";
        let commitment = "commit_789";

        let (sig, pub_key) = sign_message(miner_id, wallet, original_nonce, commitment);

        // Attempt to verify with tampered nonce should fail
        let tampered_message = format!("{}|{}|{}|{}", miner_id, wallet, tampered_nonce, commitment);
        assert!(!verify_signature(&pub_key, &sig, &tampered_message));
    }

    #[test]
    fn test_tampered_commitment_rejected() {
        let miner_id = "miner_123";
        let wallet = "RTC_abc123";
        let nonce = "nonce_456";
        let original_commitment = "commit_789";
        let tampered_commitment = "commit_attacker";

        let (sig, pub_key) = sign_message(miner_id, wallet, nonce, original_commitment);

        // Attempt to verify with tampered commitment should fail
        let tampered_message = format!("{}|{}|{}|{}", miner_id, wallet, nonce, tampered_commitment);
        assert!(!verify_signature(&pub_key, &sig, &tampered_message));
    }

    #[test]
    fn test_replay_attack_with_different_nonce() {
        let miner_id = "miner_123";
        let wallet = "RTC_abc123";
        let original_nonce = "nonce_original";
        let replay_nonce = "nonce_replay";
        let commitment = "commit_789";

        // Sign with original nonce
        let (sig, pub_key) = sign_message(miner_id, wallet, original_nonce, commitment);

        // Replay with different nonce should fail
        let replay_message = format!("{}|{}|{}|{}", miner_id, wallet, replay_nonce, commitment);
        assert!(!verify_signature(&pub_key, &sig, &replay_message));
    }

    #[test]
    fn test_wrong_public_key_rejected() {
        let miner_id = "miner_123";
        let wallet = "RTC_abc123";
        let nonce = "nonce_456";
        let commitment = "commit_789";

        let (sig, _) = sign_message(miner_id, wallet, nonce, commitment);

        // Try to verify with a different keypair's public key
        let other_signing_key = ed25519_dalek::SigningKey::generate(&mut rand::rngs::OsRng);
        let other_public_key_hex = hex::encode(other_signing_key.verifying_key().as_bytes());

        let message = format!("{}|{}|{}|{}", miner_id, wallet, nonce, commitment);
        assert!(!verify_signature(&other_public_key_hex, &sig, &message));
    }

    #[test]
    fn test_invalid_signature_format_rejected() {
        let pub_key = hex::encode([0u8; 32]);
        let invalid_sig = "not_hex";
        let message = "test_message";

        assert!(!verify_signature(&pub_key, invalid_sig, message));
    }

    #[test]
    fn test_invalid_public_key_format_rejected() {
        let invalid_pub_key = "not_hex";
        let sig = hex::encode([0u8; 64]);
        let message = "test_message";

        assert!(!verify_signature(&invalid_pub_key, &sig, message));
    }

    #[test]
    fn test_short_public_key_rejected() {
        let short_pub_key = hex::encode([0u8; 16]);
        let sig = hex::encode([0u8; 64]);
        let message = "test_message";

        assert!(!verify_signature(&short_pub_key, &sig, message));
    }

    #[test]
    fn test_short_signature_rejected() {
        let pub_key = hex::encode([0u8; 32]);
        let short_sig = hex::encode([0u8; 32]);
        let message = "test_message";

        assert!(!verify_signature(&pub_key, &short_sig, message));
    }
}
