//! Transaction handling for RustChain Wallet
//!
//! This module provides transaction creation, signing, and serialization.

use serde::{Serialize, Deserialize};
use chrono::{DateTime, Utc};
use crate::error::{Result, WalletError};
use crate::keys::KeyPair;
use crate::nonce_store::NonceStore;

/// A RustChain transaction
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Transaction {
    /// Sender address (Base58 encoded)
    pub from: String,
    /// Recipient address (Base58 encoded)
    pub to: String,
    /// Amount in the smallest unit (like satoshis)
    pub amount: u64,
    /// Transaction fee
    pub fee: u64,
    /// Nonce to prevent replay attacks
    pub nonce: u64,
    /// Transaction timestamp
    pub timestamp: DateTime<Utc>,
    /// Optional memo/note
    pub memo: Option<String>,
    /// Signature (hex encoded)
    pub signature: Option<String>,
}

impl Transaction {
    /// Create a new unsigned transaction
    pub fn new(from: String, to: String, amount: u64, fee: u64, nonce: u64) -> Self {
        Self {
            from,
            to,
            amount,
            fee,
            nonce,
            timestamp: Utc::now(),
            memo: None,
            signature: None,
        }
    }

    /// Add a memo to the transaction
    pub fn with_memo(mut self, memo: String) -> Self {
        self.memo = Some(memo);
        self
    }

    /// Get the total cost of the transaction (amount + fee)
    pub fn total_cost(&self) -> u64 {
        self.amount + self.fee
    }

    /// Serialize the transaction for signing (excludes signature field)
    pub fn serialize_for_signing(&self) -> Result<Vec<u8>> {
        let tx = UnsignedTransaction {
            from: self.from.clone(),
            to: self.to.clone(),
            amount: self.amount,
            fee: self.fee,
            nonce: self.nonce,
            timestamp: self.timestamp.timestamp(),
            memo: self.memo.clone(),
        };
        
        let json = serde_json::to_string(&tx)?;
        Ok(json.into_bytes())
    }

    /// Sign the transaction with a keypair
    pub fn sign(&mut self, keypair: &KeyPair) -> Result<()> {
        let message = self.serialize_for_signing()?;
        let signature = keypair.sign(&message)?;
        self.signature = Some(hex::encode(&signature));
        Ok(())
    }

    /// Verify the transaction signature
    pub fn verify(&self, keypair: &KeyPair) -> Result<bool> {
        let signature = self.signature.as_ref()
            .ok_or_else(|| WalletError::Transaction("Transaction not signed".to_string()))?;
        
        let sig_bytes = hex::decode(signature)?;
        let message = self.serialize_for_signing()?;
        
        keypair.verify(&message, &sig_bytes)
    }

    /// Verify the transaction signature against a public key
    pub fn verify_with_pubkey(&self, public_key: &KeyPair) -> Result<bool> {
        let signature = self.signature.as_ref()
            .ok_or_else(|| WalletError::Transaction("Transaction not signed".to_string()))?;
        
        let sig_bytes = hex::decode(signature)?;
        let message = self.serialize_for_signing()?;
        
        public_key.verify(&message, &sig_bytes)
    }

    /// Get the transaction hash (for display/reference purposes)
    pub fn hash(&self) -> Result<String> {
        use sha2::{Sha256, Digest};
        
        let message = self.serialize_for_signing()?;
        let hash = Sha256::digest(&message);
        Ok(hex::encode(&hash))
    }

    /// Serialize the complete transaction to JSON
    pub fn to_json(&self) -> Result<String> {
        Ok(serde_json::to_string_pretty(self)?)
    }

    /// Deserialize a transaction from JSON
    pub fn from_json(json: &str) -> Result<Self> {
        Ok(serde_json::from_str(json)?)
    }

    /// Verify the transaction nonce against a nonce store (replay protection)
    /// Returns Ok(()) if the nonce is valid (not previously used)
    /// Returns Err if the nonce has already been used (replay attempt)
    pub fn verify_nonce(&self, nonce_store: &NonceStore) -> Result<()> {
        nonce_store.validate_nonce(&self.from, self.nonce)
    }

