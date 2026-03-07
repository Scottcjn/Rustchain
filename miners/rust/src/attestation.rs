//! Attestation module
//! 
//! Handles the attestation loop for epoch enrollment.

use crate::api::ApiClient;
use crate::hardware::{detect_hardware, validate_hardware};
use crate::types::*;
use std::time::Duration;
use tokio::time;
use tracing::{error, info, warn};

/// Attestation manager
pub struct AttestationManager {
    config: MinerConfig,
    api_client: ApiClient,
    miner_id: String,
    hardware: HardwareInfo,
}

impl AttestationManager {
    /// Create a new attestation manager
    pub async fn new(config: MinerConfig) -> Result<Self> {
        // Detect hardware
        let hardware = detect_hardware()?;
        
        // Validate hardware (phase-2: will include fingerprint checks)
        validate_hardware(&hardware)?;

        // Generate or use provided miner ID
        let miner_id = if config.wallet.is_empty() {
            crate::hardware::generate_miner_id(&hardware)
        } else {
            config.wallet.clone()
        };

        // Create API client
        let api_client = ApiClient::new(&config)?;

        info!(
            "Initialized attestation manager for miner: {}",
            miner_id
        );
        info!(
            "Hardware: {} ({}/{}, {} cores, {} GB RAM)",
            hardware.model,
            hardware.family,
            hardware.arch,
            hardware.cores,
            hardware.total_ram_bytes / (1024 * 1024 * 1024)
        );

        Ok(Self {
            config,
            api_client,
            miner_id,
            hardware,
        })
    }

    /// Run a single attestation cycle
    pub async fn attest_once(&self) -> Result<AttestationResult> {
        info!("Starting attestation cycle...");

        // Check node health
        match self.api_client.health_check().await {
            Ok(health) => {
                if !health.ok {
                    return Err(MinerError::NodeError("Node health check failed".to_string()));
                }
            }
            Err(e) => {
                warn!("Health check failed: {}", e);
                return Err(e);
            }
        }

        // Get current epoch
        let epoch = match self.api_client.get_epoch().await {
            Ok(epoch) => epoch,
            Err(e) => {
                warn!("Failed to get epoch: {}", e);
                return Err(e);
            }
        };

        info!("Current epoch: {} (slot: {})", epoch.epoch, epoch.slot);

        // Enroll in epoch
        match self.api_client.enroll_epoch(&self.miner_id, &self.hardware).await {
            Ok(response) => {
                if response.ok {
                    info!(
                        "Successfully enrolled in epoch {} with weight {}",
                        response.epoch, response.weight
                    );
                    Ok(AttestationResult {
                        success: true,
                        epoch: response.epoch,
                        weight: response.weight,
                        message: format!(
                            "Enrolled in epoch {} with weight {} (HW: {})",
                            response.epoch, response.weight, response.hw_weight
                        ),
                    })
                } else {
                    let err = response.error.unwrap_or_else(|| "Unknown error".to_string());
                    Err(MinerError::NodeError(format!("Enrollment failed: {}", err)))
                }
            }
            Err(e) => {
                warn!("Enrollment failed: {}", e);
                Err(e)
            }
        }
    }

    /// Run continuous attestation loop
    pub async fn run_loop(&self) -> Result<()> {
        let interval = Duration::from_secs(self.config.attestation_interval_secs);
        let mut interval_timer = time::interval(interval);

        info!(
            "Starting attestation loop (interval: {}s)",
            self.config.attestation_interval_secs
        );

        // Run first attestation immediately
        match self.attest_once().await {
            Ok(result) => {
                info!("Initial attestation: {}", result.message);
            }
            Err(e) => {
                error!("Initial attestation failed: {}", e);
            }
        }

        // Continue with periodic attestations
        loop {
            interval_timer.tick().await;

            match self.attest_once().await {
                Ok(result) => {
                    info!("Attestation successful: {}", result.message);
                }
                Err(e) => {
                    warn!("Attestation failed: {}", e);
                    // Continue loop even on failure
                }
            }
        }
    }

    /// Get miner ID
    pub fn miner_id(&self) -> &str {
        &self.miner_id
    }

    /// Get hardware info
    pub fn hardware(&self) -> &HardwareInfo {
        &self.hardware
    }

    /// Get config
    pub fn config(&self) -> &MinerConfig {
        &self.config
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_attestation_manager_creation() {
        let config = MinerConfig::default()
            .with_dry_run(true)
            .with_test_only(true);
        
        let manager = AttestationManager::new(config).await;
        assert!(manager.is_ok());
    }
}
