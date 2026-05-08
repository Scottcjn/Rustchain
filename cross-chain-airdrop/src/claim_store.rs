//! Persistent claim store for duplicate-claim prevention
//!
//! The default [`InMemoryClaimStore`] loses state on restart, which means
//! duplicate claims become possible if the process is restarted between
//! claims (e.g. each invocation of the `airdrop-cli` CLI).
//!
//! For production use, prefer [`SqliteClaimStore`], which persists claimed
//! GitHub IDs and wallet addresses to a local SQLite file so duplicates are
//! rejected even after restart.

use crate::error::{AirdropError, Result};
use crate::models::{ClaimRecord, ClaimStatus};
use chrono::Utc;
use std::collections::HashSet;
use std::sync::Mutex;

// ---------------------------------------------------------------------------
// Trait
// ---------------------------------------------------------------------------

/// Abstract store for claim deduplication state.
///
/// Implementations must be `Send + Sync` so they can be shared across
/// async tasks.
pub trait ClaimStore: Send + Sync {
    /// Return true if the GitHub account has already claimed.
    fn is_github_claimed(&self, github_id: u64) -> Result<bool>;

    /// Return true if the wallet has already claimed on the given chain.
    fn is_wallet_claimed(&self, chain: &str, address: &str) -> Result<bool>;

    /// Atomically record a new claim.  Returns an error if either key
    /// already exists (implementations should enforce uniqueness).
    fn record_claim(
        &self,
        github_id: u64,
        chain: &str,
        address: &str,
        record: ClaimRecord,
    ) -> Result<()>;

    /// Look up a stored claim by ID.
    fn get_claim(&self, claim_id: &str) -> Result<Option<ClaimRecord>>;

    /// Update the status of an existing claim.
    fn update_claim(
        &self,
        claim_id: &str,
        status: ClaimStatus,
        lock_id: Option<String>,
        rejection_reason: Option<String>,
    ) -> Result<()>;

    /// Return all stored claims.
    fn get_claims(&self) -> Result<Vec<ClaimRecord>>;
}

// ---------------------------------------------------------------------------
// In-memory implementation (current behaviour — NOT durable)
// ---------------------------------------------------------------------------

/// Volatile, in-memory claim store.
///
/// This is the **existing behaviour** of `VerificationPipeline`.  It is
/// provided for backward compatibility and testing, but **should not be
/// used in production** because all deduplication state is lost on
/// process restart, allowing duplicate claims.
#[derive(Default)]
pub struct InMemoryClaimStore {
    claims: Mutex<Vec<ClaimRecord>>,
    claimed_github_ids: Mutex<HashSet<u64>>,
    claimed_wallets: Mutex<HashSet<String>>,
}

impl InMemoryClaimStore {
    pub fn new() -> Self {
        Self::default()
    }
}

impl ClaimStore for InMemoryClaimStore {
    fn is_github_claimed(&self, github_id: u64) -> Result<bool> {
        let set = self
            .claimed_github_ids
            .lock()
            .map_err(|e| AirdropError::Claim(format!("Lock poisoning: {}", e)))?;
        Ok(set.contains(&github_id))
    }

    fn is_wallet_claimed(&self, chain: &str, address: &str) -> Result<bool> {
        let set = self
            .claimed_wallets
            .lock()
            .map_err(|e| AirdropError::Claim(format!("Lock poisoning: {}", e)))?;
        Ok(set.contains(&format!("{}:{}", chain, address)))
    }

