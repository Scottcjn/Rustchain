# @rustchain/sdk

TypeScript SDK for the RustChain API. Provides typed methods for every endpoint
exposed by the RustChain integrated node (v2.2.1).

## Installation

```bash
npm install @rustchain/sdk
```

> Requires Node.js 18+ (uses the built-in `fetch` API).

## Quick start

```typescript
import { RustChainClient } from "@rustchain/sdk";

const rc = new RustChainClient({
  baseUrl: "http://50.28.86.131:8099",
});

// Health check
const health = await rc.health();
console.log(health.version); // "2.2.1-security-hardened"

// Current epoch
const epoch = await rc.epoch();
console.log(`Epoch ${epoch.epoch}, slot ${epoch.slot}`);

// Wallet balance
const bal = await rc.walletBalance("Ivan-houzhiwen");
console.log(`${bal.amount_rtc} RTC`);
```

## Admin endpoints

Pass `adminKey` in the constructor to access privileged endpoints:

```typescript
const rc = new RustChainClient({
  baseUrl: "http://50.28.86.131:8099",
  adminKey: process.env.RC_ADMIN_KEY,
});

const balances = await rc.allBalances(100);
const pending = await rc.pendingList("pending");
```

## API coverage

| Category                | Methods |
|-------------------------|---------|
| Health & Status         | `health`, `ready`, `opsReadiness`, `stats`, `metrics`, `metricsMac`, `openApiSpec`, `ouiEnforceStatus` |
| Attestation             | `attestChallenge`, `attestSubmit`, `attestDebug` |
| Epochs & Enrollment     | `epoch`, `epochEnroll`, `lotteryEligibility`, `epochRewards`, `settleRewards` |
| Block Headers           | `setMinerHeaderKey`, `ingestSignedHeader`, `chainTip` |
| Wallet & Balance        | `balanceByPk`, `walletBalance`, `walletHistory`, `signedTransfer`, `adminTransfer`, `resolveWallet`, `allBalances`, `allWalletBalances`, `ledger` |
| Pending Ledger          | `pendingList`, `pendingVoid`, `pendingConfirm`, `pendingIntegrity` |
| Withdrawals (RIP-0008)  | `registerWithdrawKey`, `withdrawRequest`, `withdrawStatus`, `withdrawHistory`, `feePool` |
| Governance (RIP-0142)   | `govRotateStage`, `govRotateMessage`, `govRotateApprove`, `govRotateCommit`, `govPropose`, `govProposals`, `govProposalDetail`, `govVote` |
| Genesis (RIP-0144)      | `genesisExport` |
| Miners & Network        | `miners`, `nodes`, `minerBadge`, `minerDashboard`, `minerAttestationHistory`, `bountyMultiplier` |
| Admin - OUI Denylist    | `ouiToggle`, `ouiList`, `ouiAdd`, `ouiRemove` |
| Admin - Wallet Review   | `walletReviewList`, `walletReviewCreate`, `walletReviewResolve` |
| Beacon Protocol         | `beaconSubmit`, `beaconDigest`, `beaconEnvelopes` |
| P2P Sync                | `p2pStats`, `p2pPing`, `p2pBlocks`, `p2pAddPeer` |

## Error handling

All non-2xx responses throw a `RustChainError` with the HTTP status and parsed
body:

```typescript
import { RustChainError } from "@rustchain/sdk";

try {
  await rc.walletBalance("nonexistent");
} catch (err) {
  if (err instanceof RustChainError) {
    console.error(err.status, err.body);
  }
}
```

## Self-signed certificates

The RustChain node uses self-signed TLS. If connecting over HTTPS, pass a
custom `fetch` that disables certificate verification, or set
`NODE_TLS_REJECT_UNAUTHORIZED=0` in your environment.

## Development

```bash
npm install
npm run build
npm test
```

## License

MIT
