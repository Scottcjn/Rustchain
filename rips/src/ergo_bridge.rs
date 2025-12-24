//! RustChain-Ergo Bridge Layer
//!
//! Provides compatibility with Ergo blockchain concepts:
//! - UTXO-based transaction model
//! - Sigma protocol primitives
//! - ErgoScript contract integration
//! - Cross-chain asset mapping
//!
//! This bridge allows RustChain to leverage Ergo's proven cryptographic
//! foundations while implementing our unique Proof of Antiquity consensus.

use crate::core_types::{WalletAddress, TokenAmount, Block, BlockHash, Transaction};
use crate::proof_of_antiquity::ValidatedProof;
use serde::{Deserialize, Serialize};
use sha2::{Sha256, Digest};
use std::collections::HashMap;

// =============================================================================
// UTXO Model (Ergo-Compatible)
// =============================================================================

/// Unique identifier for a box (UTXO)
pub type BoxId = [u8; 32];

/// Ergo-compatible UTXO box
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Box {
    /// Unique box identifier
    pub box_id: BoxId,
    /// Value in nanoERG (or nanoRTC in our case)
    pub value: u64,
    /// ErgoTree (proposition bytes) - spending condition
    pub ergo_tree: Vec<u8>,
    /// Creation height
    pub creation_height: u64,
    /// Additional tokens (NFTs, badges, etc.)
    pub tokens: Vec<Token>,
    /// Additional registers R4-R9
    pub additional_registers: HashMap<String, RegisterValue>,
    /// Transaction ID that created this box
    pub transaction_id: [u8; 32],
    /// Index in the transaction outputs
    pub index: u16,
}

impl Box {
    /// Create a new UTXO box
    pub fn new(
        value: u64,
        ergo_tree: Vec<u8>,
        creation_height: u64,
        tokens: Vec<Token>,
    ) -> Self {
        let mut box_data = Self {
            box_id: [0u8; 32],
            value,
            ergo_tree,
            creation_height,
            tokens,
            additional_registers: HashMap::new(),
            transaction_id: [0u8; 32],
            index: 0,
        };
        box_data.box_id = box_data.calculate_id();
        box_data
    }

    /// Calculate box ID (hash of contents)
    fn calculate_id(&self) -> BoxId {
        let mut hasher = Sha256::new();
        hasher.update(&self.value.to_le_bytes());
        hasher.update(&self.ergo_tree);
        hasher.update(&self.creation_height.to_le_bytes());
        for token in &self.tokens {
            hasher.update(&token.token_id);
            hasher.update(&token.amount.to_le_bytes());
        }
        hasher.finalize().into()
    }

    /// Convert RustChain wallet address to ErgoTree
    pub fn wallet_to_ergo_tree(wallet: &WalletAddress) -> Vec<u8> {
        // Simplified: create a P2PK-like proposition
        // In real implementation, this would be proper ErgoTree encoding
        let mut tree = vec![0x00, 0x08]; // Header for P2PK
        tree.extend(wallet.address.as_bytes());
        tree
    }
}

/// Token within a box (for NFT badges, etc.)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Token {
    /// Token ID (32 bytes)
    pub token_id: [u8; 32],
    /// Amount of this token
    pub amount: u64,
}

/// Register value types
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum RegisterValue {
    /// Long integer
    Long(i64),
    /// Byte array
    ByteArray(Vec<u8>),
    /// Group element (for sigma protocols)
    GroupElement([u8; 33]),
    /// Collection of values
    Collection(Vec<RegisterValue>),
}

// =============================================================================
// UTXO Set Management
// =============================================================================

/// UTXO set tracking all unspent boxes
pub struct UtxoSet {
    /// Unspent boxes by ID
    boxes: HashMap<BoxId, Box>,
    /// Boxes by wallet address (for quick lookup)
    by_address: HashMap<String, Vec<BoxId>>,
}

impl UtxoSet {
    /// Create empty UTXO set
    pub fn new() -> Self {
        Self {
            boxes: HashMap::new(),
            by_address: HashMap::new(),
        }
    }

    /// Add a box to the UTXO set
    pub fn add_box(&mut self, b: Box, owner_address: &str) {
        let box_id = b.box_id;
        self.boxes.insert(box_id, b);
        self.by_address
            .entry(owner_address.to_string())
            .or_insert_with(Vec::new)
            .push(box_id);
    }

