//! Hardware attestation with fingerprint and entropy collection

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

/// Perform hardware attestation with the node
pub async fn attest(
    transport: &NodeTransport,
    wallet: &str,
    miner_id: &str,
    hw_info: &HardwareInfo,
    fingerprint_data: Option<FingerprintData>,
) -> crate::Result<bool> {
    tracing::info!("[ATTEST] Starting hardware attestation...");

    // Step 1: Get challenge nonce from node
    let response = transport.post_json("/attest/challenge", &serde_json::json!({})).await?;
    
    if !response.status().is_success() {
        let status = response.status();
        let body = response.text().await.unwrap_or_default();
        return Err(crate::error::MinerError::Attestation(
            format!("Challenge failed: HTTP {} - {}", status, body)
        ));
    }

    let challenge: serde_json::Value = response.json().await?;
    let nonce = challenge
        .get("nonce")
        .and_then(|n| n.as_str())
        .unwrap_or("")
        .to_string();

    if nonce.is_empty() {
        return Err(crate::error::MinerError::Attestation(
            "No nonce in challenge response".to_string()
        ));
    }

    tracing::info!("[ATTEST] Got challenge nonce: {}...", &nonce[..nonce.len().min(16)]);

    // Step 2: Collect entropy
    let entropy = collect_entropy(48, 25000);

    // Step 3: Build commitment
    let entropy_json = serde_json::to_string(&entropy)?;
    let commitment_string = format!("{}{}{}", nonce, wallet, entropy_json);
    let commitment_hash = Sha256::digest(commitment_string.as_bytes());
    let commitment = hex::encode(commitment_hash);

    // Step 4: Build attestation report
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
    };

    // Step 5: Submit attestation
    let response = transport.post_json("/attest/submit", &report).await?;

    if !response.status().is_success() {
        let status = response.status();
        let body = response.text().await.unwrap_or_default();
        return Err(crate::error::MinerError::Attestation(
            format!("Submit failed: HTTP {} - {}", status, body)
        ));
    }

    let result: serde_json::Value = response.json().await?;
    
    if result.get("ok").and_then(|v| v.as_bool()).unwrap_or(false) {
        tracing::info!("[ATTEST] Attestation accepted!");
        Ok(true)
    } else {
        Err(crate::error::MinerError::Attestation(
            format!("Attestation rejected: {:?}", result)
        ))
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
}
