//! RustChain Address Generator CLI

use rustchain_address::{generate_address, generate_from_mnemonic, generate_from_private_key};
use std::env;

fn main() {
    let args: Vec<String> = env::args().collect();
    
    if args.len() < 2 {
        println!("RustChain Address Generator v0.1.0");
        println!();
        println!("Usage:");
        println!("  rtc-address generate              Generate new address");
        println!("  rtc-address import-mnemonic <mnemonic>  Generate from BIP39 mnemonic");
        println!("  rtc-address import-key <privkey>  Generate from private key hex");
        println!();
        println!("Examples:");
        println!("  rtc-address generate");
        println!("  rtc-address import-mnemonic \"abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about\"");
        println!("  rtc-address import-key 0000000000000000000000000000000000000000000000000000000000000000");
        std::process::exit(1);
    }
    
    match args[1].as_str() {
        "generate" => {
            let (address, keypair) = generate_address();
            let parts: Vec<&str> = keypair.split(':').collect();
            
            println!("Generated RustChain Address");
            println!("===========================");
            println!("Address:     {}", address);
            println!("Private Key: {}", parts[0]);
            println!("Public Key:  {}", parts[1]);
        },
        "import-mnemonic" => {
            if args.len() < 3 {
                eprintln!("Error: Please provide a mnemonic phrase");
                std::process::exit(1);
            }
            
            match generate_from_mnemonic(&args[2]) {
                Ok((address, keypair)) => {
                    println!("Generated from Mnemonic");
                    println!("========================");
                    println!("Address:     {}", address);
                    println!("Private Key: {}", keypair);
                },
                Err(e) => {
                    eprintln!("Error: {}", e);
                    std::process::exit(1);
                }
            }
        },
        "import-key" => {
            if args.len() < 3 {
                eprintln!("Error: Please provide a private key hex");
                std::process::exit(1);
            }
            
            match generate_from_private_key(&args[2]) {
                Ok((address, public_key)) => {
                    println!("Generated from Private Key");
                    println!("===========================");
                    println!("Address:    {}", address);
                    println!("Public Key: {}", public_key);
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
