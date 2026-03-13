# RustChain JavaScript SDK (rustchain-js)

[![npm version](https://badge.fury.io/js/rustchain-js.svg)](https://badge.fury.io/js/rustchain-js)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Node.js 14+](https://img.shields.io/badge/node-14+-blue.svg)](https://nodejs.org/en/download/)

Official JavaScript/TypeScript SDK for the RustChain blockchain. Query wallets, send transactions, and interact with the RustChain network from Node.js or browser environments.

## Features

- ✅ **Wallet Queries** - Check balances, verify wallet existence, view pending transfers
- ✅ **Transaction Sending** - Transfer RTC between wallets (requires admin key)
- ✅ **Network Information** - Get epoch info, active miners, holder statistics
- ✅ **Lottery Eligibility** - Check wallet eligibility for epoch rewards
- ✅ **Health Monitoring** - Node health checks and status information
- ✅ **TypeScript Ready** - Full TypeScript type definitions included
- ✅ **Type Safety** - Complete type hints for IDE autocomplete and compile-time checking
- ✅ **ESM & CJS** - Works with both module systems
- ✅ **Browser Compatible** - Works in modern browsers

## Installation

### npm

```bash
npm install rustchain-js
```

### yarn

```bash
yarn add rustchain-js
```

### pnpm

```bash
pnpm add rustchain-js
```

### CDN (for browsers)

```html
<script type="module">
  import { RustChainClient } from 'https://cdn.jsdelivr.net/npm/rustchain-js/+esm';
</script>
```

## Quick Start

### JavaScript (ES Modules)

```javascript
import { RustChainClient } from 'rustchain-js';

// Initialize client
const client = new RustChainClient({
  nodeUrl: 'https://50.28.86.131',
});

// Check wallet balance
const balance = await client.getBalance('my-wallet');
console.log(`Balance: ${balance.balance_rtc} RTC`);

// Check if wallet exists
const exists = await client.checkWalletExists('my-wallet');
console.log(`Wallet exists: ${exists}`);

// Get epoch information
const epoch = await client.getEpochInfo();
console.log(`Current epoch: ${epoch.epoch}`);
```

### TypeScript

```typescript
import { RustChainClient, BalanceResponse, RustChainError } from 'rustchain-js';

// Type-safe client initialization
const client = new RustChainClient({
  nodeUrl: 'https://50.28.86.131',
  adminKey: 'your-admin-key', // Required for transfers
  timeout: 10000
});

// Type-safe API calls
try {
  const balance: BalanceResponse = await client.getBalance('my-wallet');
  console.log(`Balance: ${balance.balance_rtc} RTC`);
  
  if (balance.exists) {
    console.log('Wallet is active');
  }
} catch (error) {
  if (error instanceof RustChainError) {
    console.error(`HTTP ${error.statusCode}: ${error.message}`);
  }
}
```

### Type Checking

The SDK includes complete TypeScript type definitions. Run type checking:

```bash
# Install dev dependencies
npm install --save-dev typescript @types/node

# Run type check
npm run typecheck
```

## Advanced Usage

### Wallet Operations

```javascript
import { RustChainClient, Wallet } from 'rustchain-js';

const client = new RustChainClient();
const wallet = new Wallet(client);

// Validate wallet name
const [isValid, msg] = wallet.validateName('my-wallet');
if (isValid) {
  console.log('✓ Valid wallet name');
} else {
  console.log(`✗ ${msg}`);
}

// Get wallet balance
const balance = await wallet.getBalance('my-wallet');
console.log(`Balance: ${balance} RTC`);

// Check pending transfers
const pending = await wallet.getPending('my-wallet');
pending.forEach(transfer => {
  console.log(`Pending: ${transfer.amount_rtc} RTC`);
});

// Get registration guide
const guide = wallet.registrationGuide('new-wallet');
console.log(guide);
```

### Transaction Operations

```javascript
import { RustChainClient, Transaction } from 'rustchain-js';

// Initialize with admin key
const client = new RustChainClient({
  adminKey: 'your-admin-key',
});
const tx = new Transaction(client);

// Validate transaction
const [isValid, msg] = await tx.validateTransfer('wallet1', 'wallet2', 10.0);
if (isValid) {
  // Send transaction
  const result = await tx.send('wallet1', 'wallet2', 10.0);
  console.log(`Transaction ID: ${result.pending_id}`);
} else {
  console.log(`Invalid transaction: ${msg}`);
}
```

### Network Information

```javascript
import { RustChainClient } from 'rustchain-js';

const client = new RustChainClient();

// Get active miners
const miners = await client.getActiveMiners();
console.log(`Active miners: ${miners.length}`);

// Get all holders (admin only)
const clientAdmin = new RustChainClient({
  adminKey: 'your-admin-key',
});
const holders = await clientAdmin.getAllHolders();
holders.slice(0, 10).forEach(holder => {
  console.log(`${holder.miner_id}: ${holder.amount_rtc} RTC`);
});

// Get holder statistics
const stats = await clientAdmin.getHolderStats();
console.log(`Total wallets: ${stats.total_wallets}`);
console.log(`Total RTC: ${stats.total_rtc}`);
```

### Error Handling

```javascript
import { 
  RustChainClient,
  RustChainError,
  WalletError,
  TransactionError,
  NetworkError,
  AuthenticationError
} from 'rustchain-js';

const client = new RustChainClient();

try {
  const balance = await client.getBalance('my-wallet');
} catch (error) {
  if (error instanceof NetworkError) {
    console.error(`Connection failed: ${error.message}`);
  } else if (error instanceof AuthenticationError) {
    console.error(`Authentication failed: ${error.message}`);
  } else if (error instanceof RustChainError) {
    console.error(`API error: ${error.message}`);
  } else {
    console.error(`Unknown error: ${error.message}`);
  }
}
```

## Configuration

### Environment Variables

You can configure the SDK using environment variables:

```bash
export RUSTCHAIN_NODE_URL="https://50.28.86.131"
export RUSTCHAIN_ADMIN_KEY="your-admin-key"
export RUSTCHAIN_TIMEOUT="10000"
```

### Custom Configuration

```javascript
const client = new RustChainClient({
  nodeUrl: 'https://50.28.86.131',    // RustChain node URL
  adminKey: 'your-admin-key',         // Admin key for privileged ops
  timeout: 10000,                     // Request timeout in ms
});
```

## API Reference

### RustChainClient

#### `constructor(options)`
Initialize the RustChain client.

**Options:**
- `nodeUrl` (string, optional): RustChain node URL (default: https://50.28.86.131)
- `adminKey` (string, optional): Admin key for privileged operations
- `timeout` (number, optional): Request timeout in milliseconds (default: 10000)

#### `getBalance(minerId)`
Get wallet balance for a miner/wallet ID.

**Returns:** Promise<Object> with `miner_id` and `balance_rtc`

#### `checkWalletExists(minerId)`
Check if a wallet exists on the network.

**Returns:** Promise<boolean>

#### `getPendingTransfers(minerId)`
Get pending transfers for a wallet.

**Returns:** Promise<Array> of pending transfer objects

#### `transferRtc(fromWallet, toWallet, amountRtc, adminKey)`
Transfer RTC between wallets.

**Returns:** Promise<Object> with transaction result

#### `getEpochInfo()`
Get current epoch and slot information.

**Returns:** Promise<Object> with epoch, slot, and enrolled_miners

#### `getActiveMiners()`
Get list of currently attesting miners.

**Returns:** Promise<Array> of miner objects

#### `getAllHolders(adminKey)`
Get all wallet balances (admin only).

**Returns:** Promise<Array> of wallet objects

#### `getHolderStats(adminKey)`
Get aggregated statistics (admin only).

**Returns:** Promise<Object> with aggregate statistics

#### `checkEligibility(minerId)`
Check lottery/epoch eligibility.

**Returns:** Promise<Object> with eligibility information

#### `healthCheck()`
Check node health status.

**Returns:** Promise<Object> with health status

#### `getNodeInfo()`
Get node information and version.

**Returns:** Promise<Object> with node information

### Wallet

High-level wallet operations wrapper.

### Transaction

High-level transaction operations wrapper.

## Examples

See the `examples/` directory for complete working examples:

- `examples/basic_usage.js` - Basic client usage
- `examples/wallet_management.js` - Wallet operations
- `examples/transactions.js` - Transaction examples
- `examples/network_info.js` - Network queries
- `examples/error_handling.js` - Error handling patterns

## Testing

Run the test suite:

```bash
npm test
```

Run with coverage:

```bash
npm run test:coverage
```

## Browser Support

The SDK works in all modern browsers that support:
- ES6 modules
- Fetch API
- AbortController

For older browsers, include polyfills for `fetch` and `AbortController`.

```html
<script src="https://cdn.jsdelivr.net/npm/whatwg-fetch@3/dist/fetch.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/abortcontroller-polyfill@1/dist/polyfill.min.js"></script>
```

## Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) for details.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- **Documentation:** https://github.com/Scottcjn/bounty-concierge
- **Issues:** https://github.com/Scottcjn/rustchain-js/issues
- **Discord:** https://discord.gg/VqVVS2CW9Q
- **Twitter:** [@RustchainPOA](https://twitter.com/RustchainPOA)

## Acknowledgments

- RustChain Team for the blockchain infrastructure
- All contributors and bounty hunters
- The PowerPC and retro computing community
