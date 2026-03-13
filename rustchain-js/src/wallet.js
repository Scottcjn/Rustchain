/**
 * RustChain Wallet Operations
 * 
 * High-level wallet management and utilities.
 */

import { WalletError } from './errors.js';

/**
 * Wallet name validation regex
 * Rules:
 * - 3 to 64 characters
 * - Lowercase alphanumeric and hyphens only
 * - Must start and end with letter or digit
 */
const WALLET_NAME_RE = /^[a-z0-9][a-z0-9\-]{1,62}[a-z0-9]$/;

/**
 * High-level wallet operations for RustChain
 * 
 * @example
 * ```javascript
 * const client = new RustChainClient();
 * const wallet = new Wallet(client);
 * 
 * const [isValid, msg] = wallet.validateName('my-wallet');
 * if (isValid) {
 *   console.log('Valid wallet name!');
 * }
 * ```
 */
export class Wallet {
  /**
   * Create a Wallet instance
   * @param {Object} client - RustChainClient instance
   */
  constructor(client) {
    this.client = client;
  }
  
  /**
   * Validate a wallet name according to RustChain rules
   * 
   * @param {string} name - Proposed wallet name
   * @returns {[boolean, string]} Tuple of [is_valid, message]
   * 
   * @example
   * ```javascript
   * const [isValid, msg] = wallet.validateName('my-wallet');
   * if (isValid) {
   *   console.log('✓ Valid wallet name');
   * } else {
   *   console.log(`✗ ${msg}`);
   * }
   * ```
   */
  validateName(name) {
    if (!name) {
      return [false, 'Wallet name cannot be empty'];
    }
    if (name.length < 3) {
      return [false, 'Wallet name must be at least 3 characters'];
    }
    if (name.length > 64) {
      return [false, 'Wallet name must be 64 characters or fewer'];
    }
    if (name !== name.toLowerCase()) {
      return [false, 'Wallet name must be lowercase'];
    }
    if (!WALLET_NAME_RE.test(name)) {
      return [false, 'Wallet name may only contain lowercase letters, digits, and hyphens'];
    }
    
    return [true, 'Valid wallet name'];
  }
  
  /**
   * Check if a wallet exists on the network
   * 
   * @param {string} name - Wallet name to check
   * @returns {Promise<boolean>} True if wallet exists
   * 
   * @example
   * ```javascript
   * const exists = await wallet.exists('my-wallet');
   * if (exists) {
   *   console.log('Wallet already registered!');
   * }
   * ```
   */
  async exists(name) {
    return this.client.checkWalletExists(name);
  }
  
  /**
   * Get wallet balance in RTC
   * 
   * @param {string} name - Wallet name
   * @returns {Promise<number>} Balance in RTC (0.0 if wallet doesn't exist)
   * 
   * @example
   * ```javascript
   * const balance = await wallet.getBalance('my-wallet');
   * console.log(`Balance: ${balance} RTC`);
   * ```
   */
  async getBalance(name) {
    const result = await this.client.getBalance(name);
    if (result.error) {
      return 0.0;
    }
    return result.balance_rtc || 0.0;
  }
  
  /**
   * Get pending transfers for a wallet
   * 
   * @param {string} name - Wallet name
   * @returns {Promise<Array>} List of pending transfer objects
   * 
   * @example
   * ```javascript
   * const pending = await wallet.getPending('my-wallet');
   * pending.forEach(transfer => {
   *   console.log(`Pending: ${transfer.amount_rtc} RTC`);
   * });
   * ```
   */
  async getPending(name) {
    return this.client.getPendingTransfers(name);
  }
  
  /**
   * Get wallet registration instructions
   * 
   * @param {string} name - Desired wallet name
   * @returns {string} Multi-line instruction string
   * 
   * @example
   * ```javascript
   * const guide = wallet.registrationGuide('my-wallet');
   * console.log(guide);
   * ```
   */
  registrationGuide(name) {
    const [isValid, msg] = this.validateName(name);
    if (!isValid) {
      return `Invalid wallet name '${name}': ${msg}`;
    }
    
    return `
Wallet Registration Guide for: ${name}
${'='.repeat(50)}

Option 1 -- Claim a Bounty (Automatic Registration)
----------------------------------------------------
Comment on any RustChain bounty issue on GitHub with:
  "I would like to claim this bounty. Wallet: ${name}"

Your wallet is registered when the first RTC transfer is made.


Option 2 -- Install RustChain Wallet GUI
-----------------------------------------
Download the wallet from the rustchain-bounties repo releases.
The wallet will generate a BIP39 seed phrase and Ed25519 keypair automatically.


Option 3 -- Open Registration Issue
------------------------------------
Create an issue on Scottcjn/rustchain-bounties titled:
  "Wallet Registration: ${name}"

An admin will set up your wallet entry.


Next Steps
----------
1. Choose a registration method above
2. Wait for confirmation (usually within 24 hours)
3. Start earning RTC through bounties and mining!

For more info: https://github.com/Scottcjn/bounty-concierge
`;
  }
  
  /**
   * Check lottery/epoch eligibility for a wallet
   * 
   * @param {string} name - Wallet name
   * @returns {Promise<Object>} Eligibility information object
   * 
   * @example
   * ```javascript
   * const eligible = await wallet.checkEligibility('my-wallet');
   * if (eligible.eligible) {
   *   console.log('Eligible for epoch rewards!');
   * }
   * ```
   */
  async checkEligibility(name) {
    return this.client.checkEligibility(name);
  }
}
