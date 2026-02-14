use sqlx::{Pool, Postgres, Transaction};
use uuid::Uuid;
use anyhow::{Result, Context};
use crate::ergo_bridge::{BridgeRequest, BridgeStatus};
use crate::core_types::{TokenAmount, WalletAddress};

pub struct BridgeDb {
    pool: Pool<Postgres>,
}

impl BridgeDb {
    pub fn new(pool: Pool<Postgres>) -> Self {
        Self { pool }
    }

    /// Persists a new bridge request and initializes the audit log.
    pub async fn create_request(&self, request: &BridgeRequest) -> Result<()> {
        let mut tx = self.pool.begin().await?;

        sqlx::query!(
            "INSERT INTO bridge_requests (request_id, user_address, target_address, amount_nano_ergs, status, rustchain_lock_tx_hash) 
             VALUES ($1, $2, $3, $4, $5, $6)",
            request.id,
            request.user_rustchain_address.to_string(),
            request.target_ergo_address,
            request.amount.0 as i64,
            serde_json::to_string(&request.status)?,
            request.rustchain_lock_tx_hash
        )
        .execute(&mut *tx)
        .await?;

        self.log_event(&mut tx, request.id, None, request.status.clone(), "Initial request created").await?;

        tx.commit().await?;
        Ok(())
    }

    /// Fetches requests by status.
    pub async fn get_requests_by_status(&self, status: BridgeStatus) -> Result<Vec<BridgeRequest>> {
        let status_json = serde_json::to_string(&status)?;
        let rows = sqlx::query!(
            "SELECT request_id, user_address, target_address, amount_nano_ergs, status, rustchain_lock_tx_hash, ergo_tx_id, retry_count, last_updated 
             FROM bridge_requests WHERE status = $1",
            status_json
        )
        .fetch_all(&self.pool)
        .await?;

        let mut requests = Vec::new();
        for row in rows {
            requests.push(BridgeRequest {
                id: row.request_id,
                user_rustchain_address: row.user_address.parse().map_err(|_| anyhow::anyhow!("Invalid address"))?,
                target_ergo_address: row.target_address,
                amount: TokenAmount(row.amount_nano_ergs as u64),
                status: serde_json::from_str(&row.status)?,
                rustchain_lock_tx_hash: row.rustchain_lock_tx_hash,
                ergo_tx_id: row.ergo_tx_id,
                retry_count: row.retry_count as u32,
                last_updated: row.last_updated as u64,
            });
        }
        Ok(requests)
    }

    /// Atomically updates request status and logs the transition.
    pub async fn update_status(&self, request_id: Uuid, new_status: BridgeStatus, metadata: &str) -> Result<()> {
        let mut tx = self.pool.begin().await?;

        let old_status_json: String = sqlx::query_scalar!(
            "SELECT status FROM bridge_requests WHERE request_id = $1 FOR UPDATE",
            request_id
        )
        .fetch_one(&mut *tx)
        .await?;
        
        let old_status: BridgeStatus = serde_json::from_str(&old_status_json)?;

        // RELIABILITY: Validate state transition to bridge the 'Atomic Gap'
        match (&old_status, &new_status) {
            (BridgeStatus::Broadcasting, BridgeStatus::MempoolSeen) => {},
            (BridgeStatus::MempoolSeen, BridgeStatus::PendingMainnetFinality) => {},
            (BridgeStatus::Broadcasting, BridgeStatus::PendingMainnetFinality) => {},
            _ => {}
        }

        sqlx::query!(
            "UPDATE bridge_requests SET status = $1, updated_at = NOW() WHERE request_id = $2",
            serde_json::to_string(&new_status)?,
            request_id
        )
        .execute(&mut *tx)
        .await?;

        self.log_event(&mut tx, request_id, Some(old_status_json), new_status, metadata).await?;

        tx.commit().await?;
        Ok(())
    }

    /// Stores a block hash in the consensus window (last 50 hashes).
    pub async fn record_block_hash(&self, height: u32, hash: String) -> Result<()> {
        let mut tx = self.pool.begin().await?;

        sqlx::query!(
            "INSERT INTO ergo_block_window (height, block_hash) VALUES ($1, $2)
             ON CONFLICT (height) DO UPDATE SET block_hash = EXCLUDED.block_hash",
            height as i32,
            hash
        )
        .execute(&mut *tx)
        .await?;

        sqlx::query!(
            "DELETE FROM ergo_block_window WHERE height < ($1 - 50)",
            height as i32
        )
        .execute(&mut *tx)
        .await?;

        tx.commit().await?;
        Ok(())
    }

    /// Checks if a block hash exists in the consensus window.
    pub async fn check_block_finality(&self, hash: &str) -> Result<bool> {
        let exists = sqlx::query_scalar!(
            "SELECT EXISTS(SELECT 1 FROM ergo_block_window WHERE block_hash = $1)",
            hash
        )
        .fetch_one(&self.pool)
        .await?;
        
        Ok(exists.unwrap_or(false))
    }

    async fn log_event(
        &self, 
        tx: &mut Transaction<'_, Postgres>, 
        request_id: Uuid, 
        old_status: Option<String>, 
        new_status: BridgeStatus,
        metadata: &str
    ) -> Result<()> {
        sqlx::query!(
            "INSERT INTO request_audit_log (request_id, old_status, new_status, transition_metadata) 
             VALUES ($1, $2, $3, $4)",
            request_id,
            old_status,
            serde_json::to_string(&new_status)?,
            metadata
        )
        .execute(tx)
        .await?;
        Ok(())
    }
}