    fn record_claim(
        &self,
        github_id: u64,
        chain: &str,
        address: &str,
        record: ClaimRecord,
    ) -> Result<()> {
        // Check uniqueness before inserting (mimics DB constraint)
        if self.is_github_claimed(github_id)? {
            return Err(AirdropError::Claim(format!(
                "GitHub account {} has already claimed airdrop",
                record.github_login
            )));
        }
        if self.is_wallet_claimed(chain, address)? {
            return Err(AirdropError::Claim(format!(
                "Wallet {} on {} has already claimed airdrop",
                address, chain
            )));
        }

        let mut claims = self
            .claims
            .lock()
            .map_err(|e| AirdropError::Claim(format!("Lock poisoning: {}", e)))?;
        claims.push(record);

        let mut gh = self
            .claimed_github_ids
            .lock()
            .map_err(|e| AirdropError::Claim(format!("Lock poisoning: {}", e)))?;
        gh.insert(github_id);

        let mut wl = self
            .claimed_wallets
            .lock()
            .map_err(|e| AirdropError::Claim(format!("Lock poisoning: {}", e)))?;
        wl.insert(format!("{}:{}", chain, address));

        Ok(())
    }

    fn get_claim(&self, claim_id: &str) -> Result<Option<ClaimRecord>> {
        let claims = self
            .claims
            .lock()
            .map_err(|e| AirdropError::Claim(format!("Lock poisoning: {}", e)))?;
        Ok(claims.iter().find(|c| c.claim_id == claim_id).cloned())
    }

    fn update_claim(
        &self,
        claim_id: &str,
        status: ClaimStatus,
        lock_id: Option<String>,
        rejection_reason: Option<String>,
    ) -> Result<()> {
        let mut claims = self
            .claims
            .lock()
            .map_err(|e| AirdropError::Claim(format!("Lock poisoning: {}", e)))?;
        if let Some(claim) = claims.iter_mut().find(|c| c.claim_id == claim_id) {
            claim.status = status;
            claim.updated_at = Utc::now();
            if let Some(lid) = lock_id {
                claim.lock_id = Some(lid);
            }
            claim.rejection_reason = rejection_reason;
            Ok(())
        } else {
            Err(AirdropError::Claim(format!(
                "Claim not found: {}",
                claim_id
            )))
        }
    }

    fn get_claims(&self) -> Result<Vec<ClaimRecord>> {
        let claims = self
            .claims
            .lock()
            .map_err(|e| AirdropError::Claim(format!("Lock poisoning: {}", e)))?;
        Ok(claims.clone())
    }
}

// ---------------------------------------------------------------------------
// SQLite implementation (durable)
// ---------------------------------------------------------------------------

/// SQLite-backed claim store.
///
/// Persists deduplication state to a local file so duplicate claims are
/// rejected even after process restart.
#[cfg(feature = "sqlite-store")]
pub struct SqliteClaimStore {
    conn: std::sync::Arc<Mutex<rusqlite::Connection>>,
}

#[cfg(feature = "sqlite-store")]
impl SqliteClaimStore {
    /// Open (or create) a SQLite database at the given path.
    pub fn open(path: &str) -> Result<Self> {
        let conn = rusqlite::Connection::open(path)
            .map_err(|e| AirdropError::Claim(format!("Failed to open claim store DB: {}", e)))?;

        conn.execute_batch(
            "
            CREATE TABLE IF NOT EXISTS claims (
                claim_id    TEXT PRIMARY KEY,
                github_id   INTEGER NOT NULL,
                chain       TEXT NOT NULL,
                address     TEXT NOT NULL,
                record_json TEXT NOT NULL,
                UNIQUE(github_id),
                UNIQUE(chain, address)
            );
            ",
        )
        .map_err(|e| AirdropError::Claim(format!("Failed to init claim store schema: {}", e)))?;

        Ok(Self {
            conn: std::sync::Arc::new(Mutex::new(conn)),
        })
    }

    /// Create an ephemeral in-memory database (useful for testing).
    pub fn memory() -> Result<Self> {
        Self::open(":memory:")
    }
}

#[cfg(feature = "sqlite-store")]
impl ClaimStore for SqliteClaimStore {
    fn is_github_claimed(&self, github_id: u64) -> Result<bool> {
        let conn = self
            .conn
            .lock()
            .map_err(|e| AirdropError::Claim(format!("Lock poisoning: {}", e)))?;
        let mut stmt = conn
            .prepare("SELECT COUNT(*) FROM claims WHERE github_id = ?")
            .map_err(|e| AirdropError::Claim(format!("SQL prepare error: {}", e)))?;
        let count: i64 = stmt
            .query_row([github_id], |row| row.get(0))
            .map_err(|e| AirdropError::Claim(format!("SQL query error: {}", e)))?;
        Ok(count > 0)
    }

