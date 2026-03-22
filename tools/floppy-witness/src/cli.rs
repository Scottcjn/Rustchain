//! CLI interface for floppy-witness

use clap::{Parser, Subcommand};
use crate::{
    calculate_capacity,
    generate_qr,
    read_witness,
    verify_witness_local,
    write_witness,
    EpochWitness,
};
use std::fs::{self, OpenOptions};
use std::io;
use std::path::Path;

#[derive(Parser)]
#[clap(author, version, about, long_about = None)]
pub struct Cli {
    #[clap(subcommand)]
    pub command: Commands,
}

#[derive(Subcommand)]
pub enum Commands {
    /// Write epoch witness to output device/file
    Write {
        /// Epoch number to witness
        #[clap(short, long)]
        epoch: u64,

        /// Output device/file path
        #[clap(short, long)]
        device: String,
    },

    /// Read epoch witness from input device/file
    Read {
        /// Input device/file path
        #[clap(short, long)]
        device: String,
    },

    /// Verify witness commitment (local check)
    Verify {
        /// Witness file path
        #[clap(short, long)]
        witness: String,
    },

    /// Calculate how many epochs can fit on a 1.44MB floppy
    Capacity {
        /// Average epoch size in bytes
        #[clap(short, long, default_value_t = 100)]
        avg_size: usize,
    },

    /// Generate base64 for QR code (for printing on label)
    Qr {
        /// Witness file path
        #[clap(short, long)]
        witness: String,
    },
}

pub fn main() -> io::Result<()> {
    let cli = Cli::parse();

    match cli.command {
        Commands::Write { epoch, device } => {
            eprintln!("Creating new witness for epoch {}", epoch);

            // In real usage, fetch data from node, here we create skeleton
            let witness = EpochWitness {
                epoch_number: epoch,
                timestamp: std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap()
                    .as_secs(),
                miners: Vec::new(),
                settlement_hash: [0u8; 32],
                ergo_anchor_txid: String::new(),
                commitment_hash: [0u8; 32],
            };

            // Compute proper commitment
            let commitment = witness.compute_commitment();
            let mut witness = witness;
            witness.commitment_hash = commitment;

            let path = Path::new(&device);
            let mut file = OpenOptions::new()
                .write(true)
                .create(true)
                .open(path)?;

            write_witness(&witness, &mut file)?;

            let metadata = file.metadata()?;
            eprintln!("Wrote witness ({} bytes) to {}", metadata.len(), device);

            Ok(())
        }

        Commands::Read { device } => {
            let path = Path::new(&device);
            let mut file = fs::File::open(path)?;
            let witness = read_witness(&mut file)?;

            println!("Witness read successfully:");
            println!("  Epoch: {}", witness.epoch_number);
            println!("  Timestamp: {}", witness.timestamp);
            println!("  Number of miners: {}", witness.miners.len());
            println!("  Ergo anchor TX: {}", witness.ergo_anchor_txid);
            println!("  Local commitment check: {}", if verify_witness_local(&witness) { "✅ OK" } else { "❌ FAIL" });

            Ok(())
        }

        Commands::Verify { witness } => {
            let path = Path::new(&witness);
            let mut file = fs::File::open(path)?;
            let witness = read_witness(&mut file)?;

            let result = verify_witness_local(&witness);

            if result {
                println!("✅ Local verification passed! Commitment hash is valid.");
                println!("  Note: For full on-chain verification, compare with RustChain node API.");
            } else {
                println!("❌ Verification failed! Commitment hash mismatch.");
            }

            Ok(())
        }

        Commands::Capacity { avg_size } => {
            let capacity = calculate_capacity(avg_size);
            println!("📊 Capacity calculation:");
            println!("  Average epoch size: {} bytes", avg_size);
            println!("  Estimated number of epochs on 1.44MB floppy: {}", capacity);
            println!("  Target: ~14,000 → we fit {} → {}", capacity, if capacity >= 14000 { "✅ OK" } else { "⚠️  Under target" });

            Ok(())
        }

        Commands::Qr { witness } => {
            let path = Path::new(&witness);
            let mut file = fs::File::open(path)?;
            let witness = read_witness(&mut file)?;

            let qr_b64 = generate_qr(&witness)
                .map_err(|e| io::Error::new(io::ErrorKind::Other, e.to_string()))?;
            println!("QR code base64 (render this to image for printing on floppy label):");
            println!("{}", qr_b64);

            Ok(())
        }
    }
}
