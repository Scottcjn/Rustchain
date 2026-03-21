# wRTC Token - Solana SPL Token for RIP-305

> **Track A of RIP-305:** Wrapped RTC (wRTC) SPL Token Implementation on Solana

## Overview

This Anchor program implements the **wRTC (Wrapped RTC)** SPL Token for Phase 1 of the cross-chain bridge described in [RIP-305](https://github.com/Scottcjn/rustchain-bounties/issues/1149).

### Token Specification

| Property | Value |
|----------|-------|
| **Name** | Wrapped RTC |
| **Symbol** | wRTC |
| **Decimals** | 6 (matches RTC internal precision) |
| **Total Allocation** | 30,000 wRTC on Solana |
| **Mint Authority** | Elyan Labs multisig (upgradeable to DAO) |
| **Program ID** | `wRTC1111111111111111111111111111111111111` |

### Why RIP-305?

RIP-305 defines a multi-phase cross-chain bridge strategy:

- **Phase 1 (This Implementation):** SPL Token on Solana - wRTC
- **Phase 2:** ERC-20 wrapper on EVM chains
- **Phase 3:** Native asset bridging via chain-specific protocols

The wRTC token serves as the Solana-side representation of RTC, enabling:
- Cross-chain transfers via bridge operations
- Integration with Solana DeFi ecosystem
- Trading on Solana-based DEXs (Raydium, Orca, etc.)

## Architecture

### Program Structure

```
solana/wrtc-program/
├── Cargo.toml                          # Workspace crate
├── programs/
│   └── wrtc/
│       ├── Cargo.toml                  # Program crate
│       └── src/
│           ├── lib.rs                   # Program entry point
│           └── instructions/
│               ├── mod.rs               # Module exports
│               ├── initialize.rs        # Initialize mint
│               ├── mint.rs              # Mint tokens
│               ├── burn.rs              # Burn tokens
│               └── set_bridge_authority.rs # Update authority
├── tests/
│   └── wrtc_token.test.ts              # TypeScript Anchor tests
├── scripts/
│   ├── deploy-devnet.sh                # Devnet deployment
│   ├── deploy-mainnet.sh               # Mainnet deployment
│   └── verify-deployment.sh            # Deployment verification
├── app/
│   └── wrtc_sdk.ts                     # TypeScript SDK
└── README.md
```

### Program Instructions

| Instruction | Description | Authority Required |
|-------------|-------------|-------------------|
| `initialize` | Initialize mint with decimals | Mint authority |
| `mint` | Mint new wRTC tokens | Mint authority |
| `burn` | Burn wRTC tokens | Mint authority |
| `set_bridge_authority` | Update mint authority | Current authority |

### Security Model

1. **Single Mint Authority:** All minting/burning controlled by one authority
2. **Multisig Ready:** Authority can be a n-of-m multisig
3. **DAO Upgrade Path:** Authority can be transferred to DAO governance
4. **Freeze Authority:** Optional account freezing (disabled by default)

## Installation

### Prerequisites

- Rust 1.70+
- Solana CLI 1.16+
- Anchor CLI 0.30.0+
- Node.js 18+ (for TypeScript/SDK)

### Build

```bash
# Build the Anchor program
cargo build-sbf

# Or with Anchor
anchor build

# Build the TypeScript SDK
npm install
npm run build
```

### Test

```bash
# Run Anchor tests
cargo test

# Or with Anchor
anchor test

# Run TypeScript tests specifically
anchor test --skip-build
```

## Deployment

### Devnet Deployment

```bash
# Ensure Solana CLI is configured for devnet
solana config set --cluster devnet

# Deploy
./scripts/deploy-devnet.sh

# Verify
./scripts/verify-deployment.sh wRTC111111... devnet
```

### Mainnet Deployment

```bash
# WARNING: Mainnet deployment requires careful consideration

# Ensure proper security measures
./scripts/deploy-mainnet.sh
```

### Post-Deployment Checklist

1. ✅ Verify program on-chain
2. ✅ Initialize mint with proper decimals (6)
3. ✅ Transfer mint authority to Elyan Labs multisig
4. ✅ Configure bridge authority for Phase 1 operations
5. ✅ Update program ID in SDK and frontend integrations
6. ✅ Verify token metadata
7. ✅ Set up monitoring and alerts

## SDK Usage

### TypeScript SDK

```typescript
import { 
  WRTCTokenSDK, 
  createWRTCTokenSDK 
} from './app/wrtc_sdk';
import { Connection, PublicKey, Keypair } from '@solana/web3.js';

// Initialize SDK
const connection = new Connection('https://api.devnet.solana.com');
const programId = new PublicKey('wRTC1111111111111111111111111111111111111');
const sdk = createWRTCTokenSDK(connection, programId);

// Initialize mint
const { mintAuthority, freezeAuthority } = await sdk.initialize({
  decimals: 6,
  mintAuthority: authorityKeypair.publicKey,
  freezeAuthority: authorityKeypair.publicKey,
});

// Mint tokens
const signature = await sdk.mint(
  { amount: 1000_000_000, recipient: recipientPubkey },
  authorityKeypair
);

// Get balance
const balance = await sdk.getBalance(holderPubkey);
console.log(`Balance: ${balance} wRTC`);

// Burn tokens
await sdk.burn(
  { amount: 100_000_000, holder: holderPubkey },
  authorityKeypair
);

// Update bridge authority
await sdk.setBridgeAuthority(
  { newAuthority: newAuthorityPubkey },
  currentAuthorityKeypair
);

// Get mint info
const mintInfo = await sdk.getMintInfo();
console.log('Supply:', mintInfo.supply.toString());
```

### CLI Usage (via Solana CLI)

```bash
# Create associated token account
spl-token create-account wRTC111111...

# Check balance
spl-token balance wRTC111111...

# Transfer tokens
spl-token transfer wRTC111111... 100 <recipient>

# Burn tokens
spl-token burn wRTC111111... 50
```

## Integration Examples

### Raydium Liquidity Pool

```typescript
// Add wRTC to Raydium liquidity pool
import { Liquidity } from '@raydium-io/raydium-sdk';

const poolInfo = await Liquidity.makePoolInfo({
  // ... configuration
  mintA: wRTCToken,
  mintB: SOL,
  // ...
});
```

### Jupiter Aggregator

```typescript
// Get quote for wRTC/SOL swap
const quote = await jupiter.getQuote({
  inputMint: wRTCMint,
  outputMint: SOLMint,
  amount: 1000000,
});
```

## Token Metadata

The wRTC token follows standard SPL token metadata:

```json
{
  "name": "Wrapped RTC",
  "symbol": "wRTC",
  "decimals": 6,
  "uri": "https://rustchain.io/tokens/wrtc.json"
}
```

### Rationale for 6 Decimals

- **RTC internal precision:** RTC uses 6 decimal places internally
- **Cross-chain consistency:** Simplifies bridging calculations
- **Solana compatibility:** Standard SPL token precision
- **User experience:** Allows fractional wRTC while maintaining sufficient granularity

## Development

### Project Structure

```
.
├── Cargo.toml              # Workspace configuration
├── Anchor.toml             # Anchor project config
├── programs/               # Solana programs
│   └── wrtc/              # wRTC token program
├── app/                   # TypeScript SDK
│   └── wrtc_sdk.ts
├── tests/                  # Integration tests
│   └── wrtc_token.test.ts
└── scripts/                # Deployment scripts
    ├── deploy-devnet.sh
    ├── deploy-mainnet.sh
    └── verify-deployment.sh
```

### Testing

```bash
# Run all tests
anchor test

# Run with verbose output
RUST_LOG=debug anchor test

# Run specific test
anchor test --grep "Initialize"
```

### Code Style

- Follow Rust standard formatting (`cargo fmt`)
- Run Clippy checks (`cargo clippy`)
- TypeScript follows Airbnb style guide

## Security Considerations

### For Bridge Operations

1. **Multisig Requirement:** All mint/burn operations should require multisig
2. **Timelock:** Consider timelock for authority changes
3. **Monitoring:** Real-time alerts for unusual minting activity
4. **Limits:** Implement per-transaction and daily minting limits

### For Users

1. **Verify Program ID:** Always verify you're interacting with the correct program
2. **Check Metadata:** Verify token metadata matches expected values
3. **Small Test First:** Test with small amounts first
4. **Use Official Bridges:** Only use official bridges for cross-chain transfers

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests (`cargo test && anchor test`)
5. Submit a pull request

## License

MIT License - See LICENSE file in the root repository.

## References

- [RIP-305: Cross-Chain Bridge Strategy](https://github.com/Scottcjn/rustchain-bounties/issues/1149)
- [Solana Program Library](https://spl.solana.com/token)
- [Anchor Framework](https://www.anchor-lang.com/)
- [SPL Token Standard](https://spl.solana.com/token)

## Support

- **Issues:** [GitHub Issues](https://github.com/Scottcjn/Rustchain/issues)
- **Discord:** [Rustchain Discord](https://discord.gg/rustchain)
- **Email:** contact@rustchain.io
