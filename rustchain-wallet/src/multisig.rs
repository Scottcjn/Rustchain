// SPDX-License-Identifier: MIT OR Apache-2.0

//! Multi-signature wallet support for RustChain Wallet.
//!
//! This module provides an offline M-of-N multisig transaction flow:
//! create a validated signer set, derive a deterministic multisig address,
//! collect Ed25519 signatures from configured signers, and verify that the
//! collected signatures meet the configured threshold before submission.

use crate::error::{Result, WalletError};
use crate::keys::KeyPair;
use crate::transaction::Transaction;
use ed25519_dalek::{Signature, Verifier, VerifyingKey};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};

const MULTISIG_DOMAIN: &str = "rustchain-multisig-v1";

/// A configured multisig signer.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct MultiSigSigner {
    /// Signer's RTC address.
    pub address: String,
    /// Signer's Ed25519 public key as hex.
    pub public_key: String,
}

impl MultiSigSigner {
    /// Create a signer entry from a wallet keypair.
    pub fn from_keypair(keypair: &KeyPair) -> Self {
        Self {
            address: keypair.rtc_address(),
            public_key: keypair.public_key_hex(),
        }
    }

    fn verifying_key(&self) -> Result<VerifyingKey> {
        let bytes = hex::decode(&self.public_key)?;
        let key_bytes: [u8; 32] = bytes
            .try_into()
            .map_err(|_| WalletError::InvalidKey("Public key must be 32 bytes".to_string()))?;
        VerifyingKey::from_bytes(&key_bytes).map_err(WalletError::from)
    }
}

/// M-of-N multisig wallet configuration.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct MultiSigConfig {
    /// Minimum number of valid signer signatures required.
    pub threshold: usize,
    /// Authorized signers.
    pub signers: Vec<MultiSigSigner>,
}

impl MultiSigConfig {
    /// Create a validated multisig configuration.
    pub fn new(threshold: usize, signers: Vec<MultiSigSigner>) -> Result<Self> {
        if threshold == 0 {
            return Err(WalletError::Transaction(
                "Multisig threshold must be greater than 0".to_string(),
            ));
        }
        if signers.is_empty() {
            return Err(WalletError::Transaction(
                "Multisig requires at least one signer".to_string(),
            ));
        }
        if threshold > signers.len() {
            return Err(WalletError::Transaction(
                "Multisig threshold cannot exceed signer count".to_string(),
            ));
        }

        let mut addresses = BTreeSet::new();
        let mut public_keys = BTreeSet::new();
        for signer in &signers {
            let verifying_key = signer.verifying_key()?;
            let expected_address = rtc_address_from_public_key(verifying_key.as_bytes());
            if signer.address != expected_address {
                return Err(WalletError::InvalidAddress(format!(
                    "Signer address {} does not match public key",
                    signer.address
                )));
            }
            if !addresses.insert(signer.address.clone()) {
                return Err(WalletError::Transaction(
                    "Duplicate multisig signer address".to_string(),
                ));
            }
            if !public_keys.insert(signer.public_key.clone()) {
                return Err(WalletError::Transaction(
                    "Duplicate multisig signer public key".to_string(),
                ));
            }
        }

        Ok(Self { threshold, signers })
    }

    /// Derive a deterministic RTC address for this multisig configuration.
    pub fn address(&self) -> String {
        let mut signer_addresses: Vec<&str> = self
            .signers
            .iter()
            .map(|signer| signer.address.as_str())
            .collect();
        signer_addresses.sort_unstable();

        let mut hasher = Sha256::new();
        hasher.update(MULTISIG_DOMAIN.as_bytes());
        hasher.update(b"|");
        hasher.update(self.threshold.to_string().as_bytes());
        for address in signer_addresses {
            hasher.update(b"|");
            hasher.update(address.as_bytes());
        }

        let digest = hasher.finalize();
        format!("RTC{}", &hex::encode(digest)[..40])
    }

    /// Return true if the address belongs to one of the configured signers.
    pub fn contains_signer(&self, address: &str) -> bool {
        self.signers.iter().any(|signer| signer.address == address)
    }

    fn signer(&self, address: &str) -> Option<&MultiSigSigner> {
        self.signers.iter().find(|signer| signer.address == address)
    }
}

