//! Local state persistence for mining operations.
//!
//! When the network is unavailable (Issue #7930), the miner continues to
//! track its state locally and can recover when connectivity returns.

use std::path::{Path, PathBuf};
use std::time::{Duration, SystemTime};

use serde::{Deserialize, Serialize};

/// Local state persisted across network outages.
///
/// This struct tracks mining progress locally so that if the node becomes
/// unreachable, the miner still knows where it left off.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LocalState {
    /// Number of consecutive heartbeat failures.
    pub consecutive_failures: u32,
    /// Local block height (tracks progress when offline).
    pub local_block_height: u64,
    /// Last known best block height from the node.
    pub best_block_height: u64,
    /// Timestamp when the outage started (if any).
    pub outage_start: Option<u64>,
    /// Number of peers seen last time node was reachable.
    pub last_seen_peers: u32,
    /// Number of attestations submitted locally.
    pub local_attestations: u64,
}

impl Default for LocalState {
    fn default() -> Self {
        Self {
            consecutive_failures: 0,
            local_block_height: 0,
            best_block_height: 0,
            outage_start: None,
            last_seen_peers: 0,
            local_attestations: 0,
        }
    }
}

impl LocalState {
    /// Mark a consecutive failure (call when heartbeat fails).
    pub fn with_consecutive_failure(self) -> Self {
        let now = SystemTime::now()
            .duration_since(SystemTime::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        Self {
            consecutive_failures: self.consecutive_failures + 1,
            outage_start: self.outage_start.or(Some(now)),
            ..self
        }
    }

    /// Mark recovery (call when heartbeat succeeds).
    pub fn with_recovery(self) -> Self {
        Self {
            consecutive_failures: 0,
            outage_start: None,
            ..self
        }
    }

    /// Calculate how long the miner has been offline.
    pub fn outage_duration(&self) -> Duration {
        if let Some(start) = self.outage_start {
            let now = SystemTime::now()
                .duration_since(SystemTime::UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs();
            Duration::from_secs(now.saturating_sub(start))
        } else {
            Duration::ZERO
        }
    }
}

/// Persistent state store backed by a JSON file.
pub struct StateStore {
    path: PathBuf,
}

impl StateStore {
    /// Create a new StateStore for the given file path.
    pub fn new(path: PathBuf) -> Self {
        Self { path }
    }

    /// Load state from disk. Returns default if file doesn't exist.
    pub fn load(&self) -> LocalState {
        if let Ok(contents) = std::fs::read_to_string(&self.path) {
            if let Ok(state) = serde_json::from_str(&contents) {
                return state;
            }
        }
        LocalState::default()
    }

    /// Save state to disk.
    pub fn save(&self, state: &LocalState) -> crate::Result<()> {
        let contents = serde_json::to_string_pretty(state)
            .map_err(|e| crate::MinerError::MinerError(format!("Failed to serialize state: {}", e)))?;
        std::fs::write(&self.path, contents)
            .map_err(|e| crate::MinerError::MinerError(format!("Failed to save state: {}", e)))?;
        Ok(())
    }
}

/// Get the default state file path.
pub fn default_state_path() -> PathBuf {
    let dir = dirs::state_dir()
        .unwrap_or_else(|| PathBuf::from("/tmp"));
    dir.join("rustchain-miner")
        .join("state.json")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn state_save_and_load_roundtrip() {
        let path = PathBuf::from("/tmp/test_state_store.json");
        let _ = std::fs::remove_file(&path);
        
        let store = StateStore::new(path.clone());
        
        let original = LocalState {
            consecutive_failures: 5,
            local_block_height: 42,
            best_block_height: 40,
            outage_start: Some(1234567890),
            last_seen_peers: 10,
            local_attestations: 3,
        };
        
        store.save(&original).unwrap();
        let loaded = store.load();
        
        assert_eq!(loaded.consecutive_failures, 5);
        assert_eq!(loaded.local_block_height, 42);
        assert_eq!(loaded.best_block_height, 40);
        assert_eq!(loaded.outage_start, Some(1234567890));
        assert_eq!(loaded.last_seen_peers, 10);
        assert_eq!(loaded.local_attestations, 3);
        
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn state_load_returns_default_when_file_missing() {
        let path = PathBuf::from("/tmp/test_state_missing.json");
        let _ = std::fs::remove_file(&path);
        
        let store = StateStore::new(path.clone());
        let state = store.load();
        
        assert_eq!(state.consecutive_failures, 0);
        assert_eq!(state.local_block_height, 0);
        
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn outage_duration_calculation() {
        let mut state = LocalState::default();
        
        // No outage -> zero duration
        assert!(state.outage_duration().as_secs() == 0);
        
        // Set an outage start
        let two_secs_ago = SystemTime::now()
            .duration_since(SystemTime::UNIX_EPOCH)
            .unwrap()
            .as_secs() - 2;
        
        state.outage_start = Some(two_secs_ago);
        let duration = state.outage_duration();
        
        assert!(duration.as_secs() >= 1);
        assert!(duration.as_secs() <= 3); // Allow for timing variance
    }

    #[test]
    fn consecutive_failure_increments() {
        let state = LocalState::default();
        let failed = state.with_consecutive_failure();
        
        assert_eq!(failed.consecutive_failures, 1);
        assert!(failed.outage_start.is_some());
        
        let failed2 = failed.with_consecutive_failure();
        assert_eq!(failed2.consecutive_failures, 2);
    }

    #[test]
    fn recovery_resets_counters() {
        let mut state = LocalState::default();
        state.consecutive_failures = 5;
        state.outage_start = Some(1234567890);
        
        let recovered = state.with_recovery();
        
        assert_eq!(recovered.consecutive_failures, 0);
        assert_eq!(recovered.outage_start, None);
    }
}
