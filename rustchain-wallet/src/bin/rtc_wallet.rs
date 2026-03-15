//! RustChain Wallet CLI
//!
//! A command-line interface for managing RustChain wallets,
//! signing transactions, and interacting with the network.

use clap::{Parser, Subcommand};
use rustchain_wallet::error::Result;
use rustchain_wallet::{
    KeyPair, Network, RustChainClient, TransactionBuilder, Wallet, WalletStorage,
};
use std::path::PathBuf;
use tracing::{error, warn};
use tracing_subscriber::{fmt, prelude::*, EnvFilter};

/// RustChain Wallet CLI - Manage your RustChain assets
#[derive(Parser)]
#[command(name = "rtc-wallet")]
#[command(author = "RustChain Contributors")]
#[command(version = "0.1.0")]
#[command(about = "A native Rust CLI wallet for RustChain", long_about = None)]
struct Cli {
    /// Network to use (mainnet, testnet, devnet)
    #[arg(short, long, default_value = "mainnet")]
    network: String,

    /// Path to wallet storage directory
    #[arg(short, long)]
    wallet_dir: Option<PathBuf>,

    /// Enable verbose output
    #[arg(short, long)]
    verbose: bool,

    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Create a new wallet with Ed25519 keypair
    Create {
        /// Name for the wallet
        #[arg(short, long)]
        name: String,

        /// Output format (json, text)
        #[arg(short, long, default_value = "text")]
        format: String,
    },

    /// Import wallet from a private key (hex or Base58)
    Import {
        /// Name for the imported wallet
        #[arg(short, long)]
        name: String,

        /// Private key (hex or Base58 encoded)
        #[arg(short, long)]
        key: String,
    },

    /// Send RTC to another address
    Send {
        /// Sender wallet name
        #[arg(short, long)]
        from: String,

        /// Recipient RTC address
        #[arg(short, long)]
        to: String,

        /// Amount to send (in RTC base units)
        #[arg(short, long)]
        amount: u64,

        /// Transaction fee (optional, defaults to 1000)
        #[arg(short, long)]
        fee: Option<u64>,

        /// Optional memo
        #[arg(short, long)]
        memo: Option<String>,

        /// API endpoint override
        #[arg(long)]
        rpc: Option<String>,

        /// Simulate transaction without broadcasting
        #[arg(long)]
        simulate: bool,
    },

    /// Show your wallet address for receiving RTC
    Receive {
        /// Wallet name
        #[arg(short, long)]
        name: String,
    },

    /// Check wallet balance from rustchain.org
    Balance {
        /// Wallet name or RTC address
        #[arg(short, long)]
        wallet: String,

        /// API endpoint override
        #[arg(long)]
        rpc: Option<String>,
    },

    /// List all wallets in storage
    List,

    /// Show wallet details
    Show {
        /// Wallet name
        #[arg(short, long)]
        name: String,
    },

    /// Export wallet private key (use with caution!)
    Export {
        /// Wallet name
        #[arg(short, long)]
        name: String,
    },

    /// Sign a message
    Sign {
        /// Wallet name
        #[arg(short, long)]
        wallet: String,

        /// Message to sign
        #[arg(short, long)]
        message: String,

        /// Output format (hex, base64)
        #[arg(short, long, default_value = "hex")]
        format: String,
    },

    /// Verify a signature
    Verify {
        /// Public key (hex)
        #[arg(short, long)]
        pubkey: String,

        /// Original message
        #[arg(short, long)]
        message: String,

        /// Signature (hex encoded)
        #[arg(short, long)]
        signature: String,
    },

    /// Get network information
    Network {
        /// API endpoint override
        #[arg(long)]
        rpc: Option<String>,
    },

    /// Delete a wallet from storage
    Delete {
        /// Wallet name
        #[arg(short, long)]
        name: String,

        /// Skip confirmation prompt
        #[arg(long)]
        yes: bool,
    },
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let cli = Cli::parse();

    // Initialize logging
    let filter = if cli.verbose { "debug" } else { "info" };

    tracing_subscriber::registry()
        .with(fmt::layer())
        .with(EnvFilter::new(filter))
        .init();