/// A multisig transaction proposal with collected signer signatures.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MultiSigProposal {
    /// Multisig wallet configuration.
    pub config: MultiSigConfig,
    /// Transaction to authorize.
    pub transaction: Transaction,
    /// Hex signatures keyed by signer RTC address.
    pub signatures: BTreeMap<String, String>,
}

impl MultiSigProposal {
    /// Create a proposal for a transaction sent from the multisig address.
    pub fn new(config: MultiSigConfig, transaction: Transaction) -> Result<Self> {
        let multisig_address = config.address();
        if transaction.from != multisig_address {
            return Err(WalletError::Transaction(format!(
                "Transaction sender must match multisig address {}",
                multisig_address
            )));
        }

        Ok(Self {
            config,
            transaction,
            signatures: BTreeMap::new(),
        })
    }

    /// Sign the proposal with one configured signer.
    pub fn sign(&mut self, keypair: &KeyPair) -> Result<()> {
        let signer_address = keypair.rtc_address();
        if !self.config.contains_signer(&signer_address) {
            return Err(WalletError::Transaction(
                "Keypair is not a configured multisig signer".to_string(),
            ));
        }
        if self.signatures.contains_key(&signer_address) {
            return Err(WalletError::Transaction(
                "Signer has already signed this proposal".to_string(),
            ));
        }

        let message = self.transaction.serialize_for_signing()?;
        let signature = keypair.sign(&message)?;
        self.signatures
            .insert(signer_address, hex::encode(signature));
        Ok(())
    }

    /// Number of collected signatures.
    pub fn signature_count(&self) -> usize {
        self.signatures.len()
    }

    /// Return true when the proposal has enough valid configured signatures.
    pub fn is_ready(&self) -> Result<bool> {
        Ok(self.valid_signature_count()? >= self.config.threshold)
    }

    /// Count valid signatures from configured signers.
    pub fn valid_signature_count(&self) -> Result<usize> {
        let message = self.transaction.serialize_for_signing()?;
        let mut valid = 0;

        for (address, signature_hex) in &self.signatures {
            let Some(signer) = self.config.signer(address) else {
                continue;
            };

            let signature_bytes = hex::decode(signature_hex)?;
            let signature = Signature::from_slice(&signature_bytes)
                .map_err(|e| WalletError::InvalidSignature(e.to_string()))?;
            if signer.verifying_key()?.verify(&message, &signature).is_ok() {
                valid += 1;
            }
        }

        Ok(valid)
    }

    /// Verify that the proposal meets its threshold.
    pub fn verify_threshold(&self) -> Result<()> {
        if self.is_ready()? {
            Ok(())
        } else {
            Err(WalletError::Transaction(format!(
                "Multisig proposal has {}/{} valid signatures",
                self.valid_signature_count()?,
                self.config.threshold
            )))
        }
    }

    /// Serialize the proposal to pretty JSON for transport between signers.
    pub fn to_json(&self) -> Result<String> {
        Ok(serde_json::to_string_pretty(self)?)
    }

    /// Deserialize a proposal from JSON.
    pub fn from_json(json: &str) -> Result<Self> {
        Ok(serde_json::from_str(json)?)
    }
}

fn rtc_address_from_public_key(public_key: &[u8; 32]) -> String {
    let hash = Sha256::digest(public_key);
    format!("RTC{}", &hex::encode(hash)[..40])
}

#[cfg(test)]
mod tests {
    use super::*;

    fn config_and_keys(threshold: usize) -> (MultiSigConfig, [KeyPair; 3]) {
        let keys = [
            KeyPair::generate(),
            KeyPair::generate(),
            KeyPair::generate(),
        ];
        let signers = keys.iter().map(MultiSigSigner::from_keypair).collect();
        (MultiSigConfig::new(threshold, signers).unwrap(), keys)
    }

    #[test]
    fn test_multisig_config_validates_threshold() {
        let signer = MultiSigSigner::from_keypair(&KeyPair::generate());

        assert!(MultiSigConfig::new(0, vec![signer.clone()]).is_err());
        assert!(MultiSigConfig::new(2, vec![signer]).is_err());
    }

