//! Nonce persistence and replay protection
//!
//! This module provides persistent storage of used nonces to prevent
//! replay attacks across application restarts.

use crate::error::{Result, WalletError};
use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::fs;
use std::path::Path;

/// Persistent nonce store for replay protection
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NonceStore {
    /// Map of address -> set of used nonces
    used_nonces: std::collections::HashMap<String, HashSet<u64>>,
    /// Map of address -> highest confirmed nonce (for optimization)
    highest_nonce: std::collections::HashMap<String, u64>,
}

impl NonceStore {
    /// Create a new empty nonce store
    pub fn new() -> Self {
        Self {
            used_nonces: std::collections::HashMap::new(),
            highest_nonce: std::collections::HashMap::new(),
        }
    }

    /// Load nonce store from file, creating empty store if not exists
    pub fn load_or_create<P: AsRef<Path>>(path: P) -> Result<Self> {
        let path = path.as_ref();

        if !path.exists() {
            return Ok(Self::new());
        }

        let data = fs::read(path)?;
        let store: NonceStore = serde_json::from_slice(&data)
            .map_err(|e| WalletError::Storage(format!("Failed to parse nonce store: {}", e)))?;

        Ok(store)
    }

    /// Save nonce store to file
    pub fn save<P: AsRef<Path>>(&self, path: P) -> Result<()> {
        let path = path.as_ref();

        // Ensure parent directory exists
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }

        let data = serde_json::to_vec_pretty(self)?;
        fs::write(path, data)?;

        // Set restrictive permissions on Unix
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let mut perms = fs::metadata(path)?.permissions();
            perms.set_mode(0o600);
            fs::set_permissions(path, perms)?;
        }

        Ok(())
    }

    /// Mark a nonce as used for an address
    /// Returns true if this was a new nonce (not previously used)
    pub fn mark_used(&mut self, address: &str, nonce: u64) -> bool {
        let used = self.used_nonces.entry(address.to_string()).or_default();

        let is_new = used.insert(nonce);

        if is_new {
            // Update highest nonce tracker
            let highest = self.highest_nonce.entry(address.to_string()).or_insert(0);
            if nonce > *highest {
                *highest = nonce;
            }
        }

        is_new
    }

    /// Check if a nonce has been used for an address
    pub fn is_used(&self, address: &str, nonce: u64) -> bool {
        self.used_nonces
            .get(address)
            .map(|set| set.contains(&nonce))
            .unwrap_or(false)
    }

    /// Get the next suggested nonce for an address
    /// Returns highest_used_nonce + 1, or 0 if no nonces used yet
    pub fn get_next_nonce(&self, address: &str) -> u64 {
        self.highest_nonce.get(address).map(|h| h + 1).unwrap_or(0)
    }

    /// Get the highest used nonce for an address
    pub fn get_highest_nonce(&self, address: &str) -> Option<u64> {
        self.highest_nonce.get(address).copied()
    }

    /// Get count of used nonces for an address
    pub fn used_count(&self, address: &str) -> usize {
        self.used_nonces
            .get(address)
            .map(|set| set.len())
            .unwrap_or(0)
    }

    /// Check if a transaction nonce would be a replay
    /// Returns Ok(()) if nonce is valid, Err if it's a replay
    pub fn validate_nonce(&self, address: &str, nonce: u64) -> Result<()> {
        if self.is_used(address, nonce) {
            return Err(WalletError::Transaction(format!(
                "Nonce {} already used for address {} (replay attempt)",
                nonce, address
            )));
        }
        Ok(())
    }

    /// Clear all used nonces for an address (use with caution)
    pub fn clear_address(&mut self, address: &str) {
        self.used_nonces.remove(address);
        self.highest_nonce.remove(address);
    }

    /// Clear all stored nonces (use with caution - only for testing/reset)
    pub fn clear_all(&mut self) {
        self.used_nonces.clear();
        self.highest_nonce.clear();
    }

    /// Merge another nonce store into this one (union of used nonces).
    ///
    /// # Merge Semantics
    /// - **Used nonces**: Union of both stores (all used nonces preserved)
    /// - **Highest nonce**: Takes maximum value per address
    ///
    /// # Use Cases
    /// - **Wallet migration**: Combine nonce history from old/new storage
    /// - **Multi-device sync**: Merge nonce tracking across devices
    /// - **Backup restoration**: Merge restored data with current state
    ///
    /// # Arguments
    /// * `other` - NonceStore to merge into self
    ///
    /// # Example
    /// ```ignore
    /// let mut store1 = NonceStore::new();
    /// store1.mark_used("addr1", 0);
    ///
    /// let mut store2 = NonceStore::new();
    /// store2.mark_used("addr1", 1);
    ///
    /// store1.merge(&store2);
    /// // Now store1 has nonces 0 and 1 for addr1
    /// ```
    pub fn merge(&mut self, other: &NonceStore) {
        for (address, nonces) in &other.used_nonces {
            let used = self.used_nonces.entry(address.clone()).or_default();
            used.extend(nonces);
        }
        for (address, highest) in &other.highest_nonce {
            let entry = self.highest_nonce.entry(address.clone()).or_insert(0);
            if *highest > *entry {
                *entry = *highest;
            }
        }
    }
}

