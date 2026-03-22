//! Simple Merkle tree implementation minimal dependency

use sha2::{Sha256, Digest};

/// Simple Merkle tree for compact witness proofs
pub struct MerkleTree {
    hashes: Vec<[u8; 32]>,
}

impl MerkleTree {
    pub fn new(items: &[impl AsRef<[u8]>]) -> Self {
        let mut hashes = Vec::with_capacity(items.len());
        for item in items {
            let mut hasher = Sha256::new();
            hasher.update(item.as_ref());
            hashes.push(hasher.finalize().into());
        }

        if hashes.is_empty() {
            return MerkleTree { hashes: Vec::new() };
        }

        // Build the tree
        let mut level = hashes.clone();
        while level.len() > 1 {
            let mut next_level = Vec::new();
            for chunk in level.chunks(2) {
                let mut hasher = Sha256::new();
                match chunk {
                    [a, b] => {
                        hasher.update(a);
                        hasher.update(b);
                    }
                    [a] => {
                        hasher.update(a);
                        hasher.update(a);
                    }
                    _ => {
                        // empty chunk, skip
                        continue;
                    }
                }
                next_level.push(hasher.finalize().into());
            }
            level = next_level;
        }

        hashes = level;
        MerkleTree { hashes }
    }

    pub fn root_hash(&self) -> Option<[u8; 32]> {
        self.hashes.first().copied()
    }
}
