//! API client module
//! 
//! Handles communication with RustChain node endpoints.

use crate::types::*;
use reqwest::{Client, ClientBuilder};
use tracing::{debug, info};

/// API client for RustChain node
pub struct ApiClient {
    client: Client,
    node_url: String,
    dry_run: bool,
    show_payload: bool,
}

impl ApiClient {
    /// Create a new API client
    pub fn new(config: &MinerConfig) -> Result<Self> {
        let mut builder = ClientBuilder::new();
        
        // Configure TLS verification
        if config.insecure_skip_verify {
            builder = builder.danger_accept_invalid_certs(true);
        }
        
        let client = builder
            .build()
            .map_err(|e| MinerError::Network(e))?;

        Ok(Self {
            client,
            node_url: config.node_url.clone(),
            dry_run: config.dry_run,
            show_payload: config.show_payload,
        })
    }

    /// Check node health
    pub async fn health_check(&self) -> Result<HealthResponse> {
        let url = format!("{}/health", self.node_url);
        debug!("Checking node health: {}", url);

        if self.dry_run {
            info!("[DRY-RUN] Would check health at {}", url);
            return Ok(HealthResponse {
                ok: true,
                version: Some("dry-run".to_string()),
                uptime_s: Some(0),
                db_rw: Some(true),
                backup_age_hours: Some(0.0),
                tip_age_slots: Some(0),
            });
        }

        let response = self.client
            .get(&url)
            .send()
            .await
            .map_err(|e| MinerError::Network(e))?;

        if !response.status().is_success() {
            return Err(MinerError::Api(format!(
                "Health check failed with status: {}",
                response.status()
            )));
        }

        let health = response
            .json::<HealthResponse>()
            .await
            .map_err(|e| MinerError::Network(reqwest::Error::from(e)))?;

        info!("Node health: ok={}, version={:?}", health.ok, health.version);
        Ok(health)
    }

    /// Get current epoch information
    pub async fn get_epoch(&self) -> Result<EpochResponse> {
        let url = format!("{}/epoch", self.node_url);
        debug!("Fetching epoch info: {}", url);

        if self.dry_run {
            info!("[DRY-RUN] Would fetch epoch from {}", url);
            return Ok(EpochResponse {
                epoch: 0,
                slot: 0,
                epoch_pot: 1.5,
                enrolled_miners: 0,
                blocks_per_epoch: 60,
                total_supply_rtc: 0.0,
            });
        }

        let response = self.client
            .get(&url)
            .send()
            .await
            .map_err(|e| MinerError::Network(e))?;

        if !response.status().is_success() {
            return Err(MinerError::Api(format!(
                "Epoch fetch failed with status: {}",
                response.status()
            )));
        }

        let epoch = response
            .json::<EpochResponse>()
            .await
            .map_err(|e| MinerError::Network(reqwest::Error::from(e)))?;

        debug!("Current epoch: {}", epoch.epoch);
        Ok(epoch)
    }

    /// Enroll in current epoch
    pub async fn enroll_epoch(
        &self,
        miner_id: &str,
        hardware: &HardwareInfo,
    ) -> Result<EnrollResponse> {
        // Generate a pseudo-pubkey from miner_id (phase-2 will use real crypto)
        let miner_pubkey = generate_miner_pubkey(miner_id);

        let payload = EnrollRequest {
            miner_pubkey: miner_pubkey.clone(),
            miner_id: miner_id.to_string(),
            device: DeviceInfo::from(hardware),
        };

        // Show payload if requested
        if self.show_payload {
            println!("[SHOW-PAYLOAD] Enrollment request:");
            println!("{}", serde_json::to_string_pretty(&payload).unwrap());
        }

        let url = format!("{}/epoch/enroll", self.node_url);
        debug!("Enrolling in epoch: {}", url);

        if self.dry_run {
            info!("[DRY-RUN] Would enroll with payload: {:?}", payload);
            return Ok(EnrollResponse {
                ok: true,
                epoch: 0,
                weight: 1.0,
                hw_weight: 1.0,
                fingerprint_failed: false,
                miner_pk: miner_pubkey,
                miner_id: miner_id.to_string(),
                error: None,
            });
        }

        let response = self.client
            .post(&url)
            .json(&payload)
            .send()
            .await
            .map_err(|e| MinerError::Network(e))?;

        let status = response.status();
        let body = response
            .text()
            .await
            .map_err(|e| MinerError::Network(e))?;

        if !status.is_success() {
            return Err(MinerError::NodeError(format!(
                "Enrollment failed ({}): {}",
                status, body
            )));
        }

        let enroll_response: EnrollResponse = serde_json::from_str(&body)
            .map_err(|e| MinerError::Serialization(e))?;

        info!(
            "Enrolled in epoch {}: weight={}, hw_weight={}",
            enroll_response.epoch, enroll_response.weight, enroll_response.hw_weight
        );

        Ok(enroll_response)
    }

    /// Get wallet balance
    pub async fn get_balance(&self, miner_id: &str) -> Result<BalanceResponse> {
        let url = format!("{}/wallet/balance?miner_id={}", self.node_url, miner_id);
        debug!("Fetching balance: {}", url);

        if self.dry_run {
            info!("[DRY-RUN] Would fetch balance for {}", miner_id);
            return Ok(BalanceResponse {
                miner_id: miner_id.to_string(),
                amount_i64: 0,
                amount_rtc: 0.0,
            });
        }

        let response = self.client
            .get(&url)
            .send()
            .await
            .map_err(|e| MinerError::Network(e))?;

        if !response.status().is_success() {
            return Err(MinerError::Api(format!(
                "Balance fetch failed with status: {}",
                response.status()
            )));
        }

        let balance = response
            .json::<BalanceResponse>()
            .await
            .map_err(|e| MinerError::Network(reqwest::Error::from(e)))?;

        debug!("Balance for {}: {} RTC", balance.miner_id, balance.amount_rtc);
        Ok(balance)
    }

    /// Get list of active miners
    pub async fn get_miners(&self) -> Result<Vec<MinerEntry>> {
        let url = format!("{}/api/miners", self.node_url);
        debug!("Fetching miners list: {}", url);

        if self.dry_run {
            info!("[DRY-RUN] Would fetch miners list from {}", url);
            return Ok(Vec::new());
        }

        let response = self.client
            .get(&url)
            .send()
            .await
            .map_err(|e| MinerError::Network(e))?;

        if !response.status().is_success() {
            return Err(MinerError::Api(format!(
                "Miners list fetch failed with status: {}",
                response.status()
            )));
        }

        let miners = response
            .json::<Vec<MinerEntry>>()
            .await
            .map_err(|e| MinerError::Network(reqwest::Error::from(e)))?;

        debug!("Found {} active miners", miners.len());
        Ok(miners)
    }
}

/// Generate a pseudo-pubkey from miner_id
/// Phase-2: Will use real Ed25519 key generation
fn generate_miner_pubkey(miner_id: &str) -> String {
    use sha2::{Sha256, Digest};
    
    let mut hasher = Sha256::new();
    hasher.update(miner_id.as_bytes());
    let hash = hasher.finalize();
    hex::encode(hash)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_generate_miner_pubkey() {
        let pubkey1 = generate_miner_pubkey("test-miner-1");
        let pubkey2 = generate_miner_pubkey("test-miner-2");
        let pubkey1_again = generate_miner_pubkey("test-miner-1");
        
        assert_eq!(pubkey1.len(), 64); // SHA256 hex
        assert_ne!(pubkey1, pubkey2);
        assert_eq!(pubkey1, pubkey1_again);
    }
}