    fn is_wallet_claimed(&self, chain: &str, address: &str) -> Result<bool> {
        let conn = self
            .conn
            .lock()
            .map_err(|e| AirdropError::Claim(format!("Lock poisoning: {}", e)))?;
        let mut stmt = conn
            .prepare("SELECT COUNT(*) FROM claims WHERE chain = ? AND address = ?")
            .map_err(|e| AirdropError::Claim(format!("SQL prepare error: {}", e)))?;
        let count: i64 = stmt
            .query_row([chain, address], |row| row.get(0))
            .map_err(|e| AirdropError::Claim(format!("SQL query error: {}", e)))?;
        Ok(count > 0)
    }

    fn record_claim(
        &self,
        github_id: u64,
        chain: &str,
        address: &str,
        record: ClaimRecord,
    ) -> Result<()> {
        let json = serde_json::to_string(&record)
            .map_err(|e| AirdropError::Claim(format!("Failed to serialize claim: {}", e)))?;

        let conn = self
            .conn
            .lock()
            .map_err(|e| AirdropError::Claim(format!("Lock poisoning: {}", e)))?;

        conn.execute(
            "INSERT INTO claims (claim_id, github_id, chain, address, record_json)
             VALUES (?, ?, ?, ?, ?)",
            [
                &record.claim_id,
                &github_id.to_string(),
                chain,
                address,
                &json,
            ],
        )
        .map_err(|e: rusqlite::Error| {
            let msg = e.to_string();
            if msg.contains("UNIQUE") || msg.contains("unique") {
                if msg.contains("github_id") {
                    AirdropError::Claim(format!(
                        "GitHub account {} has already claimed airdrop",
                        record.github_login
                    ))
                } else {
                    AirdropError::Claim(format!(
                        "Wallet {} on {} has already claimed airdrop",
                        address, chain
                    ))
                }
            } else {
                AirdropError::Claim(format!("Failed to record claim: {}", e))
            }
        })?;

        Ok(())
    }

    fn get_claim(&self, claim_id: &str) -> Result<Option<ClaimRecord>> {
        let conn = self
            .conn
            .lock()
            .map_err(|e| AirdropError::Claim(format!("Lock poisoning: {}", e)))?;
        let mut stmt = conn
            .prepare("SELECT record_json FROM claims WHERE claim_id = ?")
            .map_err(|e| AirdropError::Claim(format!("SQL prepare error: {}", e)))?;
        let result: std::result::Result<String, rusqlite::Error> =
            stmt.query_row([claim_id], |row| row.get(0));

        match result {
            Ok(json) => {
                let record: ClaimRecord = serde_json::from_str(&json).map_err(|e| {
                    AirdropError::Claim(format!("Failed to deserialize claim: {}", e))
                })?;
                Ok(Some(record))
            }
            Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
            Err(e) => Err(AirdropError::Claim(format!("SQL query error: {}", e))),
        }
    }

