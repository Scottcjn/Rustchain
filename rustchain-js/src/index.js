/**
 * RustChain JavaScript SDK
 * =========================
 * 
 * Official JavaScript/Node.js client for interacting with the RustChain blockchain.
 * Provides a simple, promise-based API for wallet management, transactions, and node queries.
 * 
 * @packageDocumentation
 * 
 * @example
 * ```javascript
 * import { RustChainClient, Wallet, Transaction } from 'rustchain-js';
 * 
 * // Initialize client
 * const client = new RustChainClient({
 *   nodeUrl: 'https://50.28.86.131',
 *   adminKey: 'your-admin-key' // Optional, required for transfers
 * });
 * 
 * // Check wallet balance
 * const balance = await client.getBalance('my-wallet');
 * console.log(`Balance: ${balance.balance_rtc} RTC`);
 * 
 * // Use Wallet helper
 * const wallet = new Wallet(client);
 * const [isValid] = wallet.validateName('my-wallet');
 * 
 * // Send transaction
 * const tx = new Transaction(client);
 * const result = await tx.send('from-wallet', 'to-wallet', 10.0);
 * console.log(`Transaction ID: ${result.pending_id}`);
 * ```
 * 
 * @module rustchain-js
 */

/**
 * Core client for RustChain blockchain API
 * @see {@link RustChainClient} for detailed API documentation
 */
export { RustChainClient } from './client.js';

/**
 * High-level wallet operations and utilities
 * @see {@link Wallet} for detailed API documentation
 */
export { Wallet } from './wallet.js';

/**
 * Transaction building and sending utilities
 * @see {@link Transaction} for detailed API documentation
 */
export { Transaction } from './transaction.js';

/**
 * Custom error classes for RustChain SDK
 * @see {@link RustChainError}, {@link WalletError}, {@link TransactionError},
 * {@link NetworkError}, {@link AuthenticationError}
 */
export * from './errors.js';

/**
 * SDK version
 * @constant {string}
 */
export const VERSION = '1.0.0';