    /// Verify both signature and nonce (complete transaction validation)
    /// Returns Ok(true) if signature is valid and nonce is not a replay
    pub fn verify_complete(&self, keypair: &KeyPair, nonce_store: &NonceStore) -> Result<bool> {
        // First check for replay
        self.verify_nonce(nonce_store)?;
        // Then verify signature
        self.verify(keypair)
    }
}

/// Internal structure for signing (excludes signature)
#[derive(Serialize, Deserialize)]
struct UnsignedTransaction {
    from: String,
    to: String,
    amount: u64,
    fee: u64,
    nonce: u64,
    timestamp: i64,
    memo: Option<String>,
}

/// Transaction builder for fluent API
pub struct TransactionBuilder {
    from: Option<String>,
    to: Option<String>,
    amount: u64,
    fee: u64,
    nonce: u64,
    memo: Option<String>,
}

impl TransactionBuilder {
    /// Create a new transaction builder
    pub fn new() -> Self {
        Self {
            from: None,
            to: None,
            amount: 0,
            fee: 1000, // Default fee
            nonce: 0,
            memo: None,
        }
    }

    /// Set the sender address
    pub fn from(mut self, address: String) -> Self {
        self.from = Some(address);
        self
    }

    /// Set the recipient address
    pub fn to(mut self, address: String) -> Self {
        self.to = Some(address);
        self
    }

    /// Set the amount to transfer
    pub fn amount(mut self, amount: u64) -> Self {
        self.amount = amount;
        self
    }

    /// Set the transaction fee
    pub fn fee(mut self, fee: u64) -> Self {
        self.fee = fee;
        self
    }

    /// Set the nonce
    pub fn nonce(mut self, nonce: u64) -> Self {
        self.nonce = nonce;
        self
    }

    /// Set the memo
    pub fn memo(mut self, memo: String) -> Self {
        self.memo = Some(memo);
        self
    }

    /// Build the transaction
    pub fn build(self) -> Result<Transaction> {
        let from = self.from.ok_or_else(|| {
            WalletError::Transaction("Sender address not set".to_string())
        })?;
        
        let to = self.to.ok_or_else(|| {
            WalletError::Transaction("Recipient address not set".to_string())
        })?;

        if self.amount == 0 {
            return Err(WalletError::Transaction("Amount must be greater than 0".to_string()));
        }

        let mut tx = Transaction::new(from, to, self.amount, self.fee, self.nonce);
        if let Some(memo) = self.memo {
            tx = tx.with_memo(memo);
        }
        
        Ok(tx)
    }
}

impl Default for TransactionBuilder {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_transaction_creation() {
        let tx = Transaction::new(
            "sender_address".to_string(),
            "recipient_address".to_string(),
            1000,
            100,
            1,
        );
        
        assert_eq!(tx.amount, 1000);
        assert_eq!(tx.fee, 100);
        assert_eq!(tx.total_cost(), 1100);
        assert!(tx.signature.is_none());
    }

    #[test]
    fn test_transaction_with_memo() {
        let tx = Transaction::new(
            "from".to_string(),
            "to".to_string(),
            1000,
            100,
            1,
        ).with_memo("Test memo".to_string());
        
        assert_eq!(tx.memo, Some("Test memo".to_string()));
    }

    #[test]
    fn test_transaction_signing() {
        let keypair = KeyPair::generate();
        let mut tx = Transaction::new(
            keypair.public_key_base58(),
            "recipient".to_string(),
            1000,
            100,
            1,
        );
        
        tx.sign(&keypair).unwrap();
        assert!(tx.signature.is_some());
        
        let valid = tx.verify(&keypair).unwrap();
        assert!(valid);
    }

    #[test]
    fn test_transaction_serialization() {
        let keypair = KeyPair::generate();
        let mut tx = Transaction::new(
            keypair.public_key_base58(),
            "recipient".to_string(),
            1000,
            100,
            1,
        ).with_memo("Test".to_string());
        
        tx.sign(&keypair).unwrap();
        
        let json = tx.to_json().unwrap();
        let loaded = Transaction::from_json(&json).unwrap();
        
        assert_eq!(tx.from, loaded.from);
        assert_eq!(tx.to, loaded.to);
        assert_eq!(tx.amount, loaded.amount);
        assert_eq!(tx.signature, loaded.signature);
    }

