//! Rustchain Main Entry Point
//!
//! This module contains the main entry point for the Rustchain node.

/// Initializes the blockchain state and starts the node.
pub fn initialize_node() {
    println!("Initializing Rustchain node...");
    
    // Fix: Corrected typo in code comment from 'recieve' to 'receive'
    // Start the P2P network listener to receive incoming transactions
    start_p2p_listener();
}

fn start_p2p_listener() {
    println!("P2P listener started on port 30303.");
}

fn main() {
    initialize_node();
}