    /// Remove a box (spend it)
    pub fn spend_box(&mut self, box_id: &BoxId) -> Option<Box> {
        if let Some(b) = self.boxes.remove(box_id) {
            // Remove from address index too
            for boxes in self.by_address.values_mut() {
                boxes.retain(|id| id != box_id);
            }
            Some(b)
        } else {
            None
        }
    }

    /// Get box by ID
    pub fn get_box(&self, box_id: &BoxId) -> Option<&Box> {
        self.boxes.get(box_id)
    }

    /// Get all boxes for an address
    pub fn get_boxes_for_address(&self, address: &str) -> Vec<&Box> {
        self.by_address
            .get(address)
            .map(|ids| {
                ids.iter()
                    .filter_map(|id| self.boxes.get(id))
                    .collect()
            })
            .unwrap_or_default()
    }

    /// Get total balance for an address
    pub fn get_balance(&self, address: &str) -> u64 {
        self.get_boxes_for_address(address)
            .iter()
            .map(|b| b.value)
            .sum()
    }
}

impl Default for UtxoSet {
    fn default() -> Self {
        Self::new()
    }
}

// =============================================================================
// Ergo-Compatible Transaction
// =============================================================================

/// Ergo-style transaction with inputs and outputs
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ErgoTransaction {
    /// Transaction ID
    pub id: [u8; 32],
    /// Input boxes being spent
    pub inputs: Vec<TransactionInput>,
    /// Data inputs (read-only)
    pub data_inputs: Vec<BoxId>,
    /// Output boxes being created
    pub outputs: Vec<Box>,
}

/// Transaction input reference
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransactionInput {
    /// Box ID being spent
    pub box_id: BoxId,
    /// Spending proof (signature, etc.)
    pub spending_proof: SpendingProof,
    /// Extension (context variables)
    pub extension: HashMap<String, Vec<u8>>,
}

/// Proof that authorizes spending a box
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum SpendingProof {
    /// Empty proof (for genesis or special cases)
    Empty,
    /// Proof of knowledge of discrete log (signature)
    ProofOfDLog {
        /// Signature bytes
        signature: Vec<u8>,
    },
    /// Threshold signature (m-of-n)
    Threshold {
        /// Required signatures
        signatures: Vec<Vec<u8>>,
    },
    /// Proof of Antiquity specific proof
    AntiquityProof {
        /// Validated PoA proof
        hardware_hash: String,
        /// Antiquity Score
        antiquity_score: f64,
        /// Entropy proof hash
        entropy_hash: String,
    },
}

impl ErgoTransaction {
    /// Create a new transaction
    pub fn new(inputs: Vec<TransactionInput>, outputs: Vec<Box>) -> Self {
        let mut tx = Self {
            id: [0u8; 32],
            inputs,
            data_inputs: Vec::new(),
            outputs,
        };
        tx.id = tx.calculate_id();
        tx
    }

    /// Calculate transaction ID
    fn calculate_id(&self) -> [u8; 32] {
        let mut hasher = Sha256::new();
        for input in &self.inputs {
            hasher.update(&input.box_id);
        }
        for output in &self.outputs {
            hasher.update(&output.box_id);
        }
        hasher.finalize().into()
    }

    /// Create a mining reward transaction (coinbase-like)
    pub fn mining_reward(
        proof: &ValidatedProof,
        reward_amount: u64,
        block_height: u64,
    ) -> Self {
        let output = Box {
            box_id: [0u8; 32],
            value: reward_amount,
            ergo_tree: Box::wallet_to_ergo_tree(&proof.wallet),
            creation_height: block_height,
            tokens: Vec::new(),
            additional_registers: {
                let mut regs = HashMap::new();
                // R4: Antiquity Score
                regs.insert("R4".to_string(), RegisterValue::Long((proof.antiquity_score * 100.0) as i64));
                // R5: Hardware model
                regs.insert("R5".to_string(), RegisterValue::ByteArray(proof.hardware.cpu_model.as_bytes().to_vec()));
                regs
            },
            transaction_id: [0u8; 32],
            index: 0,
        };

        Self::new(
            vec![TransactionInput {
                box_id: [0u8; 32], // Genesis/mining input
                spending_proof: SpendingProof::AntiquityProof {
                    hardware_hash: proof.hardware.generate_hardware_hash(),
                    antiquity_score: proof.antiquity_score,
                    entropy_hash: proof.anti_emulation_hash.clone(),
                },
                extension: HashMap::new(),
            }],
            vec![output],
        )
    }
}

