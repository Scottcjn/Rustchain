/**
 * RustChain Transaction Operations
 * 
 * High-level transaction building and sending utilities.
 */

import { TransactionError, AuthenticationError } from './errors.js';

/**
 * High-level transaction operations for RustChain
 * 
 * @example
 * ```javascript
 * const client = new RustChainClient({ adminKey: 'your-key' });
 * const tx = new Transaction(client);
 * 
 * const result = await tx.send('from-wallet', 'to-wallet', 10.0);
 * console.log(`Transaction ID: ${result.pending_id}`);
 * ```
 */
export class Transaction {
  /**
   * Create a Transaction instance
   * @param {Object} client - RustChainClient instance
   */
  constructor(client) {
    this.client = client;
  }
  
  /**
   * Send RTC from one wallet to another
   * 
   * @param {string} fromWallet - Source wallet ID
   * @param {string} toWallet - Destination wallet ID
   * @param {number} amountRtc - Amount to transfer in RTC
   * @param {string} [adminKey] - Optional admin key override
   * @returns {Promise<Object>} Transaction result with pending_id
   * @throws {TransactionError} If transaction fails
   * @throws {AuthenticationError} If admin key is missing
   * 
   * @example
   * ```javascript
   * const result = await tx.send('wallet1', 'wallet2', 10.0);
   * console.log(`Transaction ID: ${result.pending_id}`);
   * ```
   */
  async send(fromWallet, toWallet, amountRtc, adminKey = null) {
    if (amountRtc <= 0) {
      throw new TransactionError('Amount must be greater than 0');
    }
    
    if (!fromWallet || !toWallet) {
      throw new TransactionError('Both fromWallet and toWallet are required');
    }
    
    try {
      const result = await this.client.transferRtc(
        fromWallet,
        toWallet,
        amountRtc,
        adminKey
      );
      
      if (result.error) {
        throw new TransactionError(result.error);
      }
      
      return result;
      
    } catch (error) {
      if (error instanceof AuthenticationError) {
        throw error;
      }
      throw new TransactionError(`Transaction failed: ${error.message}`);
    }
  }
  
  /**
   * Build a transaction without sending it
   * 
   * Useful for previewing transaction details before submission.
   * 
   * @param {string} fromWallet - Source wallet ID
   * @param {string} toWallet - Destination wallet ID
   * @param {number} amountRtc - Amount to transfer in RTC
   * @returns {Object} Transaction preview object
   * 
   * @example
   * ```javascript
   * const preview = tx.buildTransfer('wallet1', 'wallet2', 10.0);
   * console.log(`Will send ${preview.amount_rtc} RTC`);
   * ```
   */
  buildTransfer(fromWallet, toWallet, amountRtc) {
    return {
      from_miner: fromWallet,
      to_miner: toWallet,
      amount_rtc: amountRtc,
      status: 'preview',
    };
  }
  
  /**
   * Validate a transaction before sending
   * 
   * Checks:
   * - Amount is positive
   * - Wallet names are valid format
   * - Source wallet exists (if possible)
   * 
   * @param {string} fromWallet - Source wallet ID
   * @param {string} toWallet - Destination wallet ID
   * @param {number} amountRtc - Amount to transfer in RTC
   * @returns {Promise<[boolean, string]>} Tuple of [is_valid, message]
   * 
   * @example
   * ```javascript
   * const [isValid, msg] = await tx.validateTransfer('wallet1', 'wallet2', 10.0);
   * if (isValid) {
   *   console.log('Transaction is valid!');
   * } else {
   *   console.log(`Invalid: ${msg}`);
   * }
   * ```
   */
  async validateTransfer(fromWallet, toWallet, amountRtc) {
    if (amountRtc <= 0) {
      return [false, 'Amount must be greater than 0'];
    }
    
    if (!fromWallet) {
      return [false, 'Source wallet is required'];
    }
    
    if (!toWallet) {
      return [false, 'Destination wallet is required'];
    }
    
    if (fromWallet === toWallet) {
      return [false, 'Cannot transfer to same wallet'];
    }
    
    // Check if source wallet exists
    const exists = await this.client.checkWalletExists(fromWallet);
    if (!exists) {
      return [false, `Source wallet '${fromWallet}' does not exist`];
    }
    
    return [true, 'Transaction is valid'];
  }
}
