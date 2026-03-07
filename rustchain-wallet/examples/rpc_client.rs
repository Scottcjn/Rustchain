//! RPC Client Example
//!
//! This example demonstrates using the RustChain RPC client.
//! Note: This example requires a running RustChain node or access to a public RPC endpoint.

use rustchain_wallet::{RustChainClient, Network, TransactionBuilder, Wallet};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("=== RustChain RPC Client Example ===\n");

    // Create a client for mainnet
    println!("1. Creating RPC client...");
    let client = RustChainClient::new(Network::Mainnet.rpc_url().to_string());
    println!("   RPC URL: {}\n", Network::Mainnet.rpc_url());

    // Health check
    println!("2. Performing health check...");
    match client.health_check().await {
        Ok(true) => println!("   ✓ RPC endpoint is reachable\n"),
        Ok(false) => println!("   ✗ RPC endpoint is not reachable\n"),
        Err(e) => println!("   ✗ Health check failed: {}\n", e),
    }

    // Get network information
    println!("3. Getting network information...");
    match client.get_network_info().await {
        Ok(info) => {
            println!("   Chain ID:      {}", info.chain_id);
            println!("   Network:       {}", info.network);
            println!("   Block Height:  {}", info.block_height);
            println!("   Peer Count:    {}", info.peer_count);
            println!("   Min Fee:       {} RTC", info.min_fee);
            println!("   Version:       {}\n", info.version);
        }
        Err(e) => {
            println!("   Note: Could not fetch network info (node may be offline)");
            println!("   Error: {}\n", e);
        }
    }

    // Get minimum fee
    println!("4. Getting minimum fee...");
    match client.get_min_fee().await {
        Ok(fee) => println!("   Min Fee: {} RTC\n", fee),
        Err(e) => println!("   Could not get fee: {}\n", e),
    }

    // Estimate fees for different priorities
    println!("5. Estimating fees for different priorities...");
    use rustchain_wallet::client::FeePriority;
    
    for priority in [FeePriority::Low, FeePriority::Normal, FeePriority::High, FeePriority::Instant] {
        match client.estimate_fee(1000, priority).await {
            Ok(fee) => println!("   {:?}: {} RTC", priority, fee),
            Err(_) => println!("   {:?}: Could not estimate", priority),
        }
    }
    println!();

    // Example: Check balance (using a sample address)
    println!("6. Example balance query...");
    let sample_address = "1abc123example456address789"; // Replace with real address
    println!("   Address: {}", sample_address);
    match client.get_balance(sample_address).await {
        Ok(balance) => {
            println!("   Balance:     {} RTC", balance.balance);
            println!("   Unlocked:    {} RTC", balance.unlocked);
            println!("   Locked:      {} RTC", balance.locked);
            println!("   Nonce:       {}", balance.nonce);
        }
        Err(e) => {
            println!("   Note: Could not fetch balance (address may not exist or node offline)");
            println!("   Error: {}", e);
        }
    }
    println!();

    // Example: Get nonce
    println!("7. Example nonce query...");
    match client.get_nonce(sample_address).await {
        Ok(nonce) => println!("   Nonce: {}\n", nonce),
        Err(e) => println!("   Could not get nonce: {}\n", e),
    }

    // Example: Prepare a transaction (without submitting)
    println!("8. Preparing a sample transaction...");
    let wallet = Wallet::generate();
    let mut tx = TransactionBuilder::new()
        .from(wallet.address())
        .to("recipient_address".to_string())
        .amount(1000)
        .fee(100)
        .nonce(0)
        .build()?;
    
    // Sign the transaction
    tx.sign(wallet.keypair())?;
    
    println!("   Transaction prepared:");
    println!("   From:     {}", tx.from);
    println!("   To:       {}", tx.to);
    println!("   Amount:   {} RTC", tx.amount);
    println!("   Fee:      {} RTC", tx.fee);
    println!("   Hash:     {}", tx.hash()?);
    println!();

    // Note about transaction submission
    println!("9. Transaction submission (not executed)...");
    println!("   To submit a transaction, use:");
    println!("   let response = client.submit_transaction(&tx).await?;");
    println!("   println!(\"TX Hash: {{}}\", response.tx_hash);");
    println!();

    // Testnet example
    println!("10. Creating testnet client...");
    let testnet_client = RustChainClient::new(Network::Testnet.rpc_url().to_string());
    println!("   Testnet RPC: {}", Network::Testnet.rpc_url());
    match testnet_client.health_check().await {
        Ok(true) => println!("   ✓ Testnet endpoint is reachable"),
        _ => println!("   Note: Testnet endpoint may be offline"),
    }
    println!();

    println!("=== Example Complete ===");
    println!("\nNote: Some operations may fail if the RPC node is offline.");
    println!("For full functionality, connect to a running RustChain node.");
    
    Ok(())
}
