use sha2::{Sha256, Digest};
use wasm_bindgen::prelude::*;

/// Proof-of-Antiquity hashing core
/// Compatible with wasm32-unknown-unknown, x86_64, aarch64, riscv64
#[wasm_bindgen]
pub fn compute_hash(input: &str, nonce: u64) -> String {
    let mut hasher = Sha256::new();
    hasher.update(input.as_bytes());
    hasher.update(&nonce.to_le_bytes());
    let result = hasher.finalize();
    hex::encode(result)
}

#[wasm_bindgen]
pub fn mine_chunk(data: &str, start_nonce: u64, chunk_size: u64, target_difficulty: u64) -> Option<u64> {
    let target = u64::MAX / target_difficulty.max(1);
    for i in 0..chunk_size {
        let nonce = start_nonce.wrapping_add(i);
        let hash = compute_hash(data, nonce);
        // Simplified difficulty check: first N bytes must be zero
        if hash.starts_with(&"0".repeat((target_difficulty as usize).min(8))) {
            return Some(nonce);
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn test_hash_deterministic() {
        let h1 = compute_hash("test", 1);
        let h2 = compute_hash("test", 1);
        assert_eq!(h1, h2);
    }
}