    #[test]
    fn test_multisig_config_rejects_duplicate_signers() {
        let signer = MultiSigSigner::from_keypair(&KeyPair::generate());
        let err = MultiSigConfig::new(1, vec![signer.clone(), signer]).unwrap_err();

        assert!(matches!(
            err,
            WalletError::Transaction(ref message)
                if message == "Duplicate multisig signer address"
        ));
    }

    #[test]
    fn test_multisig_config_rejects_mismatched_address() {
        let signer_a = MultiSigSigner::from_keypair(&KeyPair::generate());
        let mut signer_b = MultiSigSigner::from_keypair(&KeyPair::generate());
        signer_b.address = signer_a.address;

        let err = MultiSigConfig::new(1, vec![signer_b]).unwrap_err();
        assert!(matches!(err, WalletError::InvalidAddress(_)));
    }

    #[test]
    fn test_multisig_address_is_deterministic_by_signer_set() {
        let keys = [
            KeyPair::generate(),
            KeyPair::generate(),
            KeyPair::generate(),
        ];
        let mut signers: Vec<_> = keys.iter().map(MultiSigSigner::from_keypair).collect();
        let config_a = MultiSigConfig::new(2, signers.clone()).unwrap();
        signers.reverse();
        let config_b = MultiSigConfig::new(2, signers).unwrap();

        assert_eq!(config_a.address(), config_b.address());
        assert!(config_a.address().starts_with("RTC"));
        assert_eq!(config_a.address().len(), 43);
    }

    #[test]
    fn test_multisig_proposal_requires_multisig_sender() {
        let (config, _) = config_and_keys(2);
        let tx = Transaction::new("wrong".to_string(), "recipient".to_string(), 1000, 100, 1);

        assert!(MultiSigProposal::new(config, tx).is_err());
    }

    #[test]
    fn test_multisig_proposal_reaches_threshold() {
        let (config, keys) = config_and_keys(2);
        let tx = Transaction::new(config.address(), "recipient".to_string(), 1000, 100, 1)
            .with_memo("2 of 3 approval".to_string());
        let mut proposal = MultiSigProposal::new(config, tx).unwrap();

        proposal.sign(&keys[0]).unwrap();
        assert_eq!(proposal.valid_signature_count().unwrap(), 1);
        assert!(!proposal.is_ready().unwrap());

        proposal.sign(&keys[1]).unwrap();
        assert_eq!(proposal.signature_count(), 2);
        assert!(proposal.is_ready().unwrap());
        proposal.verify_threshold().unwrap();
    }

    #[test]
    fn test_multisig_proposal_rejects_unconfigured_and_duplicate_signer() {
        let (config, keys) = config_and_keys(2);
        let tx = Transaction::new(config.address(), "recipient".to_string(), 1000, 100, 1);
        let mut proposal = MultiSigProposal::new(config, tx).unwrap();

        proposal.sign(&keys[0]).unwrap();
        assert!(proposal.sign(&keys[0]).is_err());
        assert!(proposal.sign(&KeyPair::generate()).is_err());
    }

    #[test]
    fn test_multisig_proposal_detects_tampered_signature() {
        let (config, keys) = config_and_keys(2);
        let tx = Transaction::new(config.address(), "recipient".to_string(), 1000, 100, 1);
        let mut proposal = MultiSigProposal::new(config, tx).unwrap();

        proposal.sign(&keys[0]).unwrap();
        proposal.sign(&keys[1]).unwrap();
        let first_signer = keys[0].rtc_address();
        proposal
            .signatures
            .insert(first_signer, hex::encode([0u8; 64]));

        assert_eq!(proposal.valid_signature_count().unwrap(), 1);
        assert!(proposal.verify_threshold().is_err());
    }

    #[test]
    fn test_multisig_proposal_json_round_trip() {
        let (config, keys) = config_and_keys(2);
        let tx = Transaction::new(config.address(), "recipient".to_string(), 1000, 100, 1);
        let mut proposal = MultiSigProposal::new(config, tx).unwrap();
        proposal.sign(&keys[0]).unwrap();

        let json = proposal.to_json().unwrap();
        let loaded = MultiSigProposal::from_json(&json).unwrap();

        assert_eq!(loaded.signature_count(), 1);
        assert_eq!(
            loaded.valid_signature_count().unwrap(),
            proposal.valid_signature_count().unwrap()
        );
    }
}
