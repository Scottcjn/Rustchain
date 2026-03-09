//! Encrypted Storage Example
//!
//! This example demonstrates using the encrypted wallet storage system.

use rustchain_wallet::WalletStorage;
use tempfile::TempDir;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("=== RustChain Encrypted Storage Example ===\n");

    // Create a temporary directory for this example
    let temp_dir = TempDir::new()?;
    let storage_path = temp_dir.path().to_path_buf();
    
    println!("1. Initializing storage...");
    println!("   Storage path: {}\n", storage_path.display());

    let storage = WalletStorage::new(&storage_path)?;

    // Create and save multiple wallets
    println!("2. Creating and saving wallets...");
    
    let wallet1 = rustchain_wallet::Wallet::generate();
    let wallet2 = rustchain_wallet::Wallet::generate();
    let wallet3 = rustchain_wallet::Wallet::generate();
    
    let password1 = "secure_password_123";
    let password2 = "another_secure_password";
    let password3 = "third_wallet_password";
    
    let path1 = storage.save("alice", wallet1.keypair(), password1)?;
    let path2 = storage.save("bob", wallet2.keypair(), password2)?;
    let path3 = storage.save("charlie", wallet3.keypair(), password3)?;
    
    println!("   ✓ Saved 'alice'  -> {}", path1.display());
    println!("   ✓ Saved 'bob'    -> {}", path2.display());
    println!("   ✓ Saved 'charlie' -> {}\n", path3.display());

    // List all wallets
    println!("3. Listing stored wallets...");
    let wallets = storage.list()?;
    for name in &wallets {
        println!("   • {}", name);
    }
    println!("   Total: {} wallets\n", wallets.len());

    // Check if wallet exists
    println!("4. Checking wallet existence...");
    println!("   'alice' exists:   {}", storage.exists("alice"));
    println!("   'bob' exists:     {}", storage.exists("bob"));
    println!("   'dave' exists:    {}\n", storage.exists("dave"));

    // Load a wallet
    println!("5. Loading 'alice' wallet...");
    let loaded_keypair = storage.load("alice", password1)?;
    println!("   Address: {}", loaded_keypair.public_key_base58());
    println!("   Public Key: {}\n", loaded_keypair.public_key_hex());

    // Try to load with wrong password
    println!("6. Attempting to load with wrong password...");
    match storage.load("alice", "wrong_password") {
        Ok(_) => println!("   ERROR: Should have failed!"),
        Err(e) => println!("   ✓ Correctly rejected: {}\n", e),
    }

    // Use loaded wallet for signing
    println!("7. Using loaded wallet for signing...");
    let message = b"Signed from encrypted storage";
    let signature = loaded_keypair.sign(message)?;
    let valid = loaded_keypair.verify(message, &signature)?;
    println!("   Signature valid: {}\n", valid);

    // Delete a wallet
    println!("8. Deleting 'charlie' wallet...");
    storage.delete("charlie")?;
    println!("   ✓ Deleted\n");

    // Verify deletion
    println!("9. Verifying deletion...");
    println!("   'charlie' exists: {}\n", storage.exists("charlie"));

    // List remaining wallets
    println!("10. Listing remaining wallets...");
    let wallets = storage.list()?;
    for name in &wallets {
        println!("   • {}", name);
    }
    println!();

    // Demonstrate default storage location
    println!("11. Default storage location...");
    match WalletStorage::default_path() {
        Ok(path) => println!("   Default path: {}", path.display()),
        Err(e) => println!("   Could not determine default path: {}", e),
    }
    println!();

    println!("=== Example Complete ===");
    println!("\nNote: Temporary storage was used. Files were deleted on exit.");
    
    Ok(())
}
