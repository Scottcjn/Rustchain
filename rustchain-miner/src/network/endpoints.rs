// SPDX-License-Identifier: Apache-2.0
//! API endpoint implementations for the RustChain node.

use super::RustChainClient;
use serde::{Deserialize, Serialize};

// ── Response types ──────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
pub struct HealthResponse {
    pub ok: bool,
    pub version: Option<String>,
    pub uptime_s: Option<u64>,
    pub db_rw: Option<bool>,
}

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
pub struct EpochResponse {
    pub epoch: u64,
    pub slot: Option<u64>,
    pub blocks_per_epoch: Option<u64>,
    pub enrolled_miners: Option<u64>,
    pub epoch_pot: Option<f64>,
}

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
pub struct ChallengeResponse {
    pub nonce: String,
    pub server_time: Option<u64>,
    pub expires_at: Option<u64>,
}

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
pub struct SubmitResponse {
    #[serde(default)]
    pub status: Option<String>,
    #[serde(default)]
    pub error: Option<String>,
    // Accept any other fields
    #[serde(flatten)]
    pub extra: std::collections::HashMap<String, serde_json::Value>,
}

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
pub struct BalanceResponse {
    pub miner_id: Option<String>,
    pub amount_rtc: Option<f64>,
    pub amount_i64: Option<i64>,
}

// ── Request types ───────────────────────────────────────────────────────

#[derive(Debug, Serialize)]
pub struct EnrollRequest {
    pub miner_pubkey: String,
    pub miner_id: String,
    pub device: DeviceEnroll,
}

#[derive(Debug, Serialize)]
pub struct DeviceEnroll {
    pub family: String,
    pub arch: String,
}

// ── Client methods ──────────────────────────────────────────────────────

impl RustChainClient {
    /// GET /health
    pub fn health(&self) -> Result<HealthResponse, Box<dyn std::error::Error>> {
        let resp = self.inner().get(self.url("/health")).send()?;
        let status = resp.status();
        if !status.is_success() {
            return Err(format!("Health check failed: HTTP {}", status).into());
        }
        Ok(resp.json()?)
    }

    /// GET /epoch
    pub fn epoch(&self) -> Result<EpochResponse, Box<dyn std::error::Error>> {
        let resp = self.inner().get(self.url("/epoch")).send()?;
        Ok(resp.json()?)
    }

    /// POST /attest/challenge
    pub fn challenge(&self) -> Result<ChallengeResponse, Box<dyn std::error::Error>> {
        let resp = self
            .inner()
            .post(self.url("/attest/challenge"))
            .header("Content-Type", "application/json")
            .body("{}")
            .send()?;
        let status = resp.status();
        if status.as_u16() == 429 {
            return Err("rate_limited".into());
        }
        if !status.is_success() {
            let body = resp.text().unwrap_or_default();
            return Err(format!("Challenge failed: HTTP {} — {}", status, body).into());
        }
        Ok(resp.json()?)
    }

    /// POST /attest/submit
    pub fn submit(
        &self,
        payload: &serde_json::Value,
    ) -> Result<SubmitResponse, Box<dyn std::error::Error>> {
        let resp = self
            .inner()
            .post(self.url("/attest/submit"))
            .json(payload)
            .send()?;
        let status = resp.status();
        if status.as_u16() == 429 {
            return Err("rate_limited".into());
        }
        if !status.is_success() {
            let body = resp.text().unwrap_or_default();
            return Err(format!("Submit failed: HTTP {} — {}", status, body).into());
        }
        Ok(resp.json()?)
    }

    /// POST /epoch/enroll
    pub fn enroll(
        &self,
        wallet: &str,
        device_family: &str,
        device_arch: &str,
    ) -> Result<serde_json::Value, Box<dyn std::error::Error>> {
        let req = EnrollRequest {
            miner_pubkey: wallet.to_string(),
            miner_id: wallet.to_string(),
            device: DeviceEnroll {
                family: device_family.to_string(),
                arch: device_arch.to_string(),
            },
        };
        let resp = self
            .inner()
            .post(self.url("/epoch/enroll"))
            .json(&req)
            .send()?;
        let status = resp.status();
        if status.as_u16() == 429 {
            return Err("rate_limited".into());
        }
        if !status.is_success() {
            let body = resp.text().unwrap_or_default();
            return Err(format!("Enroll failed: HTTP {} — {}", status, body).into());
        }
        Ok(resp.json()?)
    }

    /// GET /wallet/balance?miner_id=X
    pub fn balance(&self, miner_id: &str) -> Result<BalanceResponse, Box<dyn std::error::Error>> {
        let resp = self
            .inner()
            .get(self.url("/wallet/balance"))
            .query(&[("miner_id", miner_id)])
            .send()?;
        Ok(resp.json()?)
    }
}
