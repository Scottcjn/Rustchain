//! # RustChain Core
//!
//! RustChain is a blockchain that implements **Proof of Antiquity (PoA)** -
//! a revolutionary consensus mechanism that rewards the preservation and
//! operation of vintage computing hardware.
//!
//! ## Philosophy
//!
//! > "Every vintage computer has historical potential"
//! > - Flamekeeper Scott
//!
//! Unlike Proof of Work (which wastes energy on meaningless computation) or
//! Proof of Stake (which rewards the wealthy), Proof of Antiquity rewards
//! those who preserve computing history by keeping vintage hardware running.
//!
//! ## Core Principles
//!
//! 1. **Hardware Age Matters**: Older hardware gets higher mining multipliers
//! 2. **Anti-Emulation**: Deep entropy verification ensures real hardware
//! 3. **Economic Rationality**: It's cheaper to buy a $50 486 than to emulate one
//! 4. **Fair Distribution**: No premine, no VC allocation, just mining
//!
//! ## Hardware Tiers
//!
//! | Tier | Age | Multiplier | Examples |
//! |------|-----|------------|----------|
//! | Ancient | 30+ years | 3.5x | Commodore 64, Apple II, 486 |
//! | Sacred | 25-29 years | 3.0x | Pentium, PowerPC 601 |
//! | Vintage | 20-24 years | 2.5x | PowerPC G4, Pentium III |
//! | Classic | 15-19 years | 2.0x | Core 2 Duo, PowerPC G5 |
//! | Retro | 10-14 years | 1.5x | First-gen Core i7 |
//! | Modern | 5-9 years | 1.0x | Skylake, Ryzen |
//! | Recent | 0-4 years | 0.5x | Current hardware (penalized) |
//!
//! ## RIPs (RustChain Improvement Proposals)
//!
//! - **RIP-001**: Core Types - Fundamental blockchain data structures
//! - **RIP-002**: Proof of Antiquity - The consensus mechanism
//! - **RIP-003**: Deep Entropy Verification - Anti-emulation system
//! - **RIP-004**: NFT Badges - Achievement system for miners
//! - **RIP-005**: Network Protocol - P2P communication
//!
//! ## Quick Start
//!
//! ```rust,no_run
//! use rustchain::{HardwareTier, HardwareInfo, WalletAddress};
//!
//! // Create hardware info for a PowerPC G4 (2003, 22 years old)
//! let hardware = HardwareInfo::new(
//!     "PowerPC G4 1.25GHz".to_string(),
//!     "G4".to_string(),
//!     22
//! );
//!
//! // Tier is automatically calculated as Vintage (2.5x)
//! assert_eq!(hardware.tier, HardwareTier::Vintage);
//! assert_eq!(hardware.multiplier, 2.5);
//! ```

#![warn(missing_docs)]
#![warn(rust_2018_idioms)]

// Re-export RIP modules
pub mod core_types;
pub mod proof_of_antiquity;
pub mod deep_entropy;
pub mod nft_badges;
pub mod network;
pub mod governance;
pub mod ergo_bridge;

// Re-export commonly used types
pub use core_types::{
    HardwareTier,
    HardwareInfo,
    HardwareCharacteristics,
    WalletAddress,
    Block,
    BlockHash,
    BlockMiner,
    Transaction,
    TransactionType,
    TxHash,
    TokenAmount,
    MiningProof,
    CacheSizes,
    TOTAL_SUPPLY,
    BLOCK_TIME_SECONDS,
    CHAIN_ID,
};

pub use proof_of_antiquity::{
    ProofOfAntiquity,
    ValidatedProof,
    SubmitResult,
    BlockStatus,
    ProofError,
    BLOCK_REWARD,
};

pub use deep_entropy::{
    DeepEntropyVerifier,
    EntropyProof,
    VerificationResult,
    EntropyScores,
    Challenge,
};

pub use nft_badges::{
    Badge,
    BadgeId,
    BadgeType,
    BadgeTier,
    BadgeMinter,
    BadgeCriteriaChecker,
    MinerStats,
};

pub use network::{
    Message,
    NetworkManager,
    PeerId,
    PeerInfo,
    NodeCapabilities,
    PROTOCOL_VERSION,
    DEFAULT_PORT,
    MTLS_PORT,
};

/// Prelude module for convenient imports
pub mod prelude {
    pub use crate::{
        HardwareTier,
        HardwareInfo,
        WalletAddress,
        Block,
        BlockHash,
        TokenAmount,
        MiningProof,
        ProofOfAntiquity,
        Badge,
        BadgeType,
        TOTAL_SUPPLY,
        CHAIN_ID,
    };
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_vintage_hardware_multiplier() {
        // A 486 DX2 from 1992 (33 years old in 2025)
        let hw = HardwareInfo::new(
            "Intel 486 DX2-66".to_string(),
            "486".to_string(),
            33
        );

        assert_eq!(hw.tier, HardwareTier::Ancient);
        assert_eq!(hw.multiplier, 3.5);
    }

    #[test]
    fn test_modern_hardware_penalty() {
        // Brand new RTX 5090 (0 years old)
        let hw = HardwareInfo::new(
            "NVIDIA RTX 5090".to_string(),
            "Ada".to_string(),
            0
        );

        assert_eq!(hw.tier, HardwareTier::Recent);
        assert_eq!(hw.multiplier, 0.5);
    }

    #[test]
    fn test_proof_of_antiquity_not_proof_of_work() {
        // RustChain rewards vintage hardware, not computational power
        let ancient = HardwareInfo::new("486".to_string(), "x86".to_string(), 35);
        let modern = HardwareInfo::new("Threadripper".to_string(), "Zen4".to_string(), 1);

        // The slow 486 beats the fast Threadripper 7:1
        assert!(ancient.multiplier > modern.multiplier * 6.0);
    }
}