    // Determine network
    let network = match cli.network.to_lowercase().as_str() {
        "mainnet" => Network::Mainnet,
        "testnet" => Network::Testnet,
        "devnet" => Network::Devnet,
        _ => {
            error!(
                "Invalid network: {}. Use mainnet, testnet, or devnet",
                cli.network
            );
            std::process::exit(1);
        }
    };

    // Get wallet storage
    let storage = if let Some(dir) = cli.wallet_dir {
        WalletStorage::new(dir)?
    } else {
        WalletStorage::default()?
    };

    // Execute command
    match cli.command {
        Commands::Create { name, format } => {
            cmd_create(&storage, &name, &format, network)?;
        }
        Commands::Import { name, key } => {
            cmd_import(&storage, &name, &key)?;
        }
        Commands::Send {
            from,
            to,
            amount,
            fee,
            memo,
            rpc,
            simulate,
        } => {
            cmd_send(
                &storage,
                &from,
                &to,
                amount,
                fee,
                memo.as_deref(),
                rpc.as_deref().unwrap_or(network.api_url()),
                simulate,
            )
            .await?;
        }
        Commands::Receive { name } => {
            cmd_receive(&storage, &name)?;
        }
        Commands::Balance { wallet, rpc } => {
            cmd_balance(&storage, &wallet, rpc.as_deref().unwrap_or(network.api_url())).await?;
        }
        Commands::List => {
            cmd_list(&storage)?;
        }
        Commands::Show { name } => {
            cmd_show(&storage, &name)?;
        }
        Commands::Export { name } => {
            cmd_export(&storage, &name)?;
        }
        Commands::Sign {
            wallet,
            message,
            format,
        } => {
            cmd_sign(&storage, &wallet, &message, &format)?;
        }
        Commands::Verify {
            pubkey,
            message,
            signature,
        } => {
            cmd_verify(&pubkey, &message, &signature)?;
        }
        Commands::Network { rpc } => {
            cmd_network(rpc.as_deref().unwrap_or(network.api_url())).await?;
        }
        Commands::Delete { name, yes } => {
            cmd_delete(&storage, &name, yes)?;
        }
    }

    Ok(())
}

fn cmd_create(storage: &WalletStorage, name: &str, format: &str, network: Network) -> Result<()> {
    if storage.exists(name) {
        error!("Wallet '{}' already exists", name);
        std::process::exit(1);
    }

    // Generate new wallet
    let wallet = Wallet::with_network(KeyPair::generate(), network);
    let address = wallet.address();

    // Prompt for password
    let password =
        rpassword::prompt_password("Enter password to encrypt wallet: ").unwrap_or_else(|_| {
            warn!("Could not read password, wallet will not be encrypted");
            String::new()
        });

    let confirm =
        rpassword::prompt_password("Confirm password: ").unwrap_or_else(|_| String::new());

    if password != confirm {
        error!("Passwords do not match");
        std::process::exit(1);
    }

    // Save wallet
    let path = storage.save(name, wallet.keypair(), &password)?;

    match format {
        "json" => {
            println!(
                "{}",
                serde_json::json!({
                    "name": name,
                    "address": address,
                    "public_key": wallet.public_key(),
                    "network": network.to_string(),
                    "storage_path": path.display().to_string()
                })
            );
        }
        _ => {
            println!("Wallet created successfully!");
            println!();
            println!("Name:         {}", name);
            println!("Address:      {}", address);
            println!("Public Key:   {}", wallet.public_key());
            println!("Network:      {}", network);
            println!("Storage:      {}", path.display());
            println!();
            println!("IMPORTANT: Store your password securely. It cannot be recovered!");
        }
    }

    Ok(())
}

fn cmd_import(storage: &WalletStorage, name: &str, key: &str) -> Result<()> {
    if storage.exists(name) {
        error!("Wallet '{}' already exists", name);
        std::process::exit(1);
    }

    // Try to parse key (hex first, then base58)
    let keypair = if key.len() == 64 && key.chars().all(|c| c.is_ascii_hexdigit()) {
        KeyPair::from_hex(key)?
    } else {
        KeyPair::from_base58(key)?
    };

    let address = keypair.rtc_address();

    // Prompt for password
    let password = rpassword::prompt_password("Enter password to encrypt wallet: ")
        .unwrap_or_else(|_| String::new());

    let confirm =
        rpassword::prompt_password("Confirm password: ").unwrap_or_else(|_| String::new());

    if password != confirm {
        error!("Passwords do not match");
        std::process::exit(1);
    }

    storage.save(name, &keypair, &password)?;

    println!("Wallet imported successfully!");
    println!();
    println!("Name:     {}", name);
    println!("Address:  {}", address);

    Ok(())
}

