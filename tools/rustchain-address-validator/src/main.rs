//! RTC Address Tool - CLI for RustChain address operations
//! 
//! A command-line tool for generating and validating RTC addresses.

use clap::{Parser, Subcommand};
use rustchain_address::{
    address_from_private_key, generate_address, validate_address,
};

#[derive(Parser)]
#[command(name = "rtc-address")]
#[command(about = "RustChain Address Generator and Validator", long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Generate a new random RTC address
    Generate,
    /// Validate an RTC address
    Validate {
        /// The RTC address to validate
        address: String,
    },
    /// Derive address from private key
    FromKey {
        /// Private key in hex format
        private_key: String,
    },
}

fn main() {
    let cli = Cli::parse();

    match cli.command {
        Commands::Generate => {
            let (address, private_key) = generate_address();
            println!("\n=== Generated RTC Address ===\n");
            println!("Address:     {}", address);
            println!("Private Key: {}\n", private_key);
            println!("IMPORTANT: Save your private key securely!");
            println!("    Anyone with your private key can access your funds.\n");
        }
        Commands::Validate { address } => {
            if validate_address(&address) {
                println!("Valid RTC address: {}", address);
            } else {
                println!("Invalid RTC address: {}", address);
                std::process::exit(1);
            }
        }
        Commands::FromKey { private_key } => {
            match address_from_private_key(&private_key) {
                Ok(address) => {
                    println!("\n=== Derived RTC Address ===\n");
                    println!("Address: {}\n", address);
                }
                Err(e) => {
                    println!("Error: {}", e);
                    std::process::exit(1);
                }
            }
        }
    }
}
