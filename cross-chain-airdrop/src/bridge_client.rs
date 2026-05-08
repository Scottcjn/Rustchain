//! Bridge client for cross-chain lock/release operations

use crate::error::{AirdropError, Result};
use crate::models::{ClaimStatus, TargetChain};
use chrono::{DateTime, Utc};
use reqwest::Client;
use serde::{Deserialize, Serialize};

/// Bridge API client
pub struct BridgeClient {
    client: Client,
    base_url: String,
    admin_key: Option<String>,
    timeout_secs: u64,
}

impl BridgeClient {
    pub fn new(base_url: String, admin_key: Option<String>, timeout_secs: u64) -> Self {
        Self {
            client: Client::builder()
                .timeout(std::time::Duration::from_secs(timeout_secs))
                .build()
                .unwrap_or_default(),
            base_url,
            admin_key,
            timeout_secs,
        }
    }

    pub fn with_defaults(base_url: String) -> Self {
        Self {
            client: Client::new(),
            base_url,
            admin_key: None,
            timeout_secs: 30,
        }
    }

    /// Lock RTC for cross-chain bridge
    pub async fn lock_rtc(
        &self,
        sender_wallet: &str,
        amount: f64,
        target_chain: TargetChain,
        target_wallet: &str,
        tx_hash: &str,
        receipt_signature: Option<&str>,
    ) -> Result<BridgeLockResponse> {
        let mut request = self
            .client
            .post(format!("{}/bridge/lock", self.base_url))
            .header("Content-Type", "application/json");

        let mut body = serde_json::json!({
            "sender_wallet": sender_wallet,
            "amount": amount,
            "target_chain": target_chain.to_string(),
            "target_wallet": target_wallet,
            "tx_hash": tx_hash,
        });

        if let Some(sig) = receipt_signature {
            body["receipt_signature"] = serde_json::json!(sig);
        }

        request = request.json(&body);

        let response = request
            .send()
            .await
            .map_err(|e| AirdropError::Bridge(format!("Failed to lock RTC: {}", e)))?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            return Err(AirdropError::Bridge(format!(
                "Bridge API error ({}): {}",
                status, body
            )));
        }

        let lock_response: BridgeLockResponse = response
            .json()
            .await
            .map_err(|e| AirdropError::Bridge(format!("Failed to parse lock response: {}", e)))?;

        Ok(lock_response)
    }

    /// Confirm a lock (admin only)
    pub async fn confirm_lock(
        &self,
        lock_id: &str,
        proof_ref: &str,
        notes: Option<&str>,
    ) -> Result<BridgeLockResponse> {
        let admin_key = self.admin_key.as_ref().ok_or_else(|| {
            AirdropError::Bridge("Admin key required for confirm_lock".to_string())
        })?;

        let mut request = self
            .client
            .post(format!("{}/bridge/confirm", self.base_url))
            .header("Content-Type", "application/json")
            .header("X-Admin-Key", admin_key)
            .json(&serde_json::json!({
                "lock_id": lock_id,
                "proof_ref": proof_ref,
                "notes": notes,
            }));

        let response = request
            .send()
            .await
            .map_err(|e| AirdropError::Bridge(format!("Failed to confirm lock: {}", e)))?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            return Err(AirdropError::Bridge(format!(
                "Bridge API error ({}): {}",
                status, body
            )));
        }

        let lock_response: BridgeLockResponse = response.json().await.map_err(|e| {
            AirdropError::Bridge(format!("Failed to parse confirm response: {}", e))
        })?;

        Ok(lock_response)
    }

    /// Release wRTC on target chain (admin only)
    pub async fn release_wrtc(
        &self,
        lock_id: &str,
        release_tx: &str,
        notes: Option<&str>,
    ) -> Result<BridgeLockResponse> {
        let admin_key = self.admin_key.as_ref().ok_or_else(|| {
            AirdropError::Bridge("Admin key required for release_wrtc".to_string())
        })?;

        let response = self
            .client
            .post(format!("{}/bridge/release", self.base_url))
            .header("Content-Type", "application/json")
            .header("X-Admin-Key", admin_key)
            .json(&serde_json::json!({
                "lock_id": lock_id,
                "release_tx": release_tx,
                "notes": notes,
            }))
            .send()
            .await
            .map_err(|e| AirdropError::Bridge(format!("Failed to release wRTC: {}", e)))?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            return Err(AirdropError::Bridge(format!(
                "Bridge API error ({}): {}",
                status, body
            )));
        }

        let lock_response: BridgeLockResponse = response.json().await.map_err(|e| {
            AirdropError::Bridge(format!("Failed to parse release response: {}", e))
        })?;

        Ok(lock_response)
    }

    /// Get lock status
    pub async fn get_lock_status(&self, lock_id: &str) -> Result<BridgeLockStatus> {
        let response = self
            .client
            .get(format!("{}/bridge/status/{}", self.base_url, lock_id))
            .send()
            .await
            .map_err(|e| AirdropError::Bridge(format!("Failed to get lock status: {}", e)))?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            return Err(AirdropError::Bridge(format!(
                "Bridge API error ({}): {}",
                status, body
            )));
        }

        let status: BridgeLockStatus = response
            .json()
            .await
            .map_err(|e| AirdropError::Bridge(format!("Failed to parse lock status: {}", e)))?;

        Ok(status)
    }

    /// Get bridge statistics
    pub async fn get_stats(&self) -> Result<BridgeStats> {
        let response = self
            .client
            .get(format!("{}/bridge/stats", self.base_url))
            .send()
            .await
            .map_err(|e| AirdropError::Bridge(format!("Failed to get bridge stats: {}", e)))?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            return Err(AirdropError::Bridge(format!(
                "Bridge API error ({}): {}",
                status, body
            )));
        }

        let stats: BridgeStats = response
            .json()
            .await
            .map_err(|e| AirdropError::Bridge(format!("Failed to parse bridge stats: {}", e)))?;

        Ok(stats)
    }
}

