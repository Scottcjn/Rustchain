# RustChain Core - Implementation Documentation

## Overview

This document provides comprehensive documentation for the RustChain Core implementation, a blockchain that implements **Proof of Antiquity (PoA)** - a revolutionary consensus mechanism that rewards the preservation and operation of vintage computing hardware.

## Repository Structure

```
rips/
├── Cargo.toml                 # Rust package manifest
├── src/
│   ├── lib.rs                 # Library root with module exports
│   ├── core_types.rs          # RIP-001: Fundamental data structures
│   ├── proof_of_antiquity.rs  # RIP-002: PoA consensus mechanism
│   ├── deep_entropy.rs        # RIP-003: Multi-layer entropy verification
│   ├── nft_badges.rs          # RIP-004: Achievement badge system
│   ├── network.rs             # RIP-005: P2P network protocol
│   ├── governance.rs          # RIP-006: Governance system
│   ├── ergo_bridge.rs         # Ergo blockchain compatibility layer
│   └── bin/
│       ├── node.rs            # Full node implementation
│       └── miner.rs           # Mining client
├── benches/
│   └── entropy_bench.rs       # Performance benchmarks
└── python/
    └── rustchain/
        └── deep_entropy.py    # Python reference implementation
```

## Core Modules

### 1. Core Types (RIP-001)

**File**: `src/core_types.rs`

Defines fundamental blockchain data structures:

- **HardwareTier**: Age-based hardware classification with multipliers
  - Ancient (30+ years): 3.5x
  - Sacred (25-29 years): 3.0x
  - Vintage (20-24 years): 2.5x
  - Classic (15-19 years): 2.0x
  - Retro (10-14 years): 1.5x
  - Modern (5-9 years): 1.0x
  - Recent (0-4 years): 0.5x

- **HardwareInfo**: Mining hardware description
- **WalletAddress**: RTC-prefixed wallet addresses
- **Block**: Blockchain block structure
- **Transaction**: Token transfers and mining rewards
- **MiningProof**: Miner's proof submission

**Key Constants**:
```rust
pub const TOTAL_SUPPLY: u64 = 8_388_608;  // 2^23 RTC
pub const BLOCK_TIME_SECONDS: u64 = 120;   // 2 minutes
pub const CHAIN_ID: u64 = 2718;            // RustChain mainnet
```

### 2. Proof of Antiquity (RIP-002)

**File**: `src/proof_of_antiquity.rs`

Implements the PoA consensus mechanism:

- **ProofOfAntiquity**: Main consensus validator
- **ValidatedProof**: Verified mining proof
- **AntiEmulationVerifier**: Hardware authenticity checker

**Block Window**: 120 seconds to collect mining proofs
**Max Miners per Block**: 100
**Block Reward**: 1.0 RTC (split proportionally by multiplier)

**Example Usage**:
```rust
let mut poa = ProofOfAntiquity::new();
let proof = MiningProof {
    wallet: WalletAddress::new("RTC1..."),
    hardware: HardwareInfo::new("486".to_string(), "x86".to_string(), 33),
    anti_emulation_hash: [0u8; 32],
    timestamp: current_timestamp(),
    nonce: 12345,
};
let result = poa.submit_proof(proof)?;
```

### 3. Deep Entropy Verification (RIP-003)

**File**: `src/deep_entropy.rs` ⭐ **NEW**

Multi-layer entropy verification that makes emulation economically irrational:

**Five Entropy Layers**:
1. **Instruction Timing**: CPU-specific timing patterns
2. **Memory Access Patterns**: Cache/DRAM behavior signatures
3. **Bus Timing**: ISA/PCI/PCIe timing characteristics
4. **Thermal Entropy**: Clock stability, DVFS detection
5. **Architectural Quirks**: Known hardware bugs/features

**Hardware Profiles**:
- 486DX2 (1992) - Emulation difficulty: 0.95
- Pentium (1994) - Emulation difficulty: 0.90
- Pentium II (1997) - Emulation difficulty: 0.85
- PowerPC G4 (1999) - Emulation difficulty: 0.85
- PowerPC G5 (2003) - Emulation difficulty: 0.80
- DEC Alpha (1998) - Emulation difficulty: 0.95