    #[test]
    fn test_transaction_builder() {
        let keypair = KeyPair::generate();
        let tx = TransactionBuilder::new()
            .from(keypair.public_key_base58())
            .to("recipient".to_string())
            .amount(5000)
            .fee(200)
            .nonce(42)
            .memo("Builder test".to_string())
            .build()
            .unwrap();
        
        assert_eq!(tx.amount, 5000);
        assert_eq!(tx.fee, 200);
        assert_eq!(tx.nonce, 42);
        assert_eq!(tx.memo, Some("Builder test".to_string()));
    }

    #[test]
    fn test_transaction_hash() {
        let tx = Transaction::new(
            "from".to_string(),
            "to".to_string(),
            1000,
            100,
            1,
        );

        let hash = tx.hash().unwrap();
        assert_eq!(hash.len(), 64); // SHA256 hex
    }

    // ==================== Replay Protection Tests ====================

    #[test]
    fn test_transaction_nonce_verification() {
        let keypair = KeyPair::generate();
        let mut tx = Transaction::new(
            keypair.public_key_base58(),
            "recipient".to_string(),
            1000,
            100,
            0,
        );
        tx.sign(&keypair).unwrap();

        let nonce_store = NonceStore::new();

        // First use should succeed
        assert!(tx.verify_nonce(&nonce_store).is_ok());

        // Mark nonce as used
        let mut store2 = NonceStore::new();
        store2.mark_used(&tx.from, 0);

        // Replay should fail
        assert!(tx.verify_nonce(&store2).is_err());
    }

    #[test]
    fn test_transaction_complete_verification() {
        let keypair = KeyPair::generate();
        let mut tx = Transaction::new(
            keypair.public_key_base58(),
            "recipient".to_string(),
            1000,
            100,
            0,
        );
        tx.sign(&keypair).unwrap();

        let nonce_store = NonceStore::new();

        // Complete verification should succeed
        assert!(tx.verify_complete(&keypair, &nonce_store).unwrap());

        // Mark nonce as used
        let mut store2 = NonceStore::new();
        store2.mark_used(&tx.from, 0);

        // Complete verification should fail (replay)
        assert!(tx.verify_complete(&keypair, &store2).is_err());
    }

    #[test]
    fn test_replay_protection_different_nonces() {
        let keypair = KeyPair::generate();
        let address = keypair.public_key_base58();

        let mut tx1 = Transaction::new(
            address.clone(),
            "recipient".to_string(),
            1000,
            100,
            0,
        );
        tx1.sign(&keypair).unwrap();

        let mut tx2 = Transaction::new(
            address.clone(),
            "recipient".to_string(),
            2000,
            100,
            1,
        );
        tx2.sign(&keypair).unwrap();

        let mut nonce_store = NonceStore::new();

        // First transaction should succeed
        assert!(tx1.verify_complete(&keypair, &nonce_store).unwrap());
        // Mark nonce as used after successful verification
        nonce_store.mark_used(&address, 0);

        // Second transaction with different nonce should also succeed
        assert!(tx2.verify_complete(&keypair, &nonce_store).unwrap());
        // Mark nonce as used
        nonce_store.mark_used(&address, 1);

        // First transaction replay should fail
        assert!(tx1.verify_complete(&keypair, &nonce_store).is_err());
    }

    #[test]
    fn test_replay_protection_different_addresses() {
        let keypair1 = KeyPair::generate();
        let keypair2 = KeyPair::generate();

        let mut tx1 = Transaction::new(
            keypair1.public_key_base58(),
            "recipient".to_string(),
            1000,
            100,
            0,
        );
        tx1.sign(&keypair1).unwrap();

        let mut tx2 = Transaction::new(
            keypair2.public_key_base58(),
            "recipient".to_string(),
            1000,
            100,
            0,
        );
        tx2.sign(&keypair2).unwrap();

        let nonce_store = NonceStore::new();

        // Both transactions with same nonce but different addresses should succeed
        assert!(tx1.verify_complete(&keypair1, &nonce_store).unwrap());
        assert!(tx2.verify_complete(&keypair2, &nonce_store).unwrap());
    }
}
