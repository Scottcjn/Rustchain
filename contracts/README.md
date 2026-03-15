# RIP-305: Cross-Chain Airdrop — wRTC on Solana + Base

## Solana SPL Token
```bash
cd contracts/solana
python create_wrtc_token.py
```

## Base ERC-20
```bash
cd contracts/base
npx hardhat run ../scripts/deploy_base.js --network base-sepolia
```

## Token Details
| Property | Value |
|----------|-------|
| Name | Wrapped RustChain Token |
| Symbol | wRTC |
| Decimals | 6 |
| Solana Mint | TBD (created on deploy) |
| Base Contract | TBD (created on deploy) |