impl Default for NonceStore {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    #[test]
    fn test_nonce_store_basic() {
        let mut store = NonceStore::new();
        let address = "test_address_123";

        // Initially no nonces used
        assert!(!store.is_used(address, 0));
        assert_eq!(store.get_next_nonce(address), 0);

        // Mark nonce as used
        assert!(store.mark_used(address, 0));
        assert!(store.is_used(address, 0));
        assert_eq!(store.get_next_nonce(address), 1);

        // Mark same nonce again - should return false (already used)
        assert!(!store.mark_used(address, 0));

        // Mark more nonces
        assert!(store.mark_used(address, 1));
        assert!(store.mark_used(address, 5));

        assert_eq!(store.get_next_nonce(address), 6);
        assert_eq!(store.used_count(address), 3);
    }

    #[test]
    fn test_nonce_validation() {
        let mut store = NonceStore::new();
        let address = "test_address";

        // Valid nonce
        assert!(store.validate_nonce(address, 0).is_ok());

        // Mark as used
        store.mark_used(address, 0);

        // Now should fail validation (replay)
        assert!(store.validate_nonce(address, 0).is_err());

        // Different nonce should still be valid
        assert!(store.validate_nonce(address, 1).is_ok());
    }

    #[test]
    fn test_nonce_persistence() {
        let temp_dir = TempDir::new().unwrap();
        let path = temp_dir.path().join("nonces.json");

        // Create and populate store
        let mut store = NonceStore::new();
        store.mark_used("addr1", 0);
        store.mark_used("addr1", 1);
        store.mark_used("addr2", 5);

        // Save
        store.save(&path).unwrap();

        // Load from file
        let loaded = NonceStore::load_or_create(&path).unwrap();

        // Verify data persisted
        assert!(loaded.is_used("addr1", 0));
        assert!(loaded.is_used("addr1", 1));
        assert!(loaded.is_used("addr2", 5));
        assert!(!loaded.is_used("addr1", 2));
        assert_eq!(loaded.get_next_nonce("addr1"), 2);
        assert_eq!(loaded.get_next_nonce("addr2"), 6);
    }

    #[test]
    fn test_nonce_merge() {
        let mut store1 = NonceStore::new();
        store1.mark_used("addr1", 0);
        store1.mark_used("addr1", 1);

        let mut store2 = NonceStore::new();
        store2.mark_used("addr1", 2);
        store2.mark_used("addr2", 5);

        store1.merge(&store2);

        assert!(store1.is_used("addr1", 0));
        assert!(store1.is_used("addr1", 1));
        assert!(store1.is_used("addr1", 2));
        assert!(store1.is_used("addr2", 5));
        assert_eq!(store1.get_next_nonce("addr1"), 3);
    }

    #[test]
    fn test_clear_operations() {
        let mut store = NonceStore::new();
        store.mark_used("addr1", 0);
        store.mark_used("addr1", 1);
        store.mark_used("addr2", 5);

        // Clear single address
        store.clear_address("addr1");
        assert!(!store.is_used("addr1", 0));
        assert!(!store.is_used("addr1", 1));
        assert!(store.is_used("addr2", 5));

        // Clear all
        store.clear_all();
        assert!(!store.is_used("addr2", 5));
    }

    #[test]
    fn test_multiple_addresses() {
        let mut store = NonceStore::new();

        // Use nonces for multiple addresses
        // addr_0: 0, 3, 6, 9 (4 nonces)
        // addr_1: 1, 4, 7 (3 nonces)
        // addr_2: 2, 5, 8 (3 nonces)
        for i in 0..10 {
            store.mark_used(&format!("addr_{}", i % 3), i);
        }

        // Each address should have independent nonce tracking
        assert_eq!(store.used_count("addr_0"), 4);
        assert_eq!(store.used_count("addr_1"), 3);
        assert_eq!(store.used_count("addr_2"), 3);

        // Verify specific nonces
        assert!(store.is_used("addr_0", 0));
        assert!(store.is_used("addr_0", 3));
        assert!(store.is_used("addr_1", 1));
        assert!(store.is_used("addr_1", 4));
        assert!(store.is_used("addr_2", 2));
        assert!(store.is_used("addr_2", 5));
    }

    #[test]
    fn test_get_highest_nonce() {
        let mut store = NonceStore::new();
        let address = "test_address";

        // Initially no highest nonce
        assert_eq!(store.get_highest_nonce(address), None);

        // Mark some nonces
        store.mark_used(address, 0);
        assert_eq!(store.get_highest_nonce(address), Some(0));

        store.mark_used(address, 5);
        assert_eq!(store.get_highest_nonce(address), Some(5));

        store.mark_used(address, 3); // Lower than 5, shouldn't change highest
        assert_eq!(store.get_highest_nonce(address), Some(5));

        store.mark_used(address, 10);
        assert_eq!(store.get_highest_nonce(address), Some(10));
    }

    #[test]
    fn test_get_highest_nonce_multiple_addresses() {
        let mut store = NonceStore::new();

        store.mark_used("addr_a", 0);
        store.mark_used("addr_a", 5);
        store.mark_used("addr_b", 3);
        store.mark_used("addr_b", 7);

        assert_eq!(store.get_highest_nonce("addr_a"), Some(5));
        assert_eq!(store.get_highest_nonce("addr_b"), Some(7));
        assert_eq!(store.get_highest_nonce("addr_c"), None);
    }
}
