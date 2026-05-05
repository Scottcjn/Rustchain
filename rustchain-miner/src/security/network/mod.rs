// SPDX-License-Identifier: Apache-2.0


use std::net::{SocketAddr, TcpStream};
use std::io::{Read, Write};
use std::time::Duration;
use serde::{Serialize, Deserialize};
use log::{info, warn, error};
use thiserror::Error;
use hmac::{Hmac, Mac};
use sha2::Sha256;
use aes_gcm::{
    aead::{Aead, KeyInit, OsRng},
    Aes256Gcm, Nonce
};
use rand::RngCore;
use rand::rngs::OsRng as RandOsRng;

/// Network security error type
#[derive(Error, Debug)]
pub enum NetworkSecurityError {
    #[error("Connection error: {0}")]
    ConnectionError(String),

    #[error("Authentication error: {0}")]
    AuthenticationError(String),

    #[error("Encryption error: {0}")]
    EncryptionError(String),

    #[error("Invalid data: {0}")]
    InvalidDataError(String),

    #[error("Timeout error")]
    TimeoutError,
}

/// Peer information
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct PeerInfo {
    pub peer_id: String,
    pub address: SocketAddr,
    pub public_key: Vec<u8>,
    pub last_seen: u64,
}

/// Network security module
pub struct NetworkSecurity;

impl NetworkSecurity {
    /// Create a new network security instance
    pub fn new() -> Self {
        NetworkSecurity
    }

    /// Establish a secure connection to a peer
    pub fn establish_secure_connection(
        &self,
        address: SocketAddr,
        timeout: Duration,
    ) -> Result<TcpStream, NetworkSecurityError> {
        info!("Establishing secure connection to {}", address);

        // Set up connection with timeout
        let stream = TcpStream::connect_timeout(&address, timeout)
            .map_err(|e| NetworkSecurityError::ConnectionError(e.to_string()))?;

        // Set read/write timeout
        stream.set_read_timeout(Some(timeout))
            .map_err(|e| NetworkSecurityError::ConnectionError(e.to_string()))?;
        stream.set_write_timeout(Some(timeout))
            .map_err(|e| NetworkSecurityError::ConnectionError(e.to_string()))?;

        info!("Connection established to {}", address);

        Ok(stream)
    }

    /// Perform peer authentication
    pub fn authenticate_peer(
        &self,
        stream: &mut TcpStream,
        expected_peer_id: &str,
        timeout: Duration,
    ) -> Result<PeerInfo, NetworkSecurityError> {
        info!("Authenticating peer with ID: {}", expected_peer_id);

        // In a real implementation, this would involve cryptographic authentication
        // For now, we'll simulate the process

        // Generate a random challenge
        let mut challenge = [0u8; 32];
        RandOsRng.fill_bytes(&mut challenge);

        // Send challenge to peer
        stream.write_all(&challenge)
            .map_err(|e| NetworkSecurityError::ConnectionError(e.to_string()))?;

        // Receive response (in a real implementation, this would be signed with the peer's private key)
        let mut response = [0u8; 32];
        stream.read_exact(&mut response)
            .map_err(|e| NetworkSecurityError::ConnectionError(e.to_string()))?;

        // Verify response (in a real implementation, we would verify the signature)
        if response != challenge {
            return Err(NetworkSecurityError::AuthenticationError(
                "Peer authentication failed".to_string()
            ));
        }

        // Create peer info
        let peer_info = PeerInfo {
            peer_id: expected_peer_id.to_string(),
            address: stream.peer_addr()
                .map_err(|e| NetworkSecurityError::ConnectionError(e.to_string()))?,
            public_key: vec![], // In a real implementation, this would be the peer's public key
            last_seen: chrono::Utc::now().timestamp() as u64,
        };

        info!("Peer {} authenticated successfully", expected_peer_id);

        Ok(peer_info)
    }

