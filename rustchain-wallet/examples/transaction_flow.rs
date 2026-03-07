//! Transaction Flow Example
//!
//! This example demonstrates creating, signing, and serializing transactions.

use rustchain_wallet::{Wallet, Transaction, TransactionBuilder};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("=== RustChain Transaction Flow Example ===\n");

    // Create sender and recipient wallets
    println!("1. Creating wallets...");
    let sender = Wallet::generate();
    let recipient = Wallet::generate();
    
    println!("   Sender:    {}", sender.address());
    println!("   Recipient: {}\n", recipient.address());

    // Create a transaction using the builder
    println!("2. Creating transaction...");
    let mut tx = TransactionBuilder::new()
        .from(sender.address())
        .to(recipient.address())
        .amount(5000)           // 5000 RTC (smallest unit)
        .fee(100)               // 100 RTC fee
        .nonce(1)               // Transaction nonce
        .memo("Payment for services".to_string())
        .build()?;

    println!("   From:        {}", tx.from);
    println!("   To:          {}", tx.to);
    println!("   Amount:      {} RTC", tx.amount);
    println!("   Fee:         {} RTC", tx.fee);
    println!("   Total Cost:  {} RTC", tx.total_cost());
    println!("   Nonce:       {}", tx.nonce);
    println!("   Memo:        {:?}", tx.memo);
    println!("   Timestamp:   {}\n", tx.timestamp);

    // Sign the transaction
    println!("3. Signing transaction...");
    tx.sign(sender.keypair())?;
    println!("   Signature:   {}\n", tx.signature.as_ref().unwrap());

    // Get transaction hash
    println!("4. Computing transaction hash...");
    let hash = tx.hash()?;
    println!("   Hash: {}\n", hash);

    // Serialize to JSON
    println!("5. Serializing to JSON...");
    let json = tx.to_json()?;
    println!("   JSON:\n{}\n", json);

    // Deserialize from JSON
    println!("6. Deserializing from JSON...");
    let loaded_tx = Transaction::from_json(&json)?;
    println!("   Loaded successfully!");
    println!("   Signatures match: {}\n", tx.signature == loaded_tx.signature);

    // Verify the transaction
    println!("7. Verifying transaction signature...");
    let valid = tx.verify(sender.keypair())?;
    println!("   Valid: {}\n", valid);

    // Try to verify with wrong key
    println!("8. Verifying with wrong key (should fail)...");
    let valid = tx.verify(recipient.keypair())?;
    println!("   Valid: {} (expected: false)\n", valid);

    // Create multiple transactions with incrementing nonces
    println!("9. Creating multiple transactions...");
    let mut transactions = Vec::new();
    for i in 1usize..=3 {
        let mut tx = TransactionBuilder::new()
            .from(sender.address())
            .to(recipient.address())
            .amount(1000 * i as u64)
            .fee(100)
            .nonce(i as u64)
            .build()?;
        tx.sign(sender.keypair())?;
        transactions.push(tx);
        let hash: String = transactions[i-1].hash()?;
        println!("   TX {}: amount={}, hash={}", i, transactions[i-1].amount, hash);
    }

    println!("\n=== Example Complete ===");
    Ok(())
}
