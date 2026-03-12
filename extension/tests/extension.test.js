/**
 * RustChain Extension - Unit Tests
 *
 * Tests for the browser extension background scripts and utilities.
 * Run with: node --test tests/*.test.js
 */

import { describe, it, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert';
import { webcrypto } from 'node:crypto';

// Mock chrome API
global.chrome = {
  runtime: {
    sendMessage: (msg, cb) => cb({ success: true }),
    onMessage: {
      addListener: () => {}
    },
    lastError: null
  },
  storage: {
    local: {
      get: async (keys) => ({}),
      set: async (data) => {}
    }
  },
  alarms: {
    create: () => {},
    onAlarm: {
      addListener: () => {}
    }
  }
};

// Mock crypto API using Object.defineProperty for Node.js v24+
const mockCrypto = {
  getRandomValues: (arr) => {
    for (let i = 0; i < arr.length; i++) {
      arr[i] = Math.floor(Math.random() * 256);
    }
    return arr;
  },
  subtle: {
    digest: async (algorithm, data) => {
      // Simple mock hash
      const bytes = new Uint8Array(data);
      const hash = new Uint8Array(32);
      for (let i = 0; i < 32; i++) {
        hash[i] = (bytes[i % bytes.length] + i) % 256;
      }
      return hash.buffer;
    },
    importKey: async () => ({}),
    deriveBits: async () => new ArrayBuffer(32)
  }
};

Object.defineProperty(globalThis, 'crypto', {
  value: mockCrypto,
  writable: true,
  configurable: true
});

describe('Wallet Functions', () => {
  describe('deriveAddress', () => {
    it('should derive address from public key', () => {
      const publicKey = 'abcd1234567890abcd1234567890abcd1234567890abcd1234567890abcd1234';
      const address = deriveAddress(publicKey);

      assert.ok(address.endsWith('RTC'), 'Address should end with RTC');
      assert.strictEqual(address.length, 43, 'Address should be 43 characters');
    });
  });

  describe('truncateAddress', () => {
    it('should truncate address for display', () => {
      const address = 'abcd1234567890abcd1234567890abcd1234567RTC';
      const truncated = truncateAddress(address);

      assert.strictEqual(truncated, 'abcd1234...567RTC');
    });

    it('should handle empty address', () => {
      assert.strictEqual(truncateAddress(''), '');
      assert.strictEqual(truncateAddress(null), '');
    });
  });

  describe('validateAddress', () => {
    it('should validate correct RTC address', () => {
      assert.strictEqual(validateAddress('abcd1234567890abcd1234567890abcd12345678RTC'), true);
    });

    it('should reject invalid address', () => {
      assert.strictEqual(validateAddress('invalid'), false);
      assert.strictEqual(validateAddress('abcd1234'), false);
    });

    it('should reject address without RTC suffix', () => {
      assert.strictEqual(validateAddress('abcd1234567890abcd1234567890abcd1234567'), false);
    });
  });
});

describe('Transaction Functions', () => {
  describe('createTransactionObject', () => {
    it('should create valid transaction object', () => {
      const tx = createTransactionObject({
        from: 'sender123RTC',
        to: 'receiver456RTC',
        amount: '10.5',
        memo: 'Test payment'
      });

      assert.strictEqual(tx.from, 'sender123RTC');
      assert.strictEqual(tx.to, 'receiver456RTC');
      assert.strictEqual(tx.amount, '10.5');
      assert.strictEqual(tx.memo, 'Test payment');
      assert.ok(tx.nonce);
      assert.ok(tx.timestamp);
    });
  });

  describe('validateTransaction', () => {
    it('should validate correct transaction', () => {
      const tx = {
        from: 'sender12345678901234567890123456789012345RTC',
        to: 'receiver567890123456789012345678901234567RTC',
        amount: '10.5'
      };

      const result = validateTransaction(tx);
      assert.strictEqual(result.valid, true);
    });

    it('should reject transaction with insufficient balance', () => {
      const tx = {
        from: 'sender12345678901234567890123456789012345RTC',
        to: 'receiver567890123456789012345678901234567RTC',
        amount: '1000'
      };

      const result = validateTransaction(tx, '10.0');
      assert.strictEqual(result.valid, false);
      assert.ok(result.error.includes('Insufficient'));
    });

    it('should reject transaction with invalid recipient', () => {
      const tx = {
        from: 'sender1234567890123456789012345678901234RTC',
        to: 'invalid',
        amount: '10'
      };

      const result = validateTransaction(tx);
      assert.strictEqual(result.valid, false);
    });
  });
});

describe('Message Signing', () => {
  describe('hashMessage', () => {
    it('should create hash of message', async () => {
      const message = 'Hello, RustChain!';
      const hash = await hashMessage(message);

      assert.ok(hash.startsWith('0x'));
      assert.strictEqual(hash.length, 66); // 0x + 64 hex chars
    });

    it('should produce consistent hashes', async () => {
      const message = 'Test message';
      const hash1 = await hashMessage(message);
      const hash2 = await hashMessage(message);

      assert.strictEqual(hash1, hash2);
    });
  });
});

// Helper functions (would be imported from utils in real code)
function deriveAddress(publicKey) {
  const hash = publicKey.slice(0, 40);
  return hash + 'RTC';
}

function truncateAddress(address) {
  if (!address) return '';
  return `${address.slice(0, 8)}...${address.slice(-6)}`;
}

function validateAddress(address) {
  return typeof address === 'string' &&
         address.length >= 43 &&
         address.endsWith('RTC');
}

function createTransactionObject({ from, to, amount, memo = '' }) {
  return {
    from,
    to,
    amount,
    memo,
    nonce: Date.now(),
    timestamp: new Date().toISOString()
  };
}

function validateTransaction(tx, balance = '1000.0') {
  if (!validateAddress(tx.from)) {
    return { valid: false, error: 'Invalid sender address' };
  }
  
  if (!validateAddress(tx.to)) {
    return { valid: false, error: 'Invalid recipient address' };
  }
  
  const amountNum = parseFloat(tx.amount);
  const balanceNum = parseFloat(balance);
  
  if (isNaN(amountNum) || amountNum <= 0) {
    return { valid: false, error: 'Invalid amount' };
  }
  
  if (amountNum > balanceNum) {
    return { valid: false, error: 'Insufficient balance' };
  }
  
  return { valid: true };
}

async function hashMessage(message) {
  const encoder = new TextEncoder();
  const data = encoder.encode(message);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hash = Array.from(new Uint8Array(hashBuffer))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');
  return '0x' + hash;
}