**Economic Analysis**:
```rust
let analysis = emulation_cost_analysis("486DX2");
// emulation_cost_usd: $72.50
// real_hardware_cost_usd: $50.00
// recommendation: "BUY REAL HARDWARE"
```

**Key Functions**:
- `DeepEntropyVerifier::generate_challenge()`: Create hardware challenge
- `DeepEntropyVerifier::verify()`: Verify entropy proof
- `emulation_cost_analysis()`: Economic comparison

### 4. NFT Badges (RIP-004)

**File**: `src/nft_badges.rs`

Achievement system for miners:

**Badge Tiers**:
- Legendary (5 stars): Genesis, First Block, Flamekeeper
- Epic (4 stars): Ancient Silicon, Block Legion, Year of Antiquity
- Rare (3 stars): Sacred Silicon, Block Centurion, Developer
- Uncommon (2 stars): Community Builder, Bug Hunter
- Common (1 star): Event Participant

**Architecture-Specific Badges**:
- PowerPC Pioneer
- Alpha Dreamer
- Sun Worshipper (SPARC)
- MIPS Master
- ARMed & Dangerous
- Motorolan (68k)

**BadgeMinter**: Prevents duplicate mints, processes miner stats

### 5. Network Protocol (RIP-005)

**File**: `src/network.rs`

P2P network communication:

**Message Types**:
- Handshake: Hello, HelloAck, Ping, Pong
- Chain Sync: GetBlocks, Blocks, ChainInfo
- Transactions: NewTransaction, GetPendingTransactions
- Mining: NewMiningProof, MiningStatus, NewBlock
- Discovery: GetPeers, Peers, AnnouncePeer
- Vintage Attestation: VintageChallenge, VintageAttestation

**Ports**:
- DEFAULT_PORT: 8085
- MTLS_PORT: 4443 (vintage hardware)

**NetworkManager**: Peer management, reputation system, message routing

### 6. Governance (RIP-006)

**File**: `src/governance.rs`

Hybrid human + Sophia AI governance:

**Proposal Types**:
- ParameterChange
- MonetaryPolicy
- ProtocolUpgrade
- ValidatorChange
- SmartContract
- Community

**Sophia AI Decisions**:
- Endorse: Boosts support probability
- Veto: Locks proposal
- Analyze: Neutral analysis

**Voting**:
- Token-weighted + reputation bonus (up to 20%)
- Quorum: 33%
- Approval threshold: 50%
- Voting period: 7 days

**Delegation**: Time-bound voting power delegation

### 7. Ergo Bridge

**File**: `src/ergo_bridge.rs`

Ergo blockchain compatibility:

**Features**:
- UTXO model compatibility
- Sigma protocol primitives
- ErgoScript contract templates
- Cross-chain asset mapping

**Contract Templates**:
- Mining reward distribution
- Governance voting
- NFT badge minting
- Time-locked releases
- Cross-chain bridge

## Binaries

### rustchain-node

**File**: `src/bin/node.rs`

Full node implementation:

```bash
cargo run --bin rustchain-node --features network
```

**Features**:
- Block validation
- P2P networking
- Historical data serving
- Mining proof collection
- RPC API (optional)

**Configuration**:
```rust
NodeConfig {
    wallet: WalletAddress,
    port: 8085,
    data_dir: "./rustchain_data",
    enable_mining: false,
    enable_rpc: true,
    rpc_port: 8086,
    seed_nodes: vec![],
}
```

### rustchain-miner

**File**: `src/bin/miner.rs`

Mining client for vintage hardware:

```bash
cargo run --bin rustchain-miner
```

**Features**:
- Hardware detection
- Deep entropy verification
- Automatic proof submission
- Reward tracking

**Example Configuration**:
```rust
MinerConfig {
    wallet: WalletAddress::new("RTC1MinerG4..."),
    node_url: "http://localhost:8085",
    hardware_model: "PowerPC G4 1.25GHz",
    hardware_generation: "G4",
    hardware_age_years: Some(22),
    enable_deep_entropy: true,
    mining_interval_secs: 10,
}
```

## Compilation

