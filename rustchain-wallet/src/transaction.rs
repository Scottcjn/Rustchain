//! Transaction handling for RustChain Wallet
//!
//! This module provides transaction creation, signing, and serialization.

use crate::error::{Result, WalletError};
use crate::keys::KeyPair;
use crate::nonce_store::NonceStore;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

/// Smallest-unit-to-RTC conversion factor (6 decimals).
const AMOUNT_UNIT: u64 = 1_000_000;

/// Format an f64 amount to match Python's json.dumps float representation.
/// Python serializes 1.0 as "1.0", 1000000.0 as "1000000.0", etc.
fn py_json_number(n: f64) -> String {
    if n.trunc() == n {
        format!("{n:.1}")
    } else {
        format!("{n}")
    }
}

/// Build the canonical signed message JSON, matching the Python server format:
/// `json.dumps(tx_data, sort_keys=True, separators=(",", ":"))`
///
/// Sorted key order: amount, chain_id (optional), from, memo, nonce, to
fn canonical_message(
    from: &str,
    to: &str,
    amount_rtc: f64,
    memo: &str,
    nonce_str: &str,
    chain_id: Option<&str>,
) -> Vec<u8> {
    let mut s = String::with_capacity(256);
    s.push('{');
    s.push_str("\"amount\":");
    s.push_str(&py_json_number(amount_rtc));
    if let Some(cid) = chain_id {
        s.push_str(",\"chain_id\":");
        s.push_str(&serde_json::to_string(cid).unwrap_or(cid.to_string()));
    }
    s.push_str(",\"from\":");
    s.push_str(&serde_json::to_string(from).unwrap_or(from.to_string()));
    s.push_str(",\"memo\":");
    s.push_str(&serde_json::to_string(memo).unwrap_or(memo.to_string()));
    s.push_str(",\"nonce\":");
    s.push_str(&serde_json::to_string(nonce_str).unwrap_or(nonce_str.to_string()));
    s.push_str(",\"to\":");
    s.push_str(&serde_json::to_string(to).unwrap_or(to.to_string()));
    s.push('}');
    s.into_bytes()
}

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
    /// Public key (hex encoded) for verification
    pub public_key: Option<String>,
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
            public_key: None,
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

    /// Serialize the transaction for signing using the canonical format
    /// that matches the Python server's verification format.
    ///
    /// The server reconstructs the signed message as:
    /// `json.dumps({"from":...,"to":...,"amount":...,"memo":...,"nonce":str(nonce)},
    ///              sort_keys=True, separators=(",",":"))`
    ///
    /// Note: `amount` is converted from smallest units to RTC units (÷1_000_000),
    /// and `nonce` is serialized as a JSON string (not a number).
    pub fn serialize_for_signing(&self) -> Result<Vec<u8>> {
        let amount_rtc = self.amount as f64 / AMOUNT_UNIT as f64;
        let nonce_str = self.nonce.to_string();
        let memo = self.memo.as_deref().unwrap_or("");
        Ok(canonical_message(
            &self.from, &self.to, amount_rtc, memo, &nonce_str, None,
        ))
    }

    /// Serialize the transaction for signing with an optional chain_id.
    /// Use this when the server requires chain_id in the signed message.
    pub fn serialize_for_signing_with_chain_id(&self, chain_id: &str) -> Result<Vec<u8>> {
        let amount_rtc = self.amount as f64 / AMOUNT_UNIT as f64;
        let nonce_str = self.nonce.to_string();
        let memo = self.memo.as_deref().unwrap_or("");
        Ok(canonical_message(
            &self.from,
            &self.to,
            amount_rtc,
            memo,
            &nonce_str,
            Some(chain_id),
        ))
    }

    /// Sign the transaction with a keypair
    pub fn sign(&mut self, keypair: &KeyPair) -> Result<()> {
        let message = self.serialize_for_signing()?;
        let signature = keypair.sign(&message)?;
        self.signature = Some(hex::encode(&signature));
        self.public_key = Some(keypair.public_key_hex());
        Ok(())
    }

    /// Verify the transaction signature
    pub fn verify(&self, keypair: &KeyPair) -> Result<bool> {
        let signature = self
            .signature
            .as_ref()
            .ok_or_else(|| WalletError::Transaction("Transaction not signed".to_string()))?;

        let sig_bytes = hex::decode(signature)?;
        let message = self.serialize_for_signing()?;

        keypair.verify(&message, &sig_bytes)
    }

    /// Verify the transaction signature against a public key
    pub fn verify_with_pubkey(&self, public_key: &KeyPair) -> Result<bool> {
        let signature = self
            .signature
            .as_ref()
            .ok_or_else(|| WalletError::Transaction("Transaction not signed".to_string()))?;

        let sig_bytes = hex::decode(signature)?;
        let message = self.serialize_for_signing()?;

        public_key.verify(&message, &sig_bytes)
    }

    /// Get the transaction hash (for display/reference purposes)
    pub fn hash(&self) -> Result<String> {
        use sha2::{Digest, Sha256};

        let message = self.serialize_for_signing()?;
        let hash = Sha256::digest(&message);
        Ok(hex::encode(hash))
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
        let from = self
            .from
            .ok_or_else(|| WalletError::Transaction("Sender address not set".to_string()))?;

        let to = self
            .to
            .ok_or_else(|| WalletError::Transaction("Recipient address not set".to_string()))?;

        if self.amount == 0 {
            return Err(WalletError::Transaction(
                "Amount must be greater than 0".to_string(),
            ));
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
        let tx = Transaction::new("from".to_string(), "to".to_string(), 1000, 100, 1)
            .with_memo("Test memo".to_string());

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
        )
        .with_memo("Test".to_string());

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
    fn test_transaction_builder_rejects_invalid_inputs() {
        let err = TransactionBuilder::new()
            .to("recipient".to_string())
            .amount(1000)
            .build()
            .unwrap_err();
        assert!(matches!(
            err,
            WalletError::Transaction(ref message) if message == "Sender address not set"
        ));

        let err = TransactionBuilder::new()
            .from("sender".to_string())
            .amount(1000)
            .build()
            .unwrap_err();
        assert!(matches!(
            err,
            WalletError::Transaction(ref message) if message == "Recipient address not set"
        ));

        let err = TransactionBuilder::new()
            .from("sender".to_string())
            .to("recipient".to_string())
            .build()
            .unwrap_err();
        assert!(matches!(
            err,
            WalletError::Transaction(ref message) if message == "Amount must be greater than 0"
        ));
    }

    #[test]
    fn test_transaction_hash() {
        let tx = Transaction::new("from".to_string(), "to".to_string(), 1000, 100, 1);

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

        let mut tx1 = Transaction::new(address.clone(), "recipient".to_string(), 1000, 100, 0);
        tx1.sign(&keypair).unwrap();

        let mut tx2 = Transaction::new(address.clone(), "recipient".to_string(), 2000, 100, 1);
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

    #[test]
    fn test_transaction_verify_with_pubkey() {
        let signer = KeyPair::generate();
        let verifier = KeyPair::generate();

        let mut tx = Transaction::new(
            signer.public_key_base58(),
            "recipient".to_string(),
            1000,
            100,
            1,
        );

        // Sign with signer
        tx.sign(&signer).unwrap();
        assert!(tx.signature.is_some());

        // Verify with signer's public key should succeed
        let valid = tx.verify_with_pubkey(&signer).unwrap();
        assert!(valid);

        // Verify with different key should fail
        let valid = tx.verify_with_pubkey(&verifier).unwrap();
        assert!(!valid);
    }

    #[test]
    fn test_transaction_verify_with_pubkey_unsigned() {
        let keypair = KeyPair::generate();
        let tx = Transaction::new(
            keypair.public_key_base58(),
            "recipient".to_string(),
            1000,
            100,
            1,
        );

        // Verify unsigned transaction should fail
        let result = tx.verify_with_pubkey(&keypair);
        assert!(result.is_err());
    }

    // ==================== Canonical Message Format Compatibility Tests ====================
    // These tests verify that the Rust wallet produces the exact same signed message
    // format that the Python server expects for /wallet/transfer/signed verification.

    #[test]
    fn test_canonical_message_format_matches_python_server() {
        // Python server format:
        // json.dumps({"from":"RTC...","to":"RTC...","amount":1.0,"memo":"","nonce":"1733420000000"},
        //            sort_keys=True, separators=(",",":"))
        // = {"amount":1.0,"from":"RTCabc...","memo":"","nonce":"1733420000000","to":"RTCdef..."}

        let msg = canonical_message("RTCabc123", "RTCdef456", 1.0, "", "1733420000000", None);
        let json_str = String::from_utf8(msg).unwrap();
        assert_eq!(
            json_str,
            r#"{"amount":1.0,"from":"RTCabc123","memo":"","nonce":"1733420000000","to":"RTCdef456"}"#
        );
    }

    #[test]
    fn test_canonical_message_with_memo() {
        let msg = canonical_message("RTCabc", "RTCdef", 0.5, "hello world", "42", None);
        let json_str = String::from_utf8(msg).unwrap();
        assert_eq!(
            json_str,
            r#"{"amount":0.5,"from":"RTCabc","memo":"hello world","nonce":"42","to":"RTCdef"}"#
        );
    }

    #[test]
    fn test_canonical_message_with_chain_id() {
        let msg = canonical_message(
            "RTCabc",
            "RTCdef",
            100.0,
            "",
            "1",
            Some("rustchain-mainnet"),
        );
        let json_str = String::from_utf8(msg).unwrap();
        assert_eq!(
            json_str,
            r#"{"amount":100.0,"chain_id":"rustchain-mainnet","from":"RTCabc","memo":"","nonce":"1","to":"RTCdef"}"#
        );
    }

    #[test]
    fn test_canonical_message_nonce_is_string_not_number() {
        // Critical: nonce must be a JSON string, not a number
        let msg = canonical_message("RTCabc", "RTCdef", 1.0, "", "12345", None);
        let json_str = String::from_utf8(msg).unwrap();
        // Verify nonce appears as "12345" (quoted) not 12345 (unquoted)
        assert!(json_str.contains(r#""nonce":"12345""#));
        assert!(!json_str.contains(r#""nonce":12345"#));
    }

    #[test]
    fn test_canonical_message_amount_integer_renders_as_float() {
        // Python renders 1.0 as "1.0", not "1"
        let msg = canonical_message("RTCabc", "RTCdef", 1.0, "", "1", None);
        let json_str = String::from_utf8(msg).unwrap();
        assert!(json_str.contains(r#""amount":1.0"#));
        assert!(!json_str.contains(r#""amount":1,"#));
    }

    #[test]
    fn test_serialize_for_signing_produces_canonical_format() {
        let keypair = KeyPair::generate();
        let mut tx = Transaction::new(
            keypair.public_key_base58(),
            "RTCrecipient12345678901234567890123456".to_string(),
            5_000_000, // 5.0 RTC in smallest units
            1000,
            1733420000000u64,
        )
        .with_memo("test".to_string());
        tx.sign(&keypair).unwrap();

        let message = tx.serialize_for_signing().unwrap();
        let json_str = String::from_utf8(message).unwrap();

        // Verify sorted key order: amount, from, memo, nonce, to
        let amount_pos = json_str.find(r#""amount":"#).unwrap();
        let from_pos = json_str.find(r#""from":"#).unwrap();
        let memo_pos = json_str.find(r#""memo":"#).unwrap();
        let nonce_pos = json_str.find(r#""nonce":"#).unwrap();
        let to_pos = json_str.find(r#""to":"#).unwrap();

        assert!(amount_pos < from_pos);
        assert!(from_pos < memo_pos);
        assert!(memo_pos < nonce_pos);
        assert!(nonce_pos < to_pos);

        // Verify nonce is a string
        assert!(json_str.contains(r#""nonce":"1733420000000""#));

        // Verify amount is 5.0 (5_000_000 / 1_000_000)
        assert!(json_str.contains(r#""amount":5.0"#));
    }

    #[test]
    fn test_sign_and_verify_roundtrip_with_canonical_format() {
        let keypair = KeyPair::generate();
        let mut tx = Transaction::new(
            keypair.rtc_address(),
            "RTCrecipient12345678901234567890123456".to_string(),
            1_000_000, // 1.0 RTC
            1000,
            999,
        );
        tx.sign(&keypair).unwrap();

        // Verify using the same canonical format
        let valid = tx.verify(&keypair).unwrap();
        assert!(valid);

        // Tampered amount should fail verification
        let mut tx2 = tx.clone();
        tx2.amount = 2_000_000; // Changed from 1.0 to 2.0 RTC
        let valid = tx2.verify(&keypair).unwrap();
        assert!(!valid);
    }
}
