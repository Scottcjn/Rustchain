//! RustChain Address Validator CLI

use rustchain_address::{address_from_pubkey_hex, validate_address};
use std::env;

fn main() {
    let args: Vec<String> = env::args().collect();
    
    if args.len() < 2 {
        println!("RustChain Address Validator v0.1.0");
        println!();
        println!("Usage:");
        println!("  rtc-validate address <addr>    Validate an address");
        println!("  rtc-validate pubkey <hex>     Generate address from public key hex");
        println!();
        println!("Examples:");
        println!("  rtc-validate address RTC0000000000000000000000000000000000000000");
        println!("  rtc-validate pubkey a1b2c3d4e5f6...");
        std::process::exit(1);
    }
    
    match args[1].as_str() {
        "address" => {
            if args.len() < 3 {
                eprintln!("Error: Please provide an address to validate");
                std::process::exit(1);
            }
            
            let addr = &args[2];
            let is_valid = validate_address(addr);
            
            println!("Address Validation");
            println!("==================");
            println!("Address: {}", addr);
            println!("Valid:   {}", if is_valid { "✓ YES" } else { "✗ NO" });
            
            if !is_valid {
                // Provide hints
                if !addr.starts_with("RTC") {
                    println!("Hint: Address must start with 'RTC'");
                }
                if addr.len() != 43 {
                    println!("Hint: Address must be 43 characters (RTC + 40 hex)");
                }
            }
        },
        "pubkey" => {
            if args.len() < 3 {
                eprintln!("Error: Please provide a public key hex");
                std::process::exit(1);
            }
            
            match address_from_pubkey_hex(&args[2]) {
                Ok(address) => {
                    println!("Public Key to Address");
                    println!("======================");
                    println!("Public Key: {}", args[2]);
                    println!("Address:    {}", address);
                },
                Err(e) => {
                    eprintln!("Error: {}", e);
                    std::process::exit(1);
                }
            }
        },
        _ => {
            eprintln!("Unknown command: {}", args[1]);
            eprintln!("Run without arguments to see usage");
            std::process::exit(1);
        }
    }
}
