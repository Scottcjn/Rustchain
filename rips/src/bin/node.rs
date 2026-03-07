//! RustChain Node - Full Node Implementation
//!
//! A full node implementation for the RustChain blockchain that:
//! - Validates blocks and transactions
//! - Participates in P2P network
//! - Serves historical data
//! - Supports vintage hardware attestation

use rustchain::{
    Block, BlockHash, HardwareInfo, ProofOfAntiquity,
    WalletAddress, TokenAmount, CHAIN_ID,
};
use rustchain::network::{
    NetworkManager, NodeCapabilities, PeerId, Message,
    ChainInfoMessage, HelloMessage,
};
use std::sync::Arc;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

/// Node configuration
#[derive(Debug, Clone)]
pub struct NodeConfig {
    /// Node wallet address
    pub wallet: WalletAddress,
    /// Network port to listen on
    pub port: u16,
    /// Data directory for blockchain storage
    pub data_dir: String,
    /// Enable mining
    pub enable_mining: bool,
    /// Enable RPC API
    pub enable_rpc: bool,
    /// RPC port
    pub rpc_port: u16,
    /// Seed nodes to connect to
    pub seed_nodes: Vec<String>,
}

impl Default for NodeConfig {
    fn default() -> Self {
        NodeConfig {
            wallet: WalletAddress::new("RTC1NodeDefault0000000000000000"),
            port: 8085,
            data_dir: "./rustchain_data".to_string(),
            enable_mining: false,
            enable_rpc: true,
            rpc_port: 8086,
            seed_nodes: vec![],
        }
    }
}

/// RustChain full node
pub struct RustChainNode {
    /// Node configuration
    config: NodeConfig,
    /// Network manager
    network: NetworkManager,
    /// Proof of Antiquity consensus
    poa: ProofOfAntiquity,
    /// Current chain height
    chain_height: u64,
    /// Best block hash
    best_block_hash: BlockHash,
    /// Shutdown flag
    shutdown: bool,
}

impl RustChainNode {
    /// Create a new node
    pub fn new(config: NodeConfig) -> Self {
        // Generate node keypair (simplified for now)
        let public_key = b"rustchain_node_key_v1";
        
        let capabilities = NodeCapabilities {
            archive_node: true,
            validator: true,
            mtls_enabled: false,
            miner: config.enable_mining,
            vintage_attestation: true,
            max_block_height: 0,
        };

        RustChainNode {
            config,
            network: NetworkManager::new(public_key, capabilities),
            poa: ProofOfAntiquity::new(),
            chain_height: 0,
            best_block_hash: BlockHash::genesis(),
            shutdown: false,
        }
    }

    /// Start the node
    pub fn start(&mut self) -> Result<(), NodeError> {
        println!("🔥 Starting RustChain Node...");
        println!("   Chain ID: {}", CHAIN_ID);
        println!("   Wallet: {}", self.config.wallet.0);
        println!("   Port: {}", self.config.port);
        println!("   Data Dir: {}", self.config.data_dir);
        println!("   Mining: {}", if self.config.enable_mining { "Enabled" } else { "Disabled" });

        // Initialize genesis block
        self.initialize_genesis()?;

        // Start network listener
        self.start_network()?;

        // Main event loop
        self.run_event_loop()?;

        Ok(())
    }

    /// Stop the node
    pub fn stop(&mut self) {
        println!("🛑 Stopping RustChain Node...");
        self.shutdown = true;
    }

    fn initialize_genesis(&mut self) -> Result<(), NodeError> {
        println!("📦 Initializing genesis block...");
        self.best_block_hash = BlockHash::genesis();
        self.chain_height = 0;
        Ok(())
    }

    fn start_network(&mut self) -> Result<(), NodeError> {
        println!("🌐 Starting network listener on port {}...", self.config.port);
        
        // Connect to seed nodes
        for seed in &self.config.seed_nodes {
            println!("   Connecting to seed: {}", seed);
            // In real implementation: self.network.connect(seed)?;
        }

        Ok(())
    }

    fn run_event_loop(&mut self) -> Result<(), NodeError> {
        println!("🔄 Starting event loop...");
        
        let mut last_status = SystemTime::now();
        
        while !self.shutdown {
            // Process network messages
            self.process_network_messages()?;
            
            // Check for block completion
            self.check_block_completion();
            
            // Periodic status
            if let Ok(elapsed) = last_status.elapsed() {
                if elapsed >= Duration::from_secs(60) {
                    self.print_status();
                    last_status = SystemTime::now();
                }
            }

            // Small sleep to prevent busy-waiting
            std::thread::sleep(Duration::from_millis(100));
        }

        Ok(())
    }

