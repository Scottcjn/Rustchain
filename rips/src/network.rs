// RIP-005: RustChain Network Protocol
// ====================================
// P2P network protocol for node communication
// Status: DRAFT
// Author: Flamekeeper Scott
// Created: 2025-11-28

use std::collections::{HashMap, HashSet};
use std::net::SocketAddr;
use std::time::{Duration, Instant};
use sha2::{Sha256, Digest};
use serde::{Serialize, Deserialize};

// Import from RIP-001
use crate::core_types::{
    Block, BlockHash, WalletAddress, Transaction, TxHash,
    MiningProof, HardwareInfo, TokenAmount
};

/// Protocol version
pub const PROTOCOL_VERSION: u32 = 1;

/// Default port for RustChain nodes
pub const DEFAULT_PORT: u16 = 8085;

/// mTLS port for vintage hardware
pub const MTLS_PORT: u16 = 4443;

/// Maximum peers to connect to
pub const MAX_PEERS: usize = 50;

/// Peer timeout in seconds
pub const PEER_TIMEOUT_SECS: u64 = 120;

/// Block propagation timeout
pub const BLOCK_PROPAGATION_TIMEOUT_SECS: u64 = 30;

/// Message types for the RustChain protocol
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Message {
    // === Handshake Messages ===
    /// Initial connection request
    Hello(HelloMessage),
    /// Response to hello with peer info
    HelloAck(HelloAckMessage),
    /// Periodic heartbeat
    Ping(u64),
    /// Response to ping
    Pong(u64),
    /// Graceful disconnect
    Goodbye(String),

    // === Chain Sync Messages ===
    /// Request chain info
    GetChainInfo,
    /// Chain info response
    ChainInfo(ChainInfoMessage),
    /// Request specific blocks
    GetBlocks(GetBlocksRequest),
    /// Block response
    Blocks(Vec<Block>),
    /// Request specific block by hash
    GetBlockByHash(BlockHash),
    /// Single block response
    BlockResponse(Option<Block>),

    // === Transaction Messages ===
    /// Broadcast new transaction
    NewTransaction(Transaction),
    /// Request pending transactions
    GetPendingTransactions,
    /// Pending transactions response
    PendingTransactions(Vec<Transaction>),

    // === Mining Messages ===
    /// New mining proof submission
    NewMiningProof(MiningProof),
    /// Request current mining status
    GetMiningStatus,
    /// Mining status response
    MiningStatus(MiningStatusMessage),
    /// New block announcement
    NewBlock(Block),

    // === Peer Discovery ===
    /// Request peer list
    GetPeers,
    /// Peer list response
    Peers(Vec<PeerInfo>),
    /// Announce self as peer
    AnnouncePeer(PeerInfo),

    // === Vintage Hardware Messages ===
    /// mTLS attestation from vintage hardware
    VintageAttestation(VintageAttestationMessage),
    /// Challenge for vintage hardware verification
    VintageChallenge(VintageChallengeMessage),
    /// Challenge response
    VintageChallengeResponse(VintageChallengeResponseMessage),
}

/// Hello message for initial connection
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HelloMessage {
    /// Protocol version
    pub version: u32,
    /// Node's chain ID
    pub chain_id: u64,
    /// Node's best block height
    pub best_block_height: u64,
    /// Node's best block hash
    pub best_block_hash: BlockHash,
    /// Node's capabilities
    pub capabilities: NodeCapabilities,
    /// Node's public key (for verification)
    pub public_key: Vec<u8>,
    /// Timestamp
    pub timestamp: u64,
}

/// Hello acknowledgment
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HelloAckMessage {
    /// Protocol version accepted
    pub version: u32,
    /// Node's peer ID
    pub peer_id: PeerId,
    /// Whether we need to sync
    pub needs_sync: bool,
    /// Timestamp
    pub timestamp: u64,
}

/// Chain info response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChainInfoMessage {
    /// Chain ID
    pub chain_id: u64,
    /// Current block height
    pub block_height: u64,
    /// Best block hash
    pub best_block_hash: BlockHash,
    /// Total minted tokens
    pub total_minted: TokenAmount,
    /// Mining pool remaining
    pub mining_pool: TokenAmount,
    /// Number of registered miners
    pub registered_miners: u64,
    /// Genesis block hash
    pub genesis_hash: BlockHash,
}

/// Get blocks request
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GetBlocksRequest {
    /// Start block height
    pub start_height: u64,
    /// Number of blocks to request (max 100)
    pub count: u32,
}

/// Mining status response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MiningStatusMessage {
    /// Current block being assembled
    pub current_block_height: u64,
    /// Pending proofs count
    pub pending_proofs: u32,
    /// Total multipliers in current block
    pub total_multipliers: f64,
    /// Time until block completion
    pub time_remaining_secs: u64,
    /// Is accepting proofs
    pub accepting_proofs: bool,
}