/// Bridge lock response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BridgeLockResponse {
    pub lock_id: String,
    pub state: String,
    pub sender_wallet: String,
    pub amount_rtc: f64,
    pub target_chain: String,
    pub target_wallet: String,
    pub tx_hash: String,
    pub proof_type: Option<String>,
    pub proof_ref: Option<String>,
    pub expires_at: u64,
    pub message: Option<String>,
}

/// Bridge lock status
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BridgeLockStatus {
    pub lock_id: String,
    pub state: String,
    pub sender_wallet: String,
    pub amount_rtc: f64,
    pub target_chain: String,
    pub target_wallet: String,
    pub tx_hash: Option<String>,
    pub proof_type: Option<String>,
    pub proof_ref: Option<String>,
    pub release_tx: Option<String>,
    pub confirmed_at: Option<u64>,
    pub confirmed_by: Option<String>,
    pub created_at: u64,
    pub updated_at: u64,
    pub expires_at: u64,
    pub events: Vec<BridgeEvent>,
}

/// Bridge event
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BridgeEvent {
    #[serde(rename = "type")]
    pub event_type: String,
    pub actor: Option<String>,
    pub ts: u64,
    pub details: serde_json::Value,
}

/// Bridge statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BridgeStats {
    pub by_state: serde_json::Value,
    pub by_chain: serde_json::Value,
    pub all_time: BridgeAllTimeStats,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BridgeAllTimeStats {
    pub total_locks: u64,
    pub total_rtc_locked: f64,
}

/// Convert bridge state to claim status
pub fn bridge_state_to_claim_state(state: &str) -> ClaimStatus {
    match state {
        "requested" | "pending" => ClaimStatus::Pending,
        "confirmed" => ClaimStatus::Verified,
        "releasing" => ClaimStatus::Bridging,
        "complete" => ClaimStatus::Complete,
        "failed" => ClaimStatus::Failed,
        "refunded" => ClaimStatus::Failed,
        _ => ClaimStatus::Pending,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_bridge_state_conversion() {
        assert_eq!(
            bridge_state_to_claim_state("requested"),
            ClaimStatus::Pending
        );
        assert_eq!(
            bridge_state_to_claim_state("confirmed"),
            ClaimStatus::Verified
        );
        assert_eq!(
            bridge_state_to_claim_state("complete"),
            ClaimStatus::Complete
        );
        assert_eq!(bridge_state_to_claim_state("failed"), ClaimStatus::Failed);
    }
}