    fn process_network_messages(&mut self) -> Result<(), NodeError> {
        // In real implementation, this would process actual network messages
        // For now, just a placeholder
        Ok(())
    }

    fn check_block_completion(&mut self) {
        let status = self.poa.get_status();
        
        if status.time_remaining == 0 && status.pending_proofs > 0 {
            // Block window closed, process block
            if let Some(block) = self.poa.process_block(
                self.best_block_hash.0,
                self.chain_height + 1,
            ) {
                self.accept_block(block);
            }
        }
    }

    fn accept_block(&mut self, block: Block) {
        println!("✅ Accepted block #{} with {} miners", 
                 block.height, block.miners.len());
        
        self.best_block_hash = block.hash.clone();
        self.chain_height = block.height;
        
        // Update capabilities
        self.network.capabilities.max_block_height = block.height;
        
        // Broadcast to peers
        self.broadcast_block(block);
    }

    fn broadcast_block(&self, block: Block) {
        // In real implementation, broadcast to all connected peers
        let _ = block; // Suppress unused warning
    }

    fn print_status(&self) {
        let status = self.poa.get_status();
        println!("📊 Node Status:");
        println!("   Height: {}", self.chain_height);
        println!("   Best Hash: {}", self.best_block_hash.to_hex());
        println!("   Peers: {}", self.network.peers.len());
        println!("   Pending Proofs: {}", status.pending_proofs);
        println!("   Block Time Remaining: {}s", status.time_remaining);
    }

    /// Get current chain info
    pub fn get_chain_info(&self) -> ChainInfoMessage {
        ChainInfoMessage {
            chain_id: CHAIN_ID,
            block_height: self.chain_height,
            best_block_hash: self.best_block_hash.clone(),
            total_minted: TokenAmount(self.chain_height * 100_000_000),
            mining_pool: TokenAmount(8_388_608 * 100_000_000 - self.chain_height * 100_000_000),
            registered_miners: self.poa.get_status().pending_proofs as u64,
            genesis_hash: BlockHash::genesis(),
        }
    }

    /// Submit a mining proof
    pub fn submit_proof(&mut self, proof: rustchain::MiningProof) -> Result<rustchain::proof_of_antiquity::SubmitResult, rustchain::proof_of_antiquity::ProofError> {
        self.poa.submit_proof(proof)
    }
}

/// Node error types
#[derive(Debug)]
pub enum NodeError {
    NetworkError(String),
    DatabaseError(String),
    ConsensusError(String),
    ConfigurationError(String),
}

impl std::fmt::Display for NodeError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            NodeError::NetworkError(e) => write!(f, "Network error: {}", e),
            NodeError::DatabaseError(e) => write!(f, "Database error: {}", e),
            NodeError::ConsensusError(e) => write!(f, "Consensus error: {}", e),
            NodeError::ConfigurationError(e) => write!(f, "Configuration error: {}", e),
        }
    }
}

impl std::error::Error for NodeError {}

fn main() {
    println!("🔥 RustChain Node v0.1.0");
    println!("   Proof of Antiquity Blockchain");
    println!();

    let config = NodeConfig::default();
    let mut node = RustChainNode::new(config);

    // Handle Ctrl+C
    let ctrlc_result = ctrlc::set_handler(move || {
        println!("\n⚠️  Received shutdown signal");
    });

    if let Err(e) = ctrlc_result {
        eprintln!("Error setting Ctrl+C handler: {}", e);
    }

    match node.start() {
        Ok(_) => println!("Node shutdown gracefully"),
        Err(e) => eprintln!("Node error: {}", e),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_node_creation() {
        let config = NodeConfig::default();
        let node = RustChainNode::new(config);
        
        assert_eq!(node.chain_height, 0);
        assert_eq!(node.best_block_hash, BlockHash::genesis());
    }

    #[test]
    fn test_chain_info() {
        let config = NodeConfig::default();
        let node = RustChainNode::new(config);
        let info = node.get_chain_info();
        
        assert_eq!(info.chain_id, CHAIN_ID);
        assert_eq!(info.block_height, 0);
    }
}