/// Peer info
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PeerInfo {
    /// Peer ID
    pub peer_id: PeerId,
    /// Network address
    pub address: String,
    /// Port
    pub port: u16,
    /// Capabilities
    pub capabilities: NodeCapabilities,
    /// Last seen timestamp
    pub last_seen: u64,
    /// Is vintage hardware node
    pub is_vintage: bool,
}

/// Unique peer identifier
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct PeerId(pub [u8; 32]);

impl PeerId {
    /// Generate from public key
    pub fn from_public_key(public_key: &[u8]) -> Self {
        let mut hasher = Sha256::new();
        hasher.update(b"rustchain-peer-id:");
        hasher.update(public_key);
        PeerId(hasher.finalize().into())
    }

    /// Display as hex string
    pub fn to_hex(&self) -> String {
        hex::encode(&self.0[..16]) // First 16 bytes for display
    }
}

/// Node capabilities flags
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NodeCapabilities {
    /// Can serve historical blocks
    pub archive_node: bool,
    /// Can validate transactions
    pub validator: bool,
    /// Supports mTLS for vintage hardware
    pub mtls_enabled: bool,
    /// Is a mining node
    pub miner: bool,
    /// Supports vintage hardware attestation
    pub vintage_attestation: bool,
    /// Maximum block height we have
    pub max_block_height: u64,
}

impl Default for NodeCapabilities {
    fn default() -> Self {
        NodeCapabilities {
            archive_node: false,
            validator: true,
            mtls_enabled: false,
            miner: false,
            vintage_attestation: false,
            max_block_height: 0,
        }
    }
}

/// Vintage hardware attestation message (for mTLS clients)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VintageAttestationMessage {
    /// Wallet address
    pub wallet: WalletAddress,
    /// Hardware info
    pub hardware: HardwareInfo,
    /// mTLS certificate hash
    pub cert_hash: [u8; 32],
    /// Anti-emulation proof
    pub anti_emulation_hash: [u8; 32],
    /// Entropy proof data
    pub entropy_data: Vec<u8>,
    /// Timestamp
    pub timestamp: u64,
    /// Signature
    pub signature: Vec<u8>,
}

/// Challenge for vintage hardware
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VintageChallengeMessage {
    /// Challenge nonce
    pub nonce: [u8; 32],
    /// Operations to perform
    pub operations: Vec<u8>,
    /// Expected timing range (min, max) in microseconds
    pub expected_timing: (u64, u64),
    /// Challenge expiry timestamp
    pub expires_at: u64,
}

/// Challenge response from vintage hardware
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VintageChallengeResponseMessage {
    /// Original challenge nonce
    pub challenge_nonce: [u8; 32],
    /// Computed response
    pub response: [u8; 32],
    /// Time taken in microseconds
    pub computation_time_us: u64,
    /// Additional entropy samples
    pub entropy_samples: Vec<u8>,
}

/// Network error types
#[derive(Debug)]
pub enum NetworkError {
    ConnectionFailed(String),
    Timeout,
    InvalidMessage(String),
    ProtocolMismatch { expected: u32, got: u32 },
    ChainMismatch { expected: u64, got: u64 },
    PeerBanned(PeerId),
    TooManyPeers,
    InvalidSignature,
}

/// Peer state
#[derive(Debug)]
pub struct PeerState {
    /// Peer info
    pub info: PeerInfo,
    /// Connection state
    pub state: ConnectionState,
    /// Last ping time
    pub last_ping: Instant,
    /// Pending requests
    pub pending_requests: HashSet<u64>,
    /// Reputation score (0-100)
    pub reputation: u32,
    /// Messages sent
    pub messages_sent: u64,
    /// Messages received
    pub messages_received: u64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ConnectionState {
    Connecting,
    Connected,
    Syncing,
    Ready,
    Disconnecting,
    Disconnected,
}

/// Network manager for handling peer connections
#[derive(Debug)]
pub struct NetworkManager {
    /// Our peer ID
    pub local_peer_id: PeerId,
    /// Our capabilities
    pub capabilities: NodeCapabilities,
    /// Connected peers
    pub peers: HashMap<PeerId, PeerState>,
    /// Known peer addresses
    pub known_peers: HashSet<String>,
    /// Banned peers
    pub banned_peers: HashSet<PeerId>,
    /// Message handlers
    message_id_counter: u64,
}

impl NetworkManager {
    pub fn new(public_key: &[u8], capabilities: NodeCapabilities) -> Self {
        NetworkManager {
            local_peer_id: PeerId::from_public_key(public_key),
            capabilities,
            peers: HashMap::new(),
            known_peers: HashSet::new(),
            banned_peers: HashSet::new(),
            message_id_counter: 0,
        }
    }

