//! Basic Wallet Example
//!
//! This example demonstrates basic wallet creation, signing, and verification.

use rustchain_wallet::{Wallet, KeyPair, Network};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("=== RustChain Wallet Basic Example ===\n");

    // Generate a new wallet
    println!("1. Generating a new wallet...");
    let wallet = Wallet::generate();
    
    println!("   Address:    {}", wallet.address());
    println!("   Public Key: {}", wallet.public_key());
    println!("   Network:    {}\n", wallet.network());

    // Create a wallet on testnet
    println!("2. Creating a testnet wallet...");
    let testnet_wallet = Wallet::with_network(KeyPair::generate(), Network::Testnet);
    println!("   Address:    {}", testnet_wallet.address());
    println!("   Network:    {}\n", testnet_wallet.network());

    // Sign a message
    println!("3. Signing a message...");
    let message = b"Hello, RustChain!";
    let signature = wallet.sign(message)?;
    println!("   Message:   {}", String::from_utf8_lossy(message));
    println!("   Signature: {}\n", hex::encode(&signature));

    // Verify the signature
    println!("4. Verifying the signature...");
    let valid = wallet.verify(message, &signature)?;
    println!("   Valid: {}\n", valid);

    // Try to verify with wrong message
    println!("5. Verifying with wrong message (should fail)...");
    let wrong_message = b"Wrong message";
    let valid = wallet.verify(wrong_message, &signature)?;
    println!("   Valid: {} (expected: false)\n", valid);

    // Export private key (demonstration only - don't do this in production!)
    println!("6. Exporting private key (for demonstration)...");
    let private_key = wallet.export_private_key();
    println!("   Private Key: {} (keep this secret!)\n", private_key);

    // Import from private key
    println!("7. Importing wallet from private key...");
    let imported_keypair = KeyPair::from_hex(&private_key)?;
    println!("   Imported Address: {}", bs58::encode(imported_keypair.public_key_bytes()).into_string());
    println!("   Matches original: {}\n", 
        imported_keypair.public_key_bytes() == wallet.keypair().public_key_bytes());

    println!("=== Example Complete ===");
    Ok(())
}