### Standard Build

```bash
cd rips
cargo build
```

### Release Build (Optimized)

```bash
cargo build --release
```

### Vintage Hardware Compilation

For PowerPC G4:
```bash
RUSTFLAGS="-C target-cpu=g4" cargo build --release --target powerpc-apple-darwin
```

For 486:
```bash
# Requires custom target specification
RUSTFLAGS="-C target-cpu=pentium" cargo build --release
```

## Testing

### Run All Tests

```bash
cargo test
```

### Run Specific Test

```bash
cargo test deep_entropy::tests::test_emulation_cost_analysis
```

### Run Benchmarks

```bash
cargo bench
```

### Test Coverage

```bash
cargo tarpaulin --out Html
```

## Test Results

All 36 tests pass:

```
test result: ok. 32 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out

Running unittests src/bin/miner.rs
test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out

Doc-tests rustchain
test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out
```

## Key Design Decisions

### 1. Tuple Structs for Type Safety

`WalletAddress`, `BlockHash`, and `TxHash` use tuple structs to prevent mixing different hash types:

```rust
pub struct WalletAddress(pub String);
pub struct BlockHash(pub [u8; 32]);
```

### 2. Serialization-Ready Types

All types implement `Serialize` and `Deserialize` for JSON/RPC compatibility.

### 3. Fixed-Size Arrays vs Vectors

For serialization compatibility with serde, we use `Vec<u8>` instead of `[u8; N]` for arrays larger than 32 bytes.

### 4. Economic Irrationality

Deep entropy verification is designed to make emulation cost more than buying real hardware:

- GPU emulation cost: $50-100
- Real 486 cost: $30-80
- Breakeven: < 1 day of mining

### 5. Multiplier Capping

Multipliers are capped at 3.5x (Ancient tier) to prevent inflation while still rewarding oldest hardware.

## Integration Points

### With Existing RustChain Architecture

1. **Data Paths**: All modules use consistent `WalletAddress` and `BlockHash` types
2. **Consensus**: PoA integrates with block assembly via `ProofOfAntiquity::process_block()`
3. **Network**: Messages use standardized `Message` enum with versioning
4. **Governance**: Sophia AI evaluation integrates with proposal lifecycle

### External Integrations

1. **Ergo Bridge**: UTXO compatibility for cross-chain operations
2. **mTLS**: Vintage hardware attestation on port 4443
3. **RPC API**: REST endpoints for wallet/transaction management

## Performance Characteristics

### Benchmark Results

```
entropy_challenge_generation: ~50μs
timing_stats_collection (1000 samples): ~100μs
hardware_profile_lookup: ~10ns
emulation_cost_analysis: ~5μs
```

### Memory Usage

- Core library: ~2MB
- Full node: ~50MB (with blockchain data)
- Miner: ~10MB

## Security Considerations

1. **Anti-Emulation**: Multi-layer entropy makes spoofing expensive
2. **Duplicate Prevention**: Hardware hash prevents double-mining
3. **Reputation System**: Peer reputation prevents network attacks
4. **Sophia Veto**: AI can veto harmful governance proposals

## Future Work

1. **Full Network Implementation**: Complete P2P stack with libp2p
2. **Database Layer**: Persistent blockchain storage
3. **Smart Contracts**: ErgoScript integration
4. **Light Client**: SPV proofs for mobile wallets
5. **Hardware Detection Library**: Native CPU feature detection

## References

- [RIP-001](docs/RIP-001-core-types.md): Core Types Specification
- [RIP-002](docs/RIP-002-proof-of-antiquity.md): PoA Consensus
- [RIP-003](docs/RIP-003-deep-entropy.md): Deep Entropy Verification
- [RIP-004](docs/RIP-004-nft-badges.md): NFT Badge System
- [RIP-005](docs/RIP-005-network-protocol.md): Network Protocol
- [RIP-006](docs/RIP-006-governance.md): Governance System

## License

MIT License - See LICENSE file for details.

## Authors

- Flamekeeper Scott <scott@rustchain.net>
- Sophia Elya
- RustChain Contributors

---

*Documentation generated: 2026-03-07*
*RustChain Core v0.1.0*
