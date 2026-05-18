# Smart Contract Developer Guide

This guide gives DApp builders a practical path through the RustChain contract
workspace. The current on-chain contract surface is the wrapped RTC token stack
for Base, with bridge-aware mint and burn flows documented under
`contracts/base` and `contracts/erc20`.

## Quick Start

Use the Hardhat package when you need the full development loop:

```bash
cd contracts/erc20
npm install
npm run compile
npm test
```

For a smaller reference implementation, inspect `contracts/base/wRTC.sol`. For
the production-style Base package with permit, bridge operators, pausing, tests,
deployment scripts, and interaction tooling, use `contracts/erc20`.

## Contract Lifecycle

1. Develop the contract in `contracts/erc20/contracts/WRTC.sol`.
2. Add or update tests in `contracts/erc20/test/WRTC.test.js`.
3. Compile and run the test suite with `npm run compile` and `npm test`.
4. Deploy to Base Sepolia first with `npm run deploy:base-sepolia`.
5. Verify the testnet contract before any mainnet deployment.
6. Configure bridge operators or ownership only after deployment is verified.
7. Monitor mint, burn, pause, unpause, and operator-change events.

Mainnet deployment should happen only after testnet validation, contract review,
and bridge-operator confirmation.

## Minimal DApp Interaction Example

Set `WRTC_ADDRESS` to the deployed token contract and use the provided script for
read-only checks before sending transactions:

```bash
cd contracts/erc20
export WRTC_ADDRESS=0xYourDeployedContract

node scripts/interact.js info
node scripts/interact.js balance 0xYourWallet
```

For write operations, test the exact call on Base Sepolia first:

```bash
node scripts/interact.js transfer 0xRecipient 1.5
node scripts/interact.js approve 0xSpender 10
```

Bridge-only operations such as `add-operator`, `bridge-mint`, `bridge-burn`,
`pause`, and `unpause` are administrative actions. They should be run by the
configured owner or bridge operator, preferably through a multi-signature wallet
for production deployments.

## Best Practices

- Keep private keys and RPC credentials in `.env`; never commit them.
- Run `npm test` after every Solidity or script change.
- Deploy to Base Sepolia before Base mainnet.
- Use a dedicated deployer wallet with only the gas needed for deployment.
- Transfer ownership to a multi-signature wallet for production.
- Treat bridge operator changes as high-risk configuration changes.
- Prefer read-only `info` and `balance` checks when integrating a frontend.
- Log deployed addresses, transaction hashes, constructor arguments, and
  verification status in the PR or deployment record.

## Security Checklist

Before mainnet, confirm:

- The bridge operator is not the same hot wallet used for routine development.
- The owner address is controlled by the intended production authority.
- `pause` and `unpause` procedures are documented for incident response.
- Mint and burn event monitoring is configured.
- BaseScan verification succeeds and constructor arguments are recorded.
- No test private keys, RPC URLs with tokens, or mnemonic material are committed.

## Reference Documents

- `contracts/base/README.md` - compact RIP-305 wRTC overview.
- `contracts/erc20/README.md` - full Base ERC-20 package guide.
- `contracts/erc20/docs/DEPLOYMENT_GUIDE.md` - deployment workflow.
- `contracts/erc20/docs/SECURITY_CONSIDERATIONS.md` - production risk notes.
- `contracts/erc20/docs/BRIDGE_INTEGRATION.md` - bridge integration details.
