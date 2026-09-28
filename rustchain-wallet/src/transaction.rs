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

/// Format an f64 amount exactly like Python's `repr(float)` / `json.dumps`.
///
/// Rust and Python agree on the shortest round-trip digits but not on layout:
/// Python prints `1.0` (Rust `1`) and switches to exponent form when the decimal
/// exponent is < -4 or >= 16 (`1e-05`, `1e+16`), where Rust's `{}` never does.
/// Any difference changes the signed bytes and the node rejects the signature.
fn py_json_number(n: f64) -> String {
    if n == 0.0 {
        return if n.is_sign_negative() { "-0.0" } else { "0.0" }.to_string();
    }
    // `{:e}` gives the shortest round-trip digits, e.g. "1.5e-5", "1e16".
    let sci = format!("{:e}", n.abs());
    let (mantissa, exp) = sci.split_once('e').unwrap_or((sci.as_str(), "0"));
    let exp: i32 = exp.parse().unwrap_or(0);
    let digits: String = mantissa.chars().filter(|c| *c != '.').collect();
    let sign = if n < 0.0 { "-" } else { "" };
    if !(-4..16).contains(&exp) {
        let mant = if digits.len() > 1 {
            format!("{}.{}", &digits[..1], &digits[1..])
        } else {
            digits
        };
        let esign = if exp < 0 { '-' } else { '+' };
        return format!("{sign}{mant}e{esign}{:02}", exp.abs());
    }
    if exp < 0 {
        return format!("{sign}0.{}{digits}", "0".repeat((-exp - 1) as usize));
    }
    let int_len = (exp + 1) as usize;
    if digits.len() <= int_len {
        format!("{sign}{digits}{}.0", "0".repeat(int_len - digits.len()))
    } else {
        format!("{sign}{}.{}", &digits[..int_len], &digits[int_len..])
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
    /// Network the signature is bound to (the node's `CHAIN_ID`, from
    /// `/network/info`). Signed into the message so the transfer cannot be
    /// replayed on another RustChain network. `submit_transaction` refuses
    /// transactions without it.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub chain_id: Option<String>,
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
            chain_id: None,
        }
    }

    /// Bind the transaction to a chain id (the node's `CHAIN_ID`).
    ///
    /// Clears any existing signature, since it no longer covers the message.
    pub fn with_chain_id(mut self, chain_id: impl Into<String>) -> Self {
        self.chain_id = Some(chain_id.into());
        self.signature = None;
        self
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
    /// and `nonce` is serialized as a JSON string (not a number). When
    /// `chain_id` is set it is included (sorted between `amount` and `from`).
    pub fn serialize_for_signing(&self) -> Result<Vec<u8>> {
        let amount_rtc = self.amount as f64 / AMOUNT_UNIT as f64;
        let nonce_str = self.nonce.to_string();
        let memo = self.memo.as_deref().unwrap_or("");
        Ok(canonical_message(
            &self.from,
            &self.to,
            amount_rtc,
            memo,
            &nonce_str,
            self.chain_id.as_deref(),
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
    chain_id: Option<String>,
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
            chain_id: None,
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

    /// Bind the transaction to a chain id (the node's `CHAIN_ID`)
    pub fn chain_id(mut self, chain_id: String) -> Self {
        self.chain_id = Some(chain_id);
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
        if let Some(chain_id) = self.chain_id {
            tx = tx.with_chain_id(chain_id);
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

    // Golden vectors shared with tests/test_signed_transfer_clients_chain_id.py,
    // which checks that the node's verifier accepts exactly these bytes and
    // signatures. Seed = [7; 32], nonce 1733420000123, memo "rust golden".
    const GOLDEN_CHAIN_ID: &str = "rustchain-mainnet-v2";
    const GOLDEN_FROM: &str = "RTCfe812c12f3ab4ce6ac5db69ac352f906cb1b11ef";
    const GOLDEN_TO: &str = "RTCbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";

    fn golden_tx(amount: u64) -> (KeyPair, Transaction) {
        let keypair = KeyPair::from_bytes(&[7u8; 32]).unwrap();
        assert_eq!(keypair.rtc_address(), GOLDEN_FROM);
        let tx = TransactionBuilder::new()
            .from(keypair.rtc_address())
            .to(GOLDEN_TO.to_string())
            .amount(amount)
            .nonce(1_733_420_000_123)
            .memo("rust golden".to_string())
            .chain_id(GOLDEN_CHAIN_ID.to_string())
            .build()
            .unwrap();
        (keypair, tx)
    }

    #[test]
    fn test_chain_bound_signature_matches_node_golden_vector() {
        let (keypair, mut tx) = golden_tx(1_500_000);
        let msg = String::from_utf8(tx.serialize_for_signing().unwrap()).unwrap();
        assert_eq!(
            msg,
            r#"{"amount":1.5,"chain_id":"rustchain-mainnet-v2","from":"RTCfe812c12f3ab4ce6ac5db69ac352f906cb1b11ef","memo":"rust golden","nonce":"1733420000123","to":"RTCbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}"#
        );
        tx.sign(&keypair).unwrap();
        assert_eq!(
            tx.signature.as_deref().unwrap(),
            "f7df488d1ffe61d28b35437b62771c2425d47d1ef1b3169292f731e69b639bf8c63f6b2cdc85a80114d60d50eac9421a04f7970ea593d0e5cc063d5e6565190d"
        );
    }

    #[test]
    fn test_small_amount_uses_python_exponent_form() {
        // 50 uRTC = 5e-05 RTC. Python's json.dumps writes "5e-05"; Rust's `{}`
        // writes "0.00005", which the node would reject as a bad signature.
        let (keypair, mut tx) = golden_tx(50);
        let msg = String::from_utf8(tx.serialize_for_signing().unwrap()).unwrap();
        assert!(msg.starts_with(r#"{"amount":5e-05,"chain_id":"#), "{msg}");
        tx.sign(&keypair).unwrap();
        assert_eq!(
            tx.signature.as_deref().unwrap(),
            "d3f37e63d4be98115c6ed8268c0edb4dfa2f241204a489110d289b384beaf1fa9f4e1ffb7fe66b299b7b8dda0bf1b78c75e78ca00ecba6c69eb83739e23f520a"
        );
    }

    #[test]
    fn test_py_json_number_matches_python_repr() {
        let cases: &[(f64, &str)] = &[
            (1.0, "1.0"),
            (1.5, "1.5"),
            (0.1, "0.1"),
            (0.000249, "0.000249"),
            (0.0001, "0.0001"),
            (0.00005, "5e-05"),
            (0.000001, "1e-06"),
            (0.0000015, "1.5e-06"),
            (123456.789, "123456.789"),
            (1_000_000.0, "1000000.0"),
            (1e15, "1000000000000000.0"),
            (1e16, "1e+16"),
            (8_388_608.0, "8388608.0"),
            (0.0, "0.0"),
        ];
        for (n, want) in cases {
            assert_eq!(py_json_number(*n), *want, "py_json_number({n})");
        }
    }

    #[test]
    fn test_with_chain_id_invalidates_existing_signature() {
        let keypair = KeyPair::generate();
        let mut tx = Transaction::new(keypair.rtc_address(), GOLDEN_TO.to_string(), 1, 0, 1);
        tx.sign(&keypair).unwrap();
        let tx = tx.with_chain_id(GOLDEN_CHAIN_ID);
        assert!(tx.signature.is_none());
        assert_eq!(tx.chain_id.as_deref(), Some(GOLDEN_CHAIN_ID));
    }

    #[test]
    fn test_chain_id_roundtrips_and_old_json_still_loads() {
        let (_, tx) = golden_tx(1_500_000);
        let back = Transaction::from_json(&tx.to_json().unwrap()).unwrap();
        assert_eq!(back.chain_id.as_deref(), Some(GOLDEN_CHAIN_ID));

        let mut legacy: serde_json::Value = serde_json::from_str(&tx.to_json().unwrap()).unwrap();
        legacy.as_object_mut().unwrap().remove("chain_id");
        let old = Transaction::from_json(&legacy.to_string()).unwrap();
        assert!(old.chain_id.is_none());
    }
}