    fn update_claim(
        &self,
        claim_id: &str,
        status: ClaimStatus,
        lock_id: Option<String>,
        rejection_reason: Option<String>,
    ) -> Result<()> {
        let conn = self
            .conn
            .lock()
            .map_err(|e| AirdropError::Claim(format!("Lock poisoning: {}", e)))?;

        let mut stmt = conn
            .prepare("SELECT record_json FROM claims WHERE claim_id = ?")
            .map_err(|e| AirdropError::Claim(format!("SQL prepare error: {}", e)))?;
        let result: std::result::Result<String, rusqlite::Error> =
            stmt.query_row([claim_id], |row| row.get(0));

        let json = result.map_err(|e| match e {
            rusqlite::Error::QueryReturnedNoRows => {
                AirdropError::Claim(format!("Claim not found: {}", claim_id))
            }
            other => AirdropError::Claim(format!("SQL query error: {}", other)),
        })?;

        let mut record: ClaimRecord = serde_json::from_str(&json)
            .map_err(|e| AirdropError::Claim(format!("Failed to deserialize claim: {}", e)))?;

        record.status = status;
        record.updated_at = Utc::now();
        if let Some(lid) = lock_id {
            record.lock_id = Some(lid);
        }
        record.rejection_reason = rejection_reason;

        let json = serde_json::to_string(&record)
            .map_err(|e| AirdropError::Claim(format!("Failed to serialize claim: {}", e)))?;
        conn.execute(
            "UPDATE claims SET record_json = ? WHERE claim_id = ?",
            [&json, claim_id],
        )
        .map_err(|e| AirdropError::Claim(format!("Failed to update claim: {}", e)))?;

        Ok(())
    }