// =============================================================================
// Sigma Protocol Primitives
// =============================================================================

/// Sigma proposition (spending condition)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum SigmaProposition {
    /// Prove knowledge of discrete log
    ProveDLog {
        /// Public key (group element)
        public_key: [u8; 33],
    },
    /// Prove knowledge of Diffie-Hellman tuple
    ProveDHTuple {
        /// Generator g
        g: [u8; 33],
        /// Generator h
        h: [u8; 33],
        /// u = g^x
        u: [u8; 33],
        /// v = h^x
        v: [u8; 33],
    },
    /// AND composition
    And(Vec<SigmaProposition>),
    /// OR composition
    Or(Vec<SigmaProposition>),
    /// Threshold (k-of-n)
    Threshold {
        k: u32,
        children: Vec<SigmaProposition>,
    },
    /// RustChain-specific: Antiquity proof
    ProveAntiquity {
        /// Minimum required Antiquity Score
        min_score: f64,
        /// Allowed hardware tiers
        allowed_tiers: Vec<String>,
    },
}

impl SigmaProposition {
    /// Create a simple P2PK proposition
    pub fn p2pk(public_key: [u8; 33]) -> Self {
        Self::ProveDLog { public_key }
    }

    /// Create 2-of-3 multisig
    pub fn multisig_2of3(keys: [[u8; 33]; 3]) -> Self {
        Self::Threshold {
            k: 2,
            children: keys.into_iter().map(|pk| Self::ProveDLog { public_key: pk }).collect(),
        }
    }

    /// Create an antiquity-gated proposition
    pub fn antiquity_gate(min_score: f64) -> Self {
        Self::ProveAntiquity {
            min_score,
            allowed_tiers: vec![
                "ancient".to_string(),
                "sacred".to_string(),
                "vintage".to_string(),
                "classic".to_string(),
            ],
        }
    }
}

// =============================================================================
// Contract Templates (ErgoScript-Compatible)
// =============================================================================

/// Pre-built contract templates for common RustChain operations
pub mod contracts {
    use super::*;

    /// Mining reward distribution contract
    pub fn mining_reward_contract(miner_pk: [u8; 33], min_antiquity: f64) -> Vec<u8> {
        // Simplified encoding - real implementation would compile ErgoScript
        let mut contract = vec![0x01]; // Version
        contract.extend(&miner_pk);
        contract.extend(&min_antiquity.to_le_bytes());
        contract
    }

    /// Governance voting contract
    pub fn governance_vote_contract(proposal_id: &str, voting_end_height: u64) -> Vec<u8> {
        let mut contract = vec![0x02]; // Version
        contract.extend(proposal_id.as_bytes());
        contract.extend(&voting_end_height.to_le_bytes());
        contract
    }

    /// NFT badge minting contract
    pub fn badge_mint_contract(badge_type: &str, recipient_pk: [u8; 33]) -> Vec<u8> {
        let mut contract = vec![0x03]; // Version
        contract.extend(badge_type.as_bytes());
        contract.extend(&recipient_pk);
        contract
    }

    /// Time-locked release contract (for founder allocations)
    pub fn timelock_contract(recipient_pk: [u8; 33], unlock_height: u64) -> Vec<u8> {
        let mut contract = vec![0x04]; // Version
        contract.extend(&recipient_pk);
        contract.extend(&unlock_height.to_le_bytes());
        contract
    }

    /// Cross-chain bridge contract (RTC <-> ERG)
    pub fn bridge_contract(
        rtc_address: &str,
        erg_address: &str,
        amount: u64,
    ) -> Vec<u8> {
        let mut contract = vec![0x05]; // Version
        contract.extend(rtc_address.as_bytes());
        contract.push(0x00); // Separator
        contract.extend(erg_address.as_bytes());
        contract.extend(&amount.to_le_bytes());
        contract
    }
}

// =============================================================================
// State Context (For Contract Execution)
// =============================================================================

/// Execution context for contract evaluation
pub struct StateContext {
    /// Current block height
    pub height: u64,
    /// Last block headers (for CONTEXT.headers access)
    pub last_headers: Vec<BlockHeader>,
    /// Pre-computed hash of the state
    pub state_digest: [u8; 32],
    /// Self box (the box being spent)
    pub self_box: Option<Box>,
}