#[allow(clippy::too_many_arguments)]
async fn cmd_send(
    storage: &WalletStorage,
    from: &str,
    to: &str,
    amount: u64,
    fee: Option<u64>,
    memo: Option<&str>,
    api_url: &str,
    simulate: bool,
) -> Result<()> {
    if !storage.exists(from) {
        error!("Wallet '{}' not found", from);
        std::process::exit(1);
    }

    let password =
        rpassword::prompt_password("Enter wallet password: ").unwrap_or_else(|_| String::new());

    let keypair = storage.load(from, &password)?;
    let from_address = keypair.rtc_address();

    let client = RustChainClient::new(api_url.to_string());

    // Get current nonce
    let nonce = client.get_nonce(&from_address).await.unwrap_or(0);

    // Calculate fee
    let fee = fee.unwrap_or(1000);

    // Create transaction
    let mut tx = TransactionBuilder::new()
        .from(from_address.clone())
        .to(to.to_string())
        .amount(amount)
        .fee(fee)
        .nonce(nonce)
        .build()?;

    if let Some(m) = memo {
        tx = tx.with_memo(m.to_string());
    }

    // Sign transaction
    tx.sign(&keypair)?;

    if simulate {
        println!("Simulated transaction:");
        println!("{}", tx.to_json()?);
        println!();
        println!("Transaction simulation successful");
        return Ok(());
    }

    // Submit transaction
    match client.submit_transaction(&tx).await {
        Ok(response) => {
            println!("Transaction submitted successfully!");
            println!();
            println!("TX Hash: {}", response.tx_hash);
            println!("Status:  {}", response.status);
            if let Some(block) = response.block_height {
                println!("Block:   {}", block);
            }
        }
        Err(e) => {
            error!("Failed to submit transaction: {}", e);
            std::process::exit(1);
        }
    }

    Ok(())
}

fn cmd_receive(storage: &WalletStorage, name: &str) -> Result<()> {
    if !storage.exists(name) {
        error!("Wallet '{}' not found", name);
        std::process::exit(1);
    }

    let password =
        rpassword::prompt_password("Enter wallet password: ").unwrap_or_else(|_| String::new());

    let keypair = storage.load(name, &password)?;
    let address = keypair.rtc_address();

    println!("Receive RTC at this address:");
    println!();
    println!("  {}", address);
    println!();
    println!("Share this address with the sender.");
    println!("Public Key: {}", keypair.public_key_hex());

    Ok(())
}

async fn cmd_balance(storage: &WalletStorage, wallet_or_address: &str, api_url: &str) -> Result<()> {
    let client = RustChainClient::new(api_url.to_string());

    // If it starts with RTC, treat as address; otherwise look up wallet name
    let address = if wallet_or_address.starts_with("RTC") {
        wallet_or_address.to_string()
    } else if storage.exists(wallet_or_address) {
        let password = rpassword::prompt_password("Enter wallet password: ")
            .unwrap_or_else(|_| String::new());
        let keypair = storage.load(wallet_or_address, &password)?;
        keypair.rtc_address()
    } else {
        // Treat as raw address
        wallet_or_address.to_string()
    };

    match client.get_balance(&address).await {
        Ok(balance) => {
            println!("Balance for: {}", address);
            println!("  Total:     {:.4} RTC", balance.balance);
            if balance.unlocked > 0.0 || balance.locked > 0.0 {
                println!("  Unlocked:  {:.4} RTC", balance.unlocked);
                println!("  Locked:    {:.4} RTC", balance.locked);
            }
            println!("  Nonce:     {}", balance.nonce);
        }
        Err(e) => {
            error!("Failed to get balance: {}", e);
            std::process::exit(1);
        }
    }

    Ok(())
}

fn cmd_list(storage: &WalletStorage) -> Result<()> {
    let wallets = storage.list()?;

    if wallets.is_empty() {
        println!("No wallets found in storage.");
        println!("Use 'rtc-wallet create --name <name>' to create a new wallet.");
        return Ok(());
    }

    println!("Stored wallets:");
    println!();
    for name in &wallets {
        println!("  - {}", name);
    }
    println!();
    println!("Total: {} wallet(s)", wallets.len());

    Ok(())
}

