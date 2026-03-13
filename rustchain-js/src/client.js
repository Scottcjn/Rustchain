/**
 * RustChain API Client
 * 
 * Core client for interacting with the RustChain blockchain node.
 */

import { NetworkError, RustChainError, AuthenticationError } from './errors.js';

/**
 * RustChain blockchain API client
 * 
 * @example
 * ```javascript
 * const client = new RustChainClient({
 *   nodeUrl: 'https://50.28.86.131',
 *   adminKey: 'your-admin-key'
 * });
 * 
 * const balance = await client.getBalance('my-wallet');
 * console.log(`Balance: ${balance.balance_rtc} RTC`);
 * ```
 */
export class RustChainClient {
  /**
   * Create a RustChain client
   * @param {Object} options - Client options
   * @param {string} [options.nodeUrl='https://50.28.86.131'] - RustChain node URL
   * @param {string} [options.adminKey] - Admin key for privileged operations
   * @param {number} [options.timeout=10000] - Request timeout in milliseconds
   */
  constructor(options = {}) {
    this.nodeUrl = options.nodeUrl?.replace(/\/$/, '') || 'https://50.28.86.131';
    this.adminKey = options.adminKey || null;
    this.timeout = options.timeout || 10000;
  }
  
  /**
   * Make HTTP request to RustChain node
   * 
   * @param {string} method - HTTP method (GET/POST)
   * @param {string} endpoint - API endpoint path
   * @param {Object} [params] - URL query parameters
   * @param {Object} [data] - JSON body data
   * @param {Object} [headers] - Additional headers
   * @returns {Promise<Object>} Parsed JSON response
   * @throws {NetworkError} If connection fails
   * @throws {RustChainError} If API returns error
   * @private
   */
  async _request(method, endpoint, params = null, data = null, headers = {}) {
    const url = new URL(endpoint, this.nodeUrl);
    
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        url.searchParams.append(key, value);
      });
    }
    
    const fetchOptions = {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...headers,
      },
    };
    
    if (this.adminKey) {
      fetchOptions.headers['X-Admin-Key'] = this.adminKey;
    }
    
    if (data && method === 'POST') {
      fetchOptions.body = JSON.stringify(data);
    }
    
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), this.timeout);
      
      const response = await fetch(url.toString(), {
        ...fetchOptions,
        signal: controller.signal,
      });
      
      clearTimeout(timeoutId);
      
      if (!response.ok) {
        if (response.status === 401 || response.status === 403) {
          throw new AuthenticationError(
            `HTTP ${response.status}: Admin key required or invalid`,
            response.status,
            response
          );
        }
        throw new RustChainError(
          `HTTP ${response.status}: ${response.statusText}`,
          response.status,
          response
        );
      }
      
      return await response.json();
      
    } catch (error) {
      if (error.name === 'AbortError') {
        throw new NetworkError(`Request timeout after ${this.timeout}ms`);
      }
      
      if (error instanceof RustChainError) {
        throw error;
      }
      
      if (error instanceof TypeError && error.message.includes('fetch')) {
        throw new NetworkError(`Could not connect to node at ${this.nodeUrl}`);
      }
      
      throw new RustChainError(`Request failed: ${error.message}`);
    }
  }
  
  // ==========================================================================
  // Wallet Operations
  // ==========================================================================
  
  /**
   * Get wallet balance for a miner/wallet ID
   * 
   * @param {string} minerId - Wallet or miner identifier
   * @returns {Promise<Object>} Balance information with miner_id and balance_rtc
   * 
   * @example
   * ```javascript
   * const balance = await client.getBalance('my-wallet');
   * console.log(`Balance: ${balance.balance_rtc} RTC`);
   * ```
   */
  async getBalance(minerId) {
    return this._request('GET', '/balance', { miner_id: minerId });
  }
  
  /**
   * Check if a wallet exists on the RustChain network
   * 
   * @param {string} minerId - Wallet or miner identifier
   * @returns {Promise<boolean>} True if wallet exists
   * 
   * @example
   * ```javascript
   * const exists = await client.checkWalletExists('my-wallet');
   * if (exists) {
   *   console.log('Wallet exists!');
   * }
   * ```
   */
  async checkWalletExists(minerId) {
    try {
      const result = await this.getBalance(minerId);
      return !result.error;
    } catch (error) {
      if (error instanceof NetworkError) {
        return false;
      }
      throw error;
    }
  }
  
  /**
   * Get pending transfers for a wallet
   * 
   * @param {string} minerId - Wallet or miner identifier
   * @returns {Promise<Array>} List of pending transfer objects
   * 
   * @example
   * ```javascript
   * const pending = await client.getPendingTransfers('my-wallet');
   * pending.forEach(transfer => {
   *   console.log(`Pending: ${transfer.amount_rtc} RTC`);
   * });
   * ```
   */
  async getPendingTransfers(minerId) {
    const result = await this._request('GET', '/wallet/pending', { miner_id: minerId });
    return Array.isArray(result) ? result : (result.pending || []);
  }
  
  /**
   * Transfer RTC between wallets
   * 
   * Requires admin key for authorization.
   * 
   * @param {string} fromWallet - Source wallet ID
   * @param {string} toWallet - Destination wallet ID
   * @param {number} amountRtc - Amount to transfer in RTC
   * @param {string} [adminKey] - Optional admin key override
   * @returns {Promise<Object>} Transaction result with pending_id
   * 
   * @example
   * ```javascript
   * const result = await client.transferRtc('wallet1', 'wallet2', 10.0);
   * console.log(`Transaction ID: ${result.pending_id}`);
   * ```
   */
  async transferRtc(fromWallet, toWallet, amountRtc, adminKey = null) {
    const key = adminKey || this.adminKey;
    if (!key) {
      throw new AuthenticationError('Admin key required for transfers');
    }
    
    const data = {
      from_miner: fromWallet,
      to_miner: toWallet,
      amount_rtc: amountRtc,
    };
    
    return this._request('POST', '/wallet/transfer', null, data, {
      'X-Admin-Key': key,
    });
  }
  
  // ==========================================================================
  // Network & Epoch Information
  // ==========================================================================
  
  /**
   * Get current epoch and slot information
   * 
   * @returns {Promise<Object>} Epoch information with epoch, slot, and enrolled_miners
   * 
   * @example
   * ```javascript
   * const epoch = await client.getEpochInfo();
   * console.log(`Current epoch: ${epoch.epoch}`);
   * ```
   */
  async getEpochInfo() {
    return this._request('GET', '/epoch');
  }
  
  /**
   * Get list of currently attesting miners
   * 
   * @returns {Promise<Array>} List of miner objects
   * 
   * @example
   * ```javascript
   * const miners = await client.getActiveMiners();
   * console.log(`Active miners: ${miners.length}`);
   * ```
   */
  async getActiveMiners() {
    return this._request('GET', '/api/miners');
  }
  
  /**
   * Get all wallet balances (admin only)
   * 
   * @param {string} [adminKey] - Optional admin key override
   * @returns {Promise<Array>} List of wallet objects with miner_id, amount_rtc, category
   * 
   * @example
   * ```javascript
   * const holders = await client.getAllHolders();
   * holders.slice(0, 5).forEach(holder => {
   *   console.log(`${holder.miner_id}: ${holder.amount_rtc} RTC`);
   * });
   * ```
   */
  async getAllHolders(adminKey = null) {
    const key = adminKey || this.adminKey;
    if (!key) {
      throw new AuthenticationError('Admin key required for holder listing');
    }
    
    const result = await this._request('GET', '/api/balances', null, null, {
      'X-Admin-Key': key,
    });
    return result.balances || [];
  }
  
  /**
   * Get aggregated statistics across all wallets (admin only)
   * 
   * @param {string} [adminKey] - Optional admin key override
   * @returns {Promise<Object>} Statistics object
   * 
   * @example
   * ```javascript
   * const stats = await client.getHolderStats();
   * console.log(`Total wallets: ${stats.total_wallets}`);
   * ```
   */
  async getHolderStats(adminKey = null) {
    const key = adminKey || this.adminKey;
    if (!key) {
      throw new AuthenticationError('Admin key required for stats');
    }
    
    return this._request('GET', '/api/holders/stats', null, null, {
      'X-Admin-Key': key,
    });
  }
  
  // ==========================================================================
  // Lottery & Eligibility
  // ==========================================================================
  
  /**
   * Check lottery/epoch eligibility for a wallet
   * 
   * @param {string} minerId - Wallet or miner identifier
   * @returns {Promise<Object>} Eligibility information
   * 
   * @example
   * ```javascript
   * const eligible = await client.checkEligibility('my-wallet');
   * if (eligible.eligible) {
   *   console.log('Wallet is eligible for lottery!');
   * }
   * ```
   */
  async checkEligibility(minerId) {
    return this._request('GET', '/lottery/eligibility', { miner_id: minerId });
  }
  
  // ==========================================================================
  // Health & Status
  // ==========================================================================
  
  /**
   * Check node health status
   * 
   * @returns {Promise<Object>} Health status object
   * 
   * @example
   * ```javascript
   * const health = await client.healthCheck();
   * console.log(`Node status: ${health.status}`);
   * ```
   */
  async healthCheck() {
    return this._request('GET', '/health');
  }
  
  /**
   * Get node information and version
   * 
   * @returns {Promise<Object>} Node information object
   * 
   * @example
   * ```javascript
   * const info = await client.getNodeInfo();
   * console.log(`Node version: ${info.version}`);
   * ```
   */
  async getNodeInfo() {
    return this._request('GET', '/info');
  }
}
