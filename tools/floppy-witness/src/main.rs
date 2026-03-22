mod cli;
mod merkle;

use std::io::{self, Read, Write};
use base64;
use sha2::{Sha256, Digest};

pub use merkle::MerkleTree;

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct EpochWitness {
    pub epoch_number: u64,
    pub timestamp: u64,
    pub miners: Vec<MinerEntry>,
    pub settlement_hash: [u8; 32],
    pub ergo_anchor_txid: String,
    pub commitment_hash: [u8; 32],
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct MinerEntry {
    pub miner_id: String,
    pub architecture: String,
    pub antiquity_multiplier: f32,
}

impl EpochWitness {
    /// Compute the commitment hash for this witness
    pub fn compute_commitment(&self) -> [u8; 32] {
        let mut hasher = Sha256::new();
        hasher.update(&self.epoch_number.to_be_bytes());
        hasher.update(&self.timestamp.to_be_bytes());
        for miner in &self.miners {
            hasher.update(miner.miner_id.as_bytes());
            hasher.update(miner.architecture.as_bytes());
        }
        hasher.update(self.settlement_hash);
        hasher.update(self.ergo_anchor_txid.as_bytes());
        // commitment_hash is what we're calculating, don't include it in the hash
        hasher.finalize().into()
    }

    /// Calculate approximate size in bytes after serialization
    pub fn estimated_size(&self) -> usize {
        // bincode size estimate ~ 8 + 8 + sum (miner (len + arch) + 32 + 32 + len(txid)
        let base_size = 8 + 8 + 32 + 32 + self.ergo_anchor_txid.len() + 32;
        let miner_size: usize = self.miners.iter()
            .map(|m| m.miner_id.len() + m.architecture.len() + 4) // 4 bytes for multiplier
            .sum();
        base_size + miner_size
    }
}

/// Write witness to output device/file
pub fn write_witness<W: Write>(
    witness: &EpochWitness,
    output: &mut W,
) -> io::Result<()> {
    let encoded = bincode::serialize(witness)
        .map_err(|e| io::Error::new(io::ErrorKind::Other, e))?;
    output.write_all(&encoded)?;
    Ok(())
}

/// Read witness from input device/file
pub fn read_witness<R: Read>(
    input: &mut R,
) -> io::Result<EpochWitness> {
    let witness: EpochWitness = bincode::deserialize_from(input)
        .map_err(|e| io::Error::new(io::ErrorKind::Other, e))?;
    Ok(witness)
}

/// Verify witness locally (check internal commitment hash)
/// For full node verification, you would add HTTP client externally
pub fn verify_witness_local(
    witness: &EpochWitness,
) -> bool {
    let computed = witness.compute_commitment();
    computed == witness.commitment_hash
}

/// Generate base64 for QR code rendering (for printing on floppy label)
pub fn generate_qr(witness: &EpochWitness) -> Result<String, Box<dyn std::error::Error>> {
    let encoded = bincode::serialize(witness)?;
    let base64_encoded = base64::encode(&encoded);
    Ok(base64_encoded)
}

/// Calculate how many epochs can fit on a 1.44MB floppy
/// Subtract ~2KB for boot sector, FAT has already allocated space
pub fn calculate_capacity(avg_epoch_size: usize) -> usize {
    const FLOPPY_TOTAL: usize = 1_440 * 1024;
    const OVERHEAD: usize = 2 * 1024;
    let available = FLOPPY_TOTAL - OVERHEAD;
    available / avg_epoch_size
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_serialize_deserialize() {
        let witness = EpochWitness {
            epoch_number: 1234,
            timestamp: 1680000000,
            miners: vec![
                MinerEntry {
                    miner_id: "test-miner-1".to_string(),
                    architecture: "PowerBook G4".to_string(),
                    antiquity_multiplier: 2.5,
                }
            ],
            settlement_hash: [0u8; 32],
            ergo_anchor_txid: "abc123".to_string(),
            commitment_hash: [1u8; 32],
        };

        let mut buf = Vec::new();
        write_witness(&witness, &mut buf).unwrap();
        assert!(buf.len() > 0);

        let read_back = read_witness(&mut buf.as_slice()).unwrap();
        assert_eq!(read_back.epoch_number, 1234);
        assert_eq!(read_back.miners.len(), 1);
    }

    #[test]
    fn test_capacity_calculation() {
        let avg_size = 100;
        let capacity = calculate_capacity(avg_size);
        assert_eq!(capacity, (1440 * 1024 - 2*1024) / 100);
        assert!(capacity >= 14000);
    }

    #[test]
    fn test_14mb_fit() {
        // Should fit ~14,000 epochs with average 100bytes each
        let avg_size = 100;
        let capacity = calculate_capacity(avg_size);
        println!("Average size {} bytes → capacity: {} epochs on 1.44MB floppy", avg_size, capacity);
        assert!(capacity >= 14000);
    }

    #[test]
    fn test_local_verify() {
        let mut witness = EpochWitness {
            epoch_number: 123,
            timestamp: 1234,
            miners: vec![],
            settlement_hash: [0u8; 32],
            ergo_anchor_txid: "".to_string(),
            commitment_hash: [0u8; 32],
        };
        let commitment = witness.compute_commitment();
        witness.commitment_hash = commitment;
        assert!(verify_witness_local(&witness));
    }
}

fn main() {
    cli::main();
}