    fn get_claims(&self) -> Result<Vec<ClaimRecord>> {
        let conn = self
            .conn
            .lock()
            .map_err(|e| AirdropError::Claim(format!("Lock poisoning: {}", e)))?;
        let mut stmt = conn
            .prepare("SELECT record_json FROM claims")
            .map_err(|e| AirdropError::Claim(format!("SQL prepare error: {}", e)))?;
        let mut rows = stmt
            .query([])
            .map_err(|e| AirdropError::Claim(format!("SQL query error: {}", e)))?;

        let mut claims = Vec::new();
        while let Some(row) = rows
            .next()
            .map_err(|e| AirdropError::Claim(format!("SQL row iteration error: {}", e)))?
        {
            let json: String = row
                .get(0)
                .map_err(|e| AirdropError::Claim(format!("SQL row error: {}", e)))?;
            let record: ClaimRecord = serde_json::from_str(&json)
                .map_err(|e| AirdropError::Claim(format!("Failed to deserialize claim: {}", e)))?;
            claims.push(record);
        }
        Ok(claims)
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::{ClaimStatus, TargetChain};

    fn test_record() -> ClaimRecord {
        let now = Utc::now();
        ClaimRecord {
            claim_id: "test-claim-001".to_string(),
            github_login: "testuser".to_string(),
            github_id: 12345,
            rtc_wallet: "RTCwallet1".to_string(),
            target_chain: TargetChain::Solana,
            target_address: "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU".to_string(),
            status: ClaimStatus::Pending,
            base_allocation: 100,
            multiplier: 1.0,
            final_allocation: 100,
            lock_id: None,
            bridge_tx_hash: None,
            rejection_reason: None,
            created_at: now,
            updated_at: now,
        }
    }

    // --- InMemoryClaimStore tests ---

    #[test]
    fn test_inmemory_record_and_dedup() {
        let store = InMemoryClaimStore::new();
        let rec = test_record();

        // First claim should succeed
        store
            .record_claim(rec.github_id, "solana", &rec.target_address, rec.clone())
            .unwrap();

        // Duplicate GitHub should fail
        assert!(store
            .record_claim(rec.github_id, "solana", "different_address", rec.clone())
            .is_err());

        // Duplicate wallet should fail
        assert!(store
            .record_claim(99999, "solana", &rec.target_address, rec.clone())
            .is_err());

        // Different GitHub + different wallet should succeed
        let mut rec2 = rec.clone();
        rec2.claim_id = "test-claim-002".to_string();
        rec2.github_id = 99999;
        rec2.github_login = "otheruser".to_string();
        rec2.target_address = "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM".to_string();
        let addr2 = rec2.target_address.clone();
        store
            .record_claim(rec2.github_id, "solana", &addr2, rec2)
            .unwrap();
    }

    #[test]
    fn test_inmemory_get_and_update_claim() {
        let store = InMemoryClaimStore::new();
        let rec = test_record();
        let addr = rec.target_address.clone();
        store
            .record_claim(rec.github_id, "solana", &addr, rec.clone())
            .unwrap();

        // Retrieve
        let found = store.get_claim(&rec.claim_id).unwrap().unwrap();
        assert_eq!(found.status, ClaimStatus::Pending);

        // Update
        store
            .update_claim(
                &rec.claim_id,
                ClaimStatus::Complete,
                Some("lock-1".to_string()),
                None,
            )
            .unwrap();

        let updated = store.get_claim(&rec.claim_id).unwrap().unwrap();
        assert_eq!(updated.status, ClaimStatus::Complete);
        assert_eq!(updated.lock_id, Some("lock-1".to_string()));
    }

    #[test]
    fn test_inmemory_get_claims() {
        let store = InMemoryClaimStore::new();
        assert_eq!(store.get_claims().unwrap().len(), 0);

        let rec = test_record();
        let addr = rec.target_address.clone();
        store
            .record_claim(rec.github_id, "solana", &addr, rec)
            .unwrap();

        assert_eq!(store.get_claims().unwrap().len(), 1);
    }

    // --- SqliteClaimStore tests (feature-gated) ---

    #[cfg(feature = "sqlite-store")]
    #[test]
    fn test_sqlite_record_and_dedup() {
        let store = SqliteClaimStore::memory().unwrap();
        let rec = test_record();
        let addr = rec.target_address.clone();
        store
            .record_claim(rec.github_id, "solana", &addr, rec.clone())
            .unwrap();

        // Duplicate GitHub
        assert!(store
            .record_claim(rec.github_id, "solana", "different_address", rec.clone())
            .is_err());

        // Duplicate wallet
        assert!(store
            .record_claim(99999, "solana", &rec.target_address, rec.clone())
            .is_err());

        // Different keys → OK
        let mut rec2 = rec.clone();
        rec2.claim_id = "test-claim-002".to_string();
        rec2.github_id = 99999;
        rec2.github_login = "otheruser".to_string();
        rec2.target_address = "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM".to_string();
        let addr2 = rec2.target_address.clone();
        store
            .record_claim(rec2.github_id, "solana", &addr2, rec2)
            .unwrap();
    }

    #[cfg(feature = "sqlite-store")]
    #[test]
    fn test_sqlite_survives_reopen() {
        let path = std::env::temp_dir().join("airdrop_claim_store_test.sqlite");
        let _ = std::fs::remove_file(&path);

        {
            let store = SqliteClaimStore::open(path.to_str().unwrap()).unwrap();
            let rec = test_record();
            let addr = rec.target_address.clone();
            store
                .record_claim(rec.github_id, "solana", &addr, rec)
                .unwrap();
        }

        {
            let store = SqliteClaimStore::open(path.to_str().unwrap()).unwrap();
            assert!(store.is_github_claimed(12345).unwrap());
            assert!(store
                .is_wallet_claimed("solana", "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU")
                .unwrap());

            let rec2 = test_record();
            let addr2 = rec2.target_address.clone();
            assert!(store
                .record_claim(rec2.github_id, "solana", &addr2, rec2)
                .is_err());
        }

        let _ = std::fs::remove_file(&path);
    }

    #[cfg(feature = "sqlite-store")]
    #[test]
    fn test_sqlite_get_and_update_claim() {
        let store = SqliteClaimStore::memory().unwrap();
        let rec = test_record();
        let addr = rec.target_address.clone();
        store
            .record_claim(rec.github_id, "solana", &addr, rec.clone())
            .unwrap();

        let found = store.get_claim(&rec.claim_id).unwrap().unwrap();
        assert_eq!(found.status, ClaimStatus::Pending);

        store
            .update_claim(
                &rec.claim_id,
                ClaimStatus::Complete,
                Some("lock-1".to_string()),
                None,
            )
            .unwrap();

        let updated = store.get_claim(&rec.claim_id).unwrap().unwrap();
        assert_eq!(updated.status, ClaimStatus::Complete);
        assert_eq!(updated.lock_id, Some("lock-1".to_string()));
    }
}
