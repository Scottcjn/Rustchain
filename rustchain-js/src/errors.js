/**
 * RustChain SDK Custom Errors
 * ============================
 * 
 * Custom exception classes for handling RustChain API errors.
 * 
 * Error Hierarchy:
 *   RustChainError (base, extends Error)
 *   ├── NetworkError: Network/connectivity issues
 *   ├── WalletError: Wallet operation failures
 *   ├── TransactionError: Transaction operation failures
 *   └── AuthenticationError: Auth/authorization failures
 * 
 * @example
 * ```javascript
 * import { RustChainError, NetworkError, TransactionError } from './errors.js';
 * 
 * try {
 *   await client.transferRtc(fromWallet, toWallet, amount);
 * } catch (error) {
 *   if (error instanceof NetworkError) {
 *     console.error('Connection failed:', error.message);
 *   } else if (error instanceof TransactionError) {
 *     console.error('Transaction failed:', error.message);
 *   } else if (error instanceof RustChainError) {
 *     console.error(`HTTP ${error.statusCode}: ${error.message}`);
 *   }
 * }
 * ```
 */

/**
 * Base error class for all RustChain SDK errors
 * 
 * All custom exceptions in the RustChain SDK inherit from this class.
 * Use this for catching any RustChain-related error.
 * 
 * @extends Error
 * @property {number|null} statusCode - HTTP status code from API response
 * @property {any|null} response - Original response object for debugging
 * 
 * @example
 * ```javascript
 * try {
 *   // Some RustChain operation
 *   await client.getBalance('wallet');
 * } catch (error) {
 *   if (error instanceof RustChainError) {
 *     console.error('RustChain error:', error.message);
 *   }
 * }
 * ```
 */
export class RustChainError extends Error {
  /**
   * Create a RustChainError
   * 
   * @param {string} message - Human-readable error message describing the failure
   * @param {number|null} [statusCode=null] - HTTP status code (e.g., 400, 404, 500)
   * @param {any|null} [response=null] - Original response object for advanced debugging
   */
  constructor(message, statusCode = null, response = null) {
    super(message);
    this.name = 'RustChainError';
    this.statusCode = statusCode;
    this.response = response;
    
    // Maintain proper stack trace for where error was thrown
    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, RustChainError);
    }
  }
  
  /**
   * Convert error to string representation
   * 
   * @returns {string} Formatted error string with status code if available
   * 
   * @example
   * ```javascript
   * const error = new RustChainError('Not found', 404);
   * console.log(error.toString()); // "404: Not found"
   * ```
   */
  toString() {
    if (this.statusCode) {
      return `${this.statusCode}: ${this.message}`;
    }
    return this.message;
  }
}

/**
 * Error for wallet-related operations
 * 
 * Thrown when wallet operations fail:
 * - Invalid wallet address format
 * - Wallet does not exist
 * - Insufficient balance
 * - Wallet registration issues
 * 
 * @extends RustChainError
 * 
 * @example
 * ```javascript
 * import { WalletError } from './errors.js';
 * 
 * try {
 *   await wallet.getBalance('invalid-wallet!');
 * } catch (error) {
 *   if (error instanceof WalletError) {
 *     console.error('Wallet operation failed:', error.message);
 *   }
 * }
 * ```
 */
export class WalletError extends RustChainError {
  /**
   * Create a WalletError
   * 
   * @param {string} message - Error message describing the wallet operation failure
   * @param {number|null} [statusCode=null] - HTTP status code
   * @param {any|null} [response=null] - Original response object
   */
  constructor(message, statusCode = null, response = null) {
    super(message, statusCode, response);
    this.name = 'WalletError';
  }
}

/**
 * Error for transaction-related operations
 * 
 * Thrown when transaction operations fail:
 * - Invalid transaction parameters
 * - Transaction validation failed
 * - Insufficient funds for transfer
 * - Duplicate transaction detected
 * - Signature verification failed
 * 
 * @extends RustChainError
 * 
 * @example
 * ```javascript
 * import { TransactionError } from './errors.js';
 * 
 * try {
 *   await tx.send(fromWallet, toWallet, -100); // Invalid amount
 * } catch (error) {
 *   if (error instanceof TransactionError) {
 *     console.error('Transaction error:', error.message);
 *   }
 * }
 * ```
 */
export class TransactionError extends RustChainError {
  /**
   * Create a TransactionError
   * 
   * @param {string} message - Error message describing the transaction failure
   * @param {number|null} [statusCode=null] - HTTP status code
   * @param {any|null} [response=null] - Original response object
   */
  constructor(message, statusCode = null, response = null) {
    super(message, statusCode, response);
    this.name = 'TransactionError';
  }
}

/**
 * Error for network connectivity issues
 * 
 * Thrown when network operations fail:
 * - Node is offline or unreachable
 * - Request timeout exceeded
 * - DNS resolution failed
 * - SSL/TLS handshake error
 * - Network connection lost
 * 
 * @extends RustChainError
 * 
 * @example
 * ```javascript
 * import { NetworkError } from './errors.js';
 * 
 * try {
 *   const client = new RustChainClient({ nodeUrl: 'http://offline-node:8080' });
 *   await client.healthCheck();
 * } catch (error) {
 *   if (error instanceof NetworkError) {
 *     console.error('Cannot connect to node:', error.message);
 *   }
 * }
 * ```
 */
export class NetworkError extends RustChainError {
  /**
   * Create a NetworkError
   * 
   * @param {string} message - Error message describing the network failure
   * @param {number|null} [statusCode=null] - HTTP status code (if available)
   * @param {any|null} [response=null] - Original response object (if available)
   */
  constructor(message, statusCode = null, response = null) {
    super(message, statusCode, response);
    this.name = 'NetworkError';
  }
}

/**
 * Error for authentication/authorization failures
 * 
 * Thrown when authentication or authorization fails:
 * - Missing admin key
 * - Invalid admin key
 * - Insufficient permissions
 * - Session expired
 * - API key revoked
 * 
 * Common HTTP status codes:
 * - 401: Unauthorized (authentication required)
 * - 403: Forbidden (insufficient permissions)
 * 
 * @extends RustChainError
 * 
 * @example
 * ```javascript
 * import { AuthenticationError } from './errors.js';
 * 
 * try {
 *   await client.transferRtc(from, to, amount); // Without admin key
 * } catch (error) {
 *   if (error instanceof AuthenticationError) {
 *     console.error('Auth failed:', error.message);
 *     console.log(`Status: ${error.statusCode}`); // 401 or 403
 *   }
 * }
 * ```
 */
export class AuthenticationError extends RustChainError {
  /**
   * Create an AuthenticationError
   * 
   * @param {string} message - Error message describing the auth failure
   * @param {number|null} [statusCode=null] - HTTP status code (typically 401 or 403)
   * @param {any|null} [response=null] - Original response object
   */
  constructor(message, statusCode = null, response = null) {
    super(message, statusCode, response);
    this.name = 'AuthenticationError';
  }
}
