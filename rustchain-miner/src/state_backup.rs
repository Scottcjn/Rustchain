//! Miner state backup import/export helpers.

use chrono::Utc;
use serde::{Deserialize, Serialize};
use std::path::Path;

use crate::config::Config;
use crate::error::{MinerError, Result};
use crate::hardware::HardwareInfo;

const BACKUP_VERSION: u32 = 1;

/// Portable miner state snapshot for backup or machine migration.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct MinerStateBackup {
    /// Backup schema version.
    pub version: u32,

    /// RFC3339 export timestamp.
    pub exported_at: String,

    /// Wallet address used by the miner.
    pub wallet: String,

    /// Miner identity used for attestation and enrollment.
    pub miner_id: String,

    /// Node URL used when the backup was created.
    pub node_url: String,

    /// Optional HTTP proxy URL used when the backup was created.
    #[serde(default)]
    pub proxy_url: Option<String>,

    /// Mining block interval.
    pub block_time_secs: u64,

    /// Attestation TTL.
    pub attestation_ttl_secs: u64,

    /// Last known sync checkpoint, reserved for future node-backed exports.
    #[serde(default)]
    pub last_sync_checkpoint: Option<String>,

    /// Attestation history, reserved for future node-backed exports.
    #[serde(default)]
    pub attestation_records: Vec<serde_json::Value>,

    /// Pending reward records, reserved for future node-backed exports.
    #[serde(default)]
    pub pending_rewards: Vec<serde_json::Value>,
}

impl MinerStateBackup {
    /// Build a backup from local miner configuration and detected hardware.
    pub fn from_config(config: &Config, hardware: &HardwareInfo) -> Self {
        let miner_id = config
            .miner_id
            .clone()
            .unwrap_or_else(|| hardware.generate_miner_id());
        let wallet = config
            .wallet
            .clone()
            .unwrap_or_else(|| hardware.generate_wallet(&miner_id));

        Self {
            version: BACKUP_VERSION,
            exported_at: Utc::now().to_rfc3339(),
            wallet,
            miner_id,
            node_url: config.node_url.clone(),
            proxy_url: config.proxy_url.clone(),
            block_time_secs: config.block_time_secs,
            attestation_ttl_secs: config.attestation_ttl_secs,
            last_sync_checkpoint: None,
            attestation_records: Vec::new(),
            pending_rewards: Vec::new(),
        }
    }

    /// Validate and apply imported state to a miner configuration.
    pub fn apply_to_config(&self, config: &mut Config) -> Result<()> {
        self.validate()?;
        config.wallet = Some(self.wallet.clone());
        config.miner_id = Some(self.miner_id.clone());
        config.node_url = self.node_url.clone();
        config.proxy_url = self.proxy_url.clone();
        config.block_time_secs = self.block_time_secs;
        config.attestation_ttl_secs = self.attestation_ttl_secs;
        Ok(())
    }

    fn validate(&self) -> Result<()> {
        if self.version != BACKUP_VERSION {
            return Err(MinerError::Config(format!(
                "unsupported miner state backup version {}",
                self.version
            )));
        }
        if self.wallet.trim().is_empty() {
            return Err(MinerError::Config(
                "miner state backup is missing wallet".to_string(),
            ));
        }
        if self.miner_id.trim().is_empty() {
            return Err(MinerError::Config(
                "miner state backup is missing miner_id".to_string(),
            ));
        }
        if self.node_url.trim().is_empty() {
            return Err(MinerError::Config(
                "miner state backup is missing node_url".to_string(),
            ));
        }
        Ok(())
    }
}

/// Write local miner state to a JSON backup file.
pub fn export_state(path: &Path, config: &Config) -> Result<MinerStateBackup> {
    let hardware = HardwareInfo::collect()?;
    let backup = MinerStateBackup::from_config(config, &hardware);
    let encoded = serde_json::to_string_pretty(&backup)?;
    std::fs::write(path, encoded)?;
    Ok(backup)
}

/// Read and validate a JSON backup file.
pub fn import_state(path: &Path) -> Result<MinerStateBackup> {
    let raw = std::fs::read_to_string(path)?;
    let backup: MinerStateBackup = serde_json::from_str(&raw)?;
    backup.validate()?;
    Ok(backup)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_hardware() -> HardwareInfo {
        HardwareInfo {
            platform: "linux".to_string(),
            machine: "x86_64".to_string(),
            hostname: "miner-host".to_string(),
            family: "x86_64".to_string(),
            arch: "modern".to_string(),
            cpu: "test cpu".to_string(),
            cores: 4,
            memory_gb: 8,
            serial: Some("serial-1".to_string()),
            macs: vec!["00:11:22:33:44:55".to_string()],
            mac: "00:11:22:33:44:55".to_string(),
        }
    }

    #[test]
    fn backup_roundtrip_applies_identity_to_config() {
        let mut config = Config::default();
        config.wallet = Some("RTCbackupwallet".to_string());
        config.miner_id = Some("miner-backup".to_string());
        config.node_url = "https://node.example".to_string();
        config.proxy_url = Some("http://proxy.example".to_string());

        let backup = MinerStateBackup::from_config(&config, &sample_hardware());
        let encoded = serde_json::to_string(&backup).unwrap();
        let decoded: MinerStateBackup = serde_json::from_str(&encoded).unwrap();

        let mut restored = Config::default();
        decoded.apply_to_config(&mut restored).unwrap();

        assert_eq!(restored.wallet.as_deref(), Some("RTCbackupwallet"));
        assert_eq!(restored.miner_id.as_deref(), Some("miner-backup"));
        assert_eq!(restored.node_url, "https://node.example");
        assert_eq!(restored.proxy_url.as_deref(), Some("http://proxy.example"));
    }

    #[test]
    fn rejects_missing_wallet() {
        let mut backup = MinerStateBackup::from_config(&Config::default(), &sample_hardware());
        backup.wallet.clear();

        let err = backup.validate().unwrap_err().to_string();
        assert!(err.contains("missing wallet"));
    }
}