    /// Add a peer connection
    pub fn add_peer(&mut self, peer_info: PeerInfo) -> Result<(), NetworkError> {
        if self.peers.len() >= MAX_PEERS {
            return Err(NetworkError::TooManyPeers);
        }

        if self.banned_peers.contains(&peer_info.peer_id) {
            return Err(NetworkError::PeerBanned(peer_info.peer_id.clone()));
        }

        let state = PeerState {
            info: peer_info.clone(),
            state: ConnectionState::Connected,
            last_ping: Instant::now(),
            pending_requests: HashSet::new(),
            reputation: 50, // Start neutral
            messages_sent: 0,
            messages_received: 0,
        };

        self.peers.insert(peer_info.peer_id.clone(), state);
        self.known_peers.insert(format!("{}:{}", peer_info.address, peer_info.port));

        Ok(())
    }

    /// Remove a peer
    pub fn remove_peer(&mut self, peer_id: &PeerId) {
        self.peers.remove(peer_id);
    }

    /// Update peer reputation
    pub fn update_reputation(&mut self, peer_id: &PeerId, delta: i32) {
        if let Some(peer) = self.peers.get_mut(peer_id) {
            let new_rep = (peer.reputation as i32 + delta).clamp(0, 100) as u32;
            peer.reputation = new_rep;

            // Ban peers with very low reputation
            if new_rep == 0 {
                self.banned_peers.insert(peer_id.clone());
                self.peers.remove(peer_id);
            }
        }
    }

    /// Get peers for message broadcast
    pub fn get_broadcast_peers(&self, exclude: Option<&PeerId>) -> Vec<&PeerId> {
        self.peers
            .iter()
            .filter(|(id, state)| {
                state.state == ConnectionState::Ready
                    && exclude.map_or(true, |e| *id != e)
            })
            .map(|(id, _)| id)
            .collect()
    }

    /// Create hello message
    pub fn create_hello(&self, chain_info: &ChainInfoMessage) -> Message {
        Message::Hello(HelloMessage {
            version: PROTOCOL_VERSION,
            chain_id: chain_info.chain_id,
            best_block_height: chain_info.block_height,
            best_block_hash: chain_info.best_block_hash.clone(),
            capabilities: self.capabilities.clone(),
            public_key: vec![], // Would be filled in by caller
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_secs(),
        })
    }

    /// Process incoming message
    pub fn handle_message(
        &mut self,
        from: &PeerId,
        message: Message,
    ) -> Result<Option<Message>, NetworkError> {
        // Update peer state
        if let Some(peer) = self.peers.get_mut(from) {
            peer.messages_received += 1;
            peer.last_ping = Instant::now();
        }

        match message {
            Message::Ping(nonce) => Ok(Some(Message::Pong(nonce))),

            Message::GetPeers => {
                let peers: Vec<PeerInfo> = self.peers
                    .values()
                    .filter(|p| p.state == ConnectionState::Ready)
                    .map(|p| p.info.clone())
                    .collect();
                Ok(Some(Message::Peers(peers)))
            }

            Message::AnnouncePeer(info) => {
                self.known_peers.insert(format!("{}:{}", info.address, info.port));
                Ok(None)
            }

            Message::Goodbye(reason) => {
                self.remove_peer(from);
                Ok(None)
            }

            // Other messages would be handled by higher layers
            _ => Ok(None),
        }
    }

    /// Get next message ID
    pub fn next_message_id(&mut self) -> u64 {
        self.message_id_counter += 1;
        self.message_id_counter
    }

    /// Clean up stale peers
    pub fn cleanup_stale_peers(&mut self) {
        let timeout = Duration::from_secs(PEER_TIMEOUT_SECS);
        let stale_peers: Vec<PeerId> = self.peers
            .iter()
            .filter(|(_, state)| state.last_ping.elapsed() > timeout)
            .map(|(id, _)| id.clone())
            .collect();

        for peer_id in stale_peers {
            self.remove_peer(&peer_id);
        }
    }
}

/// Block propagation manager
#[derive(Debug)]
pub struct BlockPropagator {
    /// Blocks we've seen (to avoid re-broadcasting)
    seen_blocks: HashMap<BlockHash, Instant>,
    /// Pending block announcements
    pending_announcements: Vec<(BlockHash, Instant)>,
}

impl BlockPropagator {
    pub fn new() -> Self {
        BlockPropagator {
            seen_blocks: HashMap::new(),
            pending_announcements: Vec::new(),
        }
    }

    /// Check if we've seen this block
    pub fn has_seen(&self, hash: &BlockHash) -> bool {
        self.seen_blocks.contains_key(hash)
    }

