# BOUNTY #1149 Track A - Solana SPL Token Implementation

## Summary

This document describes the implementation of **RIP-305 Track A: Solana SPL Token (wRTC)** for the Rustchain repository.

**Bounty:** [#1149 Track A - Solana SPL Token](https://github.com/Scottcjn/rustchain-bounties/issues/1149)  
**Reward:** 75 RTC  
**Claim Comment:** https://github.com/Scottcjn/rustchain-bounties/issues/1149#issuecomment-4102378009

---

## What Was Built

### Directory Structure

```
solana/wrtc-program/
├── Cargo.toml                           # Anchor program workspace crate
├── programs/
│   └── wrtc/
│       ├── Cargo.toml                   # wRTC program crate
│       └── src/
│           ├── lib.rs                   # Program entry point with ID
│           └── instructions/
│               ├── mod.rs               # Module exports
│               ├── initialize.rs        # Initialize mint instruction
│               ├── mint.rs              # Mint tokens instruction
│               ├── burn.rs              # Burn tokens instruction
│               └── set_bridge_authority.rs # Update authority instruction
├── tests/
│   └── wrtc_token.test.ts              # Comprehensive TypeScript tests
├── scripts/
│   ├── deploy-devnet.sh                 # Devnet deployment script
│   ├── deploy-mainnet.sh                # Mainnet deployment script
│   └── verify-deployment.sh             # Deployment verification script
├── app/
│   └── wrtc_sdk.ts                      # Full TypeScript SDK
├── README.md                            # Comprehensive documentation
└── .gitignore
```

### Token Specification

| Property | Value |
|----------|-------|
| Name | Wrapped RTC |
| Symbol | wRTC |
| Decimals | 6 (matches RTC internal precision) |
| Total Allocation | 30,000 wRTC on Solana |
| Mint Authority | Elyan Labs multisig (upgradeable to DAO) |
| Program ID | `wRTC1111111111111111111111111111111111111` |

### Program Instructions

1. **initialize(decimals: u8)** - Initialize the wRTC mint
2. **mint(amount: u64)** - Mint new wRTC tokens to a recipient
3. **burn(amount: u64)** - Burn wRTC tokens from a holder
4. **set_bridge_authority(new_authority: Pubkey)** - Update mint authority

---

## Implementation Details

### Rust/Anchor Program

The program is built with Anchor 0.30.0 and uses:
- `anchor_lang` for the program framework
- `anchor_spl` for SPL token integration
- `spl_token` for token operations

#### Key Security Features

- **Mint Authority Control:** Only the designated authority can mint/burn
- **Signer Verification:** All sensitive instructions require signed transactions
- **Upgrade Path:** Authority can be transferred to multisig or DAO

### TypeScript SDK

The SDK provides:
- `initialize()` - Initialize mint with parameters
- `mint()` - Mint tokens to a recipient
- `burn()` - Burn tokens from a holder
- `setBridgeAuthority()` - Update authority
- `getMintInfo()` - Get mint information
- `getBalance()` - Get holder's token balance
- `transfer()` - Transfer between accounts
- `createTokenAccount()` - Create associated token account

### TypeScript Tests

Comprehensive tests covering:
1. Initialize the wRTC mint
2. Create recipient token account
3. Mint wRTC tokens
4. Transfer tokens between accounts
5. Burn tokens
6. Set new bridge authority
7. Verify mint info

---

## How to Build

```bash
cd solana/wrtc-program

# Build the Anchor program
cargo build-sbf

# Or with Anchor CLI
anchor build
```

## How to Test

```bash
# Ensure Solana CLI is configured
solana config set --cluster devnet

# Run Anchor tests
anchor test
```

---

## How to Deploy

### Devnet

```bash
# Configure for devnet
solana config set --cluster devnet

# Run deployment script
./scripts/deploy-devnet.sh
```

### Mainnet

```bash
# WARNING: Mainnet deployment requires careful consideration
./scripts/deploy-mainnet.sh
```

### Verification

```bash
# Verify deployment
./scripts/verify-deployment.sh wRTC111111... devnet
```

---

## Deployment Info

### Devnet Deployment

After deployment, update these values:

```json
{
  "programId": "wRTC1111111111111111111111111111111111111",
  "cluster": "devnet",
  "mint": "<deployed-mint-address>",
  "timestamp": "2026-03-21T13:50:00Z"
}
```

### Mainnet Deployment

```json
{
  "programId": "<deployed-program-id>",
  "cluster": "mainnet-beta",
  "timestamp": "<deployment-timestamp>",
  "token": {
    "name": "Wrapped RTC",
    "symbol": "wRTC",
    "decimals": 6
  }
}
```

---

## Integration

### Using the SDK

```typescript
import { WRTCTokenSDK } from './app/wrtc_sdk';
import { Connection, PublicKey, Keypair } from '@solana/web3.js';

const connection = new Connection('https://api.devnet.solana.com');
const sdk = new WRTCTokenSDK(
  connection,
  new PublicKey('wRTC1111111111111111111111111111111111111')
);

// Initialize
await sdk.initialize({
  decimals: 6,
  mintAuthority: authority.publicKey,
  freezeAuthority: authority.publicKey,
}, authority);

// Mint
await sdk.mint({ amount: 1000_000_000, recipient }, authority);

// Check balance
const balance = await sdk.getBalance(holder);
```

---

## Security Considerations

### Phase 1 Bridge Operations

1. **Authority Management:** The mint authority should be a hardware wallet or multisig
2. **Monitoring:** Set up alerts for unusual minting activity
3. **Limits:** Consider implementing per-transaction and daily limits
4. **Timelock:** Use timelock for any authority changes

### For Users

1. Always verify the program ID matches `wRTC1111111111111111111111111111111111111`
2. Verify token metadata (name: "Wrapped RTC", symbol: "wRTC", decimals: 6)
3. Test with small amounts first
4. Only use official bridges for cross-chain transfers

---

## Rationale for Design Decisions

### 6 Decimals

- Matches RTC internal precision for accurate cross-chain conversions
- Standard for SPL tokens
- Allows fractional amounts while maintaining precision

### Single Mint Authority

- Simplifies Phase 1 bridge operations
- Easier to secure with multisig
- Can be upgraded to DAO governance later

### Anchor Framework

- Well-tested and audited
- Built-in account validation
- IDL generation for TypeScript SDK
- Large ecosystem support

---

## Files Modified/Created

### New Files

| File | Purpose |
|------|---------|
| `solana/wrtc-program/Cargo.toml` | Workspace crate configuration |
| `solana/wrtc-program/programs/wrtc/Cargo.toml` | Program crate configuration |
| `solana/wrtc-program/programs/wrtc/src/lib.rs` | Program entry point |
| `solana/wrtc-program/programs/wrtc/src/instructions/mod.rs` | Instruction module |
| `solana/wrtc-program/programs/wrtc/src/instructions/initialize.rs` | Initialize instruction |
| `solana/wrtc-program/programs/wrtc/src/instructions/mint.rs` | Mint instruction |
| `solana/wrtc-program/programs/wrtc/src/instructions/burn.rs` | Burn instruction |
| `solana/wrtc-program/programs/wrtc/src/instructions/set_bridge_authority.rs` | Authority instruction |
| `solana/wrtc-program/tests/wrtc_token.test.ts` | TypeScript tests |
| `solana/wrtc-program/scripts/deploy-devnet.sh` | Devnet deployment |
| `solana/wrtc-program/scripts/deploy-mainnet.sh` | Mainnet deployment |
| `solana/wrtc-program/scripts/verify-deployment.sh` | Deployment verification |
| `solana/wrtc-program/app/wrtc_sdk.ts` | TypeScript SDK |
| `solana/wrtc-program/README.md` | Documentation |
| `solana/wrtc-program/.gitignore` | Git ignore rules |

---

## Next Steps

1. **Deploy to Devnet:** Run deployment scripts to verify functionality
2. **Update Program ID:** Generate a real program ID for mainnet
3. **Configure Multisig:** Set up Elyan Labs multisig for mint authority
4. **Phase 2 Integration:** Implement bridge logic for ERC-20 on EVM chains
5. **Frontend Integration:** Add wRTC to RustChain DEX/bridge UI

---

## References

- [RIP-305](https://github.com/Scottcjn/rustchain-bounties/issues/1149)
- [Solana SPL Token Standard](https://spl.solana.com/token)
- [Anchor Framework Documentation](https://www.anchor-lang.com/)
- [Solana Program Library](https://github.com/solana-labs/solana-program-library)

---

**Implementation Date:** 2026-03-21  
**Implementation by:** kuanglaodi2-sudo  
**Bounty:** #1149 Track A - Solana SPL Token
