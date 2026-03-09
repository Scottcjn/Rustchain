/**
 * RustChain Wallet - Validation Utilities
 *
 * Provides validation functions for addresses, transactions, and messages.
 * Used by both background scripts and popup UI.
 */

/**
 * Validate RustChain address format
 * @param {string} address - The address to validate
 * @returns {boolean}
 */
export function validateAddress(address) {
  if (typeof address !== 'string') return false;
  if (!address.endsWith('RTC')) return false;
  if (address.length < 43) return false;
  
  // Check valid characters (hex + RTC suffix)
  const addressWithoutSuffix = address.slice(0, -3);
  return /^[a-fA-F0-9]+$/.test(addressWithoutSuffix);
}

/**
 * Validate transaction parameters
 * @param {Object} tx - Transaction object
 * @param {string} tx.from - Sender address
 * @param {string} tx.to - Recipient address
 * @param {string} tx.amount - Amount in RTC
 * @param {string} [tx.memo] - Optional memo
 * @param {string} [balance] - Sender's balance for validation
 * @returns {{valid: boolean, error?: string}}
 */
export function validateTransaction(tx, balance = '1000.0') {
  // Check required fields
  if (!tx.from || !tx.to || !tx.amount) {
    return { valid: false, error: 'Missing required fields (from, to, amount)' };
  }

  // Validate addresses
  if (!validateAddress(tx.from)) {
    return { valid: false, error: 'Invalid sender address' };
  }

  if (!validateAddress(tx.to)) {
    return { valid: false, error: 'Invalid recipient address' };
  }

  // Validate amount
  const amountNum = parseFloat(tx.amount);
  if (isNaN(amountNum) || amountNum <= 0) {
    return { valid: false, error: 'Invalid amount (must be positive number)' };
  }

  // Check balance
  const balanceNum = parseFloat(balance);
  const networkFee = 0.0001;
  if (amountNum + networkFee > balanceNum) {
    return { valid: false, error: `Insufficient balance (need ${amountNum + networkFee} RTC including fee)` };
  }

  return { valid: true };
}

/**
 * Validate message for signing
 * @param {string} message - Message to validate
 * @returns {{valid: boolean, error?: string}}
 */
export function validateMessage(message) {
  if (typeof message !== 'string') {
    return { valid: false, error: 'Message must be a string' };
  }

  if (message.length === 0) {
    return { valid: false, error: 'Message cannot be empty' };
  }

  if (message.length > 10000) {
    return { valid: false, error: 'Message too long (max 10000 characters)' };
  }

  return { valid: true };
}

/**
 * Truncate address for display
 * @param {string} address
 * @returns {string}
 */
export function truncateAddress(address) {
  if (!address) return '';
  if (address.length < 16) return address;
  return `${address.slice(0, 8)}...${address.slice(-6)}`;
}

/**
 * Truncate hash for display
 * @param {string} hash
 * @returns {string}
 */
export function truncateHash(hash) {
  if (!hash) return '';
  if (hash.length < 20) return hash;
  return `${hash.slice(0, 10)}...${hash.slice(-8)}`;
}

/**
 * Format amount with proper precision
 * @param {string|number} amount
 * @param {number} decimals
 * @returns {string}
 */
export function formatAmount(amount, decimals = 8) {
  const num = typeof amount === 'string' ? parseFloat(amount) : amount;
  if (isNaN(num)) return '0.00000000';
  return num.toFixed(decimals);
}

/**
 * Derive address from public key (simplified for MVP)
 * @param {string} publicKey
 * @returns {string}
 */
export function deriveAddress(publicKey) {
  const hash = publicKey.slice(0, 40);
  return hash + 'RTC';
}