    /// Encrypt network traffic
    pub fn encrypt_traffic(
        data: &[u8],
        key: &[u8],
    ) -> Result<(Vec<u8>, Vec<u8>), NetworkSecurityError> {
        // Validate key size
        if key.len() != 32 {
            return Err(NetworkSecurityError::EncryptionError(
                "Invalid key size".to_string()
            ));
        }

        // Generate a random nonce
        let mut nonce = [0u8; 12];
        RandOsRng.fill_bytes(&mut nonce);

        // Create cipher
        let cipher = Aes256Gcm::new_from_slice(key)
            .map_err(|e| NetworkSecurityError::EncryptionError(e.to_string()))?;

        // Encrypt
        let ciphertext = cipher.encrypt(Nonce::from_slice(&nonce), data)
            .map_err(|e| NetworkSecurityError::EncryptionError(e.to_string()))?;

        Ok((ciphertext, nonce.to_vec()))
    }

    /// Decrypt network traffic
    pub fn decrypt_traffic(
        ciphertext: &[u8],
        nonce: &[u8],
        key: &[u8],
    ) -> Result<Vec<u8>, NetworkSecurityError> {
        // Validate key size
        if key.len() != 32 {
            return Err(NetworkSecurityError::EncryptionError(
                "Invalid key size".to_string()
            ));
        }

        // Validate nonce size
        if nonce.len() != 12 {
            return Err(NetworkSecurityError::EncryptionError(
                "Invalid nonce size".to_string()
            ));
        }

        // Create cipher
        let cipher = Aes256Gcm::new_from_slice(key)
            .map_err(|e| NetworkSecurityError::EncryptionError(e.to_string()))?;

        // Decrypt
        let plaintext = cipher.decrypt(Nonce::from_slice(nonce), ciphertext)
            .map_err(|e| NetworkSecurityError::EncryptionError(e.to_string()))?;

        Ok(plaintext)
    }

    /// Generate a session key for secure communication
    pub fn generate_session_key() -> Vec<u8> {
        let mut key = vec![0u8; 32];
        RandOsRng.fill_bytes(&mut key);
        key
    }

    /// Verify message integrity using HMAC
    pub fn verify_message_integrity(
        data: &[u8],
        signature: &[u8],
        key: &[u8],
    ) -> Result<bool, NetworkSecurityError> {
        type HmacSha256 = Hmac<Sha256>;

        let mut mac = HmacSha256::new_from_slice(key)
            .map_err(|_| NetworkSecurityError::EncryptionError("Invalid key size".to_string()))?;

        mac.update(data);
        let expected_signature = mac.finalize().into_bytes();

        Ok(signature == expected_signature.as_slice())
    }

    /// Create a secure handshake protocol
    pub fn perform_handshake(
        stream: &mut TcpStream,
        local_peer_id: &str,
        timeout: Duration,
    ) -> Result<(PeerInfo, Vec<u8>), NetworkSecurityError> {
        info!("Performing handshake with peer");

        // Generate session key
        let session_key = Self::generate_session_key();

        // In a real implementation, this would involve a more complex handshake protocol
        // with cryptographic verification of peer identity

        // For now, we'll just send our peer ID and receive theirs
        stream.set_read_timeout(Some(timeout))
            .map_err(|e| NetworkSecurityError::ConnectionError(e.to_string()))?;
        stream.set_write_timeout(Some(timeout))
            .map_err(|e| NetworkSecurityError::ConnectionError(e.to_string()))?;

        // Send our peer ID
        stream.write_all(local_peer_id.as_bytes())
            .map_err(|e| NetworkSecurityError::ConnectionError(e.to_string()))?;

        // Receive peer ID
        let mut peer_id_buf = [0u8; 64];
        let bytes_read = stream.read(&mut peer_id_buf)
            .map_err(|e| NetworkSecurityError::ConnectionError(e.to_string()))?;

        if bytes_read == 0 {
            return Err(NetworkSecurityError::ConnectionError(
                "Peer closed connection".to_string()
            ));
        }

        let peer_id = String::from_utf8_lossy(&peer_id_buf[..bytes_read]).to_string();

        // Create peer info
        let peer_info = PeerInfo {
            peer_id: peer_id.clone(),
            address: stream.peer_addr()
                .map_err(|e| NetworkSecurityError::ConnectionError(e.to_string()))?,
            public_key: vec![], // In a real implementation, this would be the peer's public key
            last_seen: chrono::Utc::now().timestamp() as u64,
        };

        info!("Handshake completed with peer {}", peer_id);

        Ok((peer_info, session_key))
    }
}