    /// Mark block as seen
    pub fn mark_seen(&mut self, hash: BlockHash) {
        self.seen_blocks.insert(hash, Instant::now());
    }

    /// Clean up old seen blocks (keep last hour)
    pub fn cleanup(&mut self) {
        let cutoff = Instant::now() - Duration::from_secs(3600);
        self.seen_blocks.retain(|_, when| *when > cutoff);
    }
}

/// API endpoint definitions
pub mod api {
    use super::*;

    /// REST API endpoints
    pub const API_PREFIX: &str = "/api";

    #[derive(Debug, Clone)]
    pub enum Endpoint {
        /// GET /api/stats - Get blockchain statistics
        Stats,
        /// GET /api/blocks - List blocks
        Blocks,
        /// GET /api/block/:hash - Get specific block
        BlockByHash(String),
        /// GET /api/wallets - List wallets
        Wallets,
        /// GET /api/wallet/:address - Get wallet details
        WalletByAddress(String),
        /// POST /api/mine - Submit mining proof
        Mine,
        /// POST /api/send - Send transaction
        Send,
        /// GET /api/faucet - Request test tokens
        Faucet,
        /// GET /api/badges/:wallet - Get badges for wallet
        Badges(String),
        /// POST /api/hardware/verify - Verify hardware attestation
        HardwareVerify,
    }

    impl Endpoint {
        pub fn path(&self) -> String {
            match self {
                Endpoint::Stats => format!("{}/stats", API_PREFIX),
                Endpoint::Blocks => format!("{}/blocks", API_PREFIX),
                Endpoint::BlockByHash(h) => format!("{}/block/{}", API_PREFIX, h),
                Endpoint::Wallets => format!("{}/wallets", API_PREFIX),
                Endpoint::WalletByAddress(a) => format!("{}/wallet/{}", API_PREFIX, a),
                Endpoint::Mine => format!("{}/mine", API_PREFIX),
                Endpoint::Send => format!("{}/send", API_PREFIX),
                Endpoint::Faucet => format!("{}/faucet", API_PREFIX),
                Endpoint::Badges(w) => format!("{}/badges/{}", API_PREFIX, w),
                Endpoint::HardwareVerify => format!("{}/hardware/verify", API_PREFIX),
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_peer_id_generation() {
        let public_key = b"test_public_key_12345";
        let peer_id = PeerId::from_public_key(public_key);
        assert_eq!(peer_id.0.len(), 32);
    }

    #[test]
    fn test_network_manager_add_peer() {
        let mut manager = NetworkManager::new(b"test_key", NodeCapabilities::default());

        let peer_info = PeerInfo {
            peer_id: PeerId::from_public_key(b"peer_key"),
            address: "192.168.1.100".to_string(),
            port: 8085,
            capabilities: NodeCapabilities::default(),
            last_seen: 0,
            is_vintage: false,
        };

        assert!(manager.add_peer(peer_info).is_ok());
        assert_eq!(manager.peers.len(), 1);
    }

    #[test]
    fn test_reputation_system() {
        let mut manager = NetworkManager::new(b"test_key", NodeCapabilities::default());

        let peer_id = PeerId::from_public_key(b"peer_key");
        let peer_info = PeerInfo {
            peer_id: peer_id.clone(),
            address: "192.168.1.100".to_string(),
            port: 8085,
            capabilities: NodeCapabilities::default(),
            last_seen: 0,
            is_vintage: false,
        };

        manager.add_peer(peer_info).unwrap();

        // Good behavior increases reputation
        manager.update_reputation(&peer_id, 10);
        assert_eq!(manager.peers.get(&peer_id).unwrap().reputation, 60);

        // Bad behavior decreases reputation
        manager.update_reputation(&peer_id, -20);
        assert_eq!(manager.peers.get(&peer_id).unwrap().reputation, 40);
    }

    #[test]
    fn test_block_propagator() {
        let mut propagator = BlockPropagator::new();

        let hash = BlockHash::from_bytes([1u8; 32]);

        assert!(!propagator.has_seen(&hash));
        propagator.mark_seen(hash.clone());
        assert!(propagator.has_seen(&hash));
    }

    #[test]
    fn test_message_ping_pong() {
        let mut manager = NetworkManager::new(b"test_key", NodeCapabilities::default());

        let peer_id = PeerId::from_public_key(b"peer_key");
        let peer_info = PeerInfo {
            peer_id: peer_id.clone(),
            address: "192.168.1.100".to_string(),
            port: 8085,
            capabilities: NodeCapabilities::default(),
            last_seen: 0,
            is_vintage: false,
        };

        manager.add_peer(peer_info).unwrap();

        let response = manager.handle_message(&peer_id, Message::Ping(12345)).unwrap();
        assert!(matches!(response, Some(Message::Pong(12345))));
    }
}