fn cmd_show(storage: &WalletStorage, name: &str) -> Result<()> {
    if !storage.exists(name) {
        error!("Wallet '{}' not found", name);
        std::process::exit(1);
    }

    let password =
        rpassword::prompt_password("Enter wallet password: ").unwrap_or_else(|_| String::new());

    let keypair = storage.load(name, &password)?;
    let address = keypair.rtc_address();

    println!("Wallet: {}", name);
    println!("Address:    {}", address);
    println!("Public Key: {}", keypair.public_key_hex());

    Ok(())
}

fn cmd_export(storage: &WalletStorage, name: &str) -> Result<()> {
    if !storage.exists(name) {
        error!("Wallet '{}' not found", name);
        std::process::exit(1);
    }

    warn!("WARNING: You are about to export your private key!");
    warn!("Never share your private key with anyone!");
    println!();

    let confirm =
        rpassword::prompt_password("Type 'YES' to confirm: ").unwrap_or_else(|_| String::new());

    if confirm != "YES" {
        println!("Export cancelled.");
        return Ok(());
    }

    let password =
        rpassword::prompt_password("Enter wallet password: ").unwrap_or_else(|_| String::new());

    let keypair = storage.load(name, &password)?;
    let private_key = keypair.export_private_key();

    println!();
    println!("Private Key (hex):");
    println!("{}", private_key);
    println!();
    warn!("Store this key securely and delete it from your terminal history!");

    Ok(())
}

fn cmd_sign(storage: &WalletStorage, wallet: &str, message: &str, format: &str) -> Result<()> {
    if !storage.exists(wallet) {
        error!("Wallet '{}' not found", wallet);
        std::process::exit(1);
    }

    let password =
        rpassword::prompt_password("Enter wallet password: ").unwrap_or_else(|_| String::new());

    let keypair = storage.load(wallet, &password)?;
    let signature = keypair.sign(message.as_bytes())?;

    match format {
        "base64" => {
            use base64::Engine;
            println!(
                "{}",
                base64::engine::general_purpose::STANDARD.encode(&signature)
            );
        }
        _ => {
            println!("{}", hex::encode(&signature));
        }
    }

    Ok(())
}

fn cmd_verify(pubkey: &str, message: &str, signature: &str) -> Result<()> {
    // Parse public key from hex
    let keypair = KeyPair::from_hex(pubkey)?;

    // Parse signature
    let sig_bytes = hex::decode(signature)
        .map_err(|e| rustchain_wallet::WalletError::InvalidSignature(e.to_string()))?;

    let valid = keypair.verify(message.as_bytes(), &sig_bytes)?;

    if valid {
        println!("Signature is VALID");
        println!("  Public Key: {}", pubkey);
        println!("  Message:    {}", message);
    } else {
        error!("Signature is INVALID");
        std::process::exit(1);
    }

    Ok(())
}

async fn cmd_network(api_url: &str) -> Result<()> {
    let client = RustChainClient::new(api_url.to_string());

    match client.get_network_info().await {
        Ok(info) => {
            println!("Network Information:");
            println!("  Chain ID:      {}", info.chain_id);
            println!("  Network:       {}", info.network);
            println!("  Block Height:  {}", info.block_height);
            println!("  Peers:         {}", info.peer_count);
            println!("  Min Fee:       {} RTC", info.min_fee);
            println!("  Version:       {}", info.version);
        }
        Err(e) => {
            error!("Failed to get network info: {}", e);
            std::process::exit(1);
        }
    }

    Ok(())
}

fn cmd_delete(storage: &WalletStorage, name: &str, yes: bool) -> Result<()> {
    if !storage.exists(name) {
        error!("Wallet '{}' not found", name);
        std::process::exit(1);
    }

    if !yes {
        warn!("WARNING: This will permanently delete wallet '{}'!", name);
        warn!("This action cannot be undone!");
        println!();

        let confirm = rpassword::prompt_password("Type 'DELETE' to confirm: ")
            .unwrap_or_else(|_| String::new());

        if confirm != "DELETE" {
            println!("Deletion cancelled.");
            return Ok(());
        }
    }

    storage.delete(name)?;
    println!("Wallet '{}' deleted successfully", name);

    Ok(())
}
