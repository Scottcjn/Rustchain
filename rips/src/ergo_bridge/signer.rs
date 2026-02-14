use ergo_lib::chain::transaction::unsigned::UnsignedTransaction;
use ergo_lib::chain::transaction::Transaction;
use ergo_lib::ergotree_ir::chain::address::Address;
use ergo_lib::ergotree_ir::chain::address::NetworkPrefix;
use ergo_lib::wallet::signing::TransactionContext;
use ergo_lib::wallet::Wallet;
use ergo_lib::wallet::secret_key::SecretKey;
use anyhow::{Result, Context};
use async_trait::async_trait;
use std::fs;
use std::path::Path;

/// SECURITY: Signer Trait to abstract away key management.
#[async_trait]
pub trait BridgeSigner: Send + Sync {
    /// Signs an unsigned transaction using the underlying KMS or local key.
    async fn sign_tx(&self, unsigned_tx: UnsignedTransaction, context: TransactionContext) -> Result<Transaction>;
    
    /// Returns the public address associated with this signer.
    fn get_address(&self) -> Address;
}

/// SECURITY: File-based signer for Testnet deployments.
/// Reads a secret key from a secure local file.
pub struct FileKeySigner {
    wallet: Wallet,
    address: Address,
}

impl FileKeySigner {
    pub fn load_from_file<P: AsRef<Path>>(path: P, network: NetworkPrefix) -> Result<Self> {
        let key_hex = fs::read_to_string(path).context("Failed to read key file")?;
        let secret_bytes = hex::decode(key_hex.trim()).context("Failed to decode hex key")?;
        let secret_key = SecretKey::from_bytes(&secret_bytes).map_err(|_| anyhow::anyhow!("Invalid secret key bytes"))?;
        
        let wallet = Wallet::from_secrets(vec![secret_key.clone()]);
        let address = secret_key.get_address_from_public_key();
        
        Ok(Self { wallet, address })
    }

    pub fn new_from_secret(secret_key: SecretKey) -> Self {
        let address = secret_key.get_address_from_public_key();
        let wallet = Wallet::from_secrets(vec![secret_key]);
        Self { wallet, address }
    }
}

#[async_trait]
impl BridgeSigner for FileKeySigner {
    async fn sign_tx(&self, unsigned_tx: UnsignedTransaction, context: TransactionContext) -> Result<Transaction> {
        self.wallet.sign_transaction(context).context("Failed to sign transaction")
    }

    fn get_address(&self) -> Address {
        self.address.clone()
    }
}

/// SECURITY: Mock KMS implementation for testing and secure deployments.
/// Ensures no raw Private Keys are handled in the application logic.
pub struct MockKmsSigner {
    address: Address,
}

impl MockKmsSigner {
    pub fn new(address: Address) -> Self {
        Self { address }
    }
}

#[async_trait]
impl BridgeSigner for MockKmsSigner {
    async fn sign_tx(&self, _unsigned_tx: UnsignedTransaction, _context: TransactionContext) -> Result<Transaction> {
        Err(anyhow::anyhow!("MockKmsSigner: Signing not implemented for mock"))
    }

    fn get_address(&self) -> Address {
        self.address.clone()
    }
}