/// Simplified block header for context
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BlockHeader {
    /// Block height
    pub height: u64,
    /// Block hash
    pub id: [u8; 32],
    /// Parent block hash
    pub parent_id: [u8; 32],
    /// Timestamp
    pub timestamp: u64,
    /// Total antiquity score in block
    pub total_antiquity_score: f64,
}

impl StateContext {
    /// Create context for a given height
    pub fn at_height(height: u64) -> Self {
        Self {
            height,
            last_headers: Vec::new(),
            state_digest: [0u8; 32],
            self_box: None,
        }
    }

    /// Add headers to context
    pub fn with_headers(mut self, headers: Vec<BlockHeader>) -> Self {
        self.last_headers = headers;
        self
    }

    /// Set the self box
    pub fn with_self_box(mut self, b: Box) -> Self {
        self.self_box = Some(b);
        self
    }
}

// =============================================================================
// Bridge to RustChain Native Types
// =============================================================================

/// Convert between RustChain and Ergo-style types
pub trait ErgoCompatible {
    /// Convert to Ergo-compatible box
    fn to_ergo_box(&self, height: u64) -> Box;
}

impl ErgoCompatible for crate::core_types::BlockMiner {
    fn to_ergo_box(&self, height: u64) -> Box {
        Box {
            box_id: [0u8; 32],
            value: self.reward.to_rtc() as u64 * 1_000_000_000, // nanoRTC
            ergo_tree: Box::wallet_to_ergo_tree(&self.wallet),
            creation_height: height,
            tokens: Vec::new(),
            additional_registers: {
                let mut regs = HashMap::new();
                regs.insert("R4".to_string(), RegisterValue::Long((self.antiquity_score * 100.0) as i64));
                regs.insert("R5".to_string(), RegisterValue::ByteArray(self.hardware.as_bytes().to_vec()));
                regs
            },
            transaction_id: [0u8; 32],
            index: 0,
        }
    }
}

/// Convert RustChain block to Ergo-compatible format
pub fn rustchain_block_to_ergo(block: &Block) -> (BlockHeader, Vec<ErgoTransaction>) {
    let header = BlockHeader {
        height: block.height,
        id: {
            let mut id = [0u8; 32];
            hex::decode_to_slice(&block.hash, &mut id).ok();
            id
        },
        parent_id: {
            let mut id = [0u8; 32];
            hex::decode_to_slice(&block.previous_hash, &mut id).ok();
            id
        },
        timestamp: block.timestamp,
        total_antiquity_score: block.miners.iter().map(|m| m.antiquity_score).sum(),
    };

    let transactions: Vec<ErgoTransaction> = block.miners.iter().map(|miner| {
        let output = miner.to_ergo_box(block.height);
        ErgoTransaction::new(Vec::new(), vec![output])
    }).collect();

    (header, transactions)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_utxo_set() {
        let mut utxo_set = UtxoSet::new();

        let wallet = WalletAddress::new("RTC1TestWallet".to_string());
        let b = Box::new(
            1_000_000_000, // 1 RTC in nanoRTC
            Box::wallet_to_ergo_tree(&wallet),
            100,
            Vec::new(),
        );

        utxo_set.add_box(b.clone(), &wallet.address);

        assert_eq!(utxo_set.get_balance(&wallet.address), 1_000_000_000);

        utxo_set.spend_box(&b.box_id);
        assert_eq!(utxo_set.get_balance(&wallet.address), 0);
    }

    #[test]
    fn test_sigma_propositions() {
        let pk = [0u8; 33];

        let p2pk = SigmaProposition::p2pk(pk);
        assert!(matches!(p2pk, SigmaProposition::ProveDLog { .. }));

        let antiquity = SigmaProposition::antiquity_gate(50.0);
        if let SigmaProposition::ProveAntiquity { min_score, .. } = antiquity {
            assert_eq!(min_score, 50.0);
        } else {
            panic!("Expected ProveAntiquity");
        }
    }

    #[test]
    fn test_contracts() {
        let pk = [0u8; 33];

        let reward = contracts::mining_reward_contract(pk, 25.0);
        assert_eq!(reward[0], 0x01);

        let vote = contracts::governance_vote_contract("RCP-0001", 10000);
        assert_eq!(vote[0], 0x02);

        let badge = contracts::badge_mint_contract("pioneer", pk);
        assert_eq!(badge[0], 0x03);
    }
}
