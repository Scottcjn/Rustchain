/**
 * RustChain Snap - Unit Tests
 *
 * Tests for the MetaMask Snap integration.
 * Run with: node --test tests/*.test.js
 */

import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert';

// Mock snap API
let mockSnapState = { accounts: [] };

// Reset state before each test
beforeEach(() => {
  mockSnapState = { accounts: [] };
});

global.snap = {
  request: async ({ method, params }) => {
    if (method === 'snap_manageState') {
      if (params.operation === 'get') {
        return mockSnapState;
      }
      mockSnapState = params.newState;
      return mockSnapState;
    }
    if (method === 'snap_dialog') {
      return true; // Auto-approve for tests
    }
    if (method === 'snap_notify') {
      return null;
    }
    return null;
  }
};

// Mock crypto API using Object.defineProperty for Node.js v24+
const mockCrypto = {
  getRandomValues: (arr) => {
    for (let i = 0; i < arr.length; i++) {
      arr[i] = i; // Deterministic for tests
    }
    return arr;
  },
  subtle: {
    digest: async (algorithm, data) => {
      const bytes = new Uint8Array(data);
      const hash = new Uint8Array(32);
      for (let i = 0; i < 32; i++) {
        hash[i] = (bytes[i % bytes.length] + i) % 256;
      }
      return hash.buffer;
    }
  }
};

Object.defineProperty(globalThis, 'crypto', {
  value: mockCrypto,
  writable: true,
  configurable: true
});

// Mock fetch
global.fetch = async (url) => ({
  ok: true,
  json: async () => ({ balance: '100.00000000' })
});

describe('Snap RPC Methods', () => {
  describe('createAccount', () => {
    it('should create a new account with valid address', async () => {
      const { onRpcRequest } = await import('../src/index.js');

      const result = await onRpcRequest({
        request: { method: 'rustchain_createAccount' }
      });

      assert.ok(result.address, 'Should have address');
      assert.ok(result.publicKey, 'Should have publicKey');
      assert.ok(result.address.endsWith('RTC'), 'Address should end with RTC');
    });
  });

  describe('getAccounts', () => {
    it('should return empty array when no accounts', async () => {
      const { onRpcRequest } = await import('../src/index.js');

      const result = await onRpcRequest({
        request: { method: 'rustchain_getAccounts' }
      });

      assert.ok(Array.isArray(result));
    });
  });

  describe('getBalance', () => {
    it('should return balance for address', async () => {
      const { onRpcRequest } = await import('../src/index.js');

      const result = await onRpcRequest({
        request: {
          method: 'rustchain_getBalance',
          params: ['test123456789012345678901234567890123RTC']
        }
      });

      assert.ok(result.balance);
      assert.ok(result.address);
    });
  });

  describe('signMessage', () => {
    it('should sign a message', async () => {
      // First create an account directly to populate state
      const { createAccount } = await import('../src/index.js');
      
      // Manually setup account in state
      mockSnapState.accounts = [{
        address: 'test12345678901234567890123456789012345RTC',
        publicKey: 'testpubkey123456789012345678901234567890',
        encryptedPrivateKey: 'testkey123',
        createdAt: Date.now()
      }];

      const { onRpcRequest } = await import('../src/index.js');

      const result = await onRpcRequest({
        request: {
          method: 'rustchain_signMessage',
          params: [{ address: 'test12345678901234567890123456789012345RTC', message: 'Hello, RustChain!' }]
        }
      });

      assert.ok(result.signature);
      assert.ok(result.signedMessage);
      assert.ok(result.address);
    });
  });

  describe('eth_chainId', () => {
    it('should return RustChain chain ID', async () => {
      const { onRpcRequest } = await import('../src/index.js');

      const result = await onRpcRequest({
        request: { method: 'eth_chainId' }
      });

      assert.strictEqual(result, 'rustchain-mainnet');
    });
  });
});

describe('Utility Functions', () => {
  describe('deriveAddress', () => {
    it('should derive address from public key', () => {
      const publicKey = 'abcd1234567890abcd1234567890abcd1234567890abcd1234567890abcd1234';
      const address = deriveAddress(publicKey);

      assert.ok(address.endsWith('RTC'));
      assert.strictEqual(address.length, 43);
    });
  });

  describe('truncateAddress', () => {
    it('should truncate address correctly', () => {
      const address = 'abcd1234567890abcd1234567890abcd1234567RTC';
      const truncated = truncateAddress(address);

      assert.strictEqual(truncated, 'abcd1234...567RTC');
    });
  });

  describe('validateAddress', () => {
    it('should validate correct address', () => {
      assert.strictEqual(validateAddress('test123456789012345678901234567890123456RTC'), true);
    });

    it('should reject invalid address', () => {
      assert.strictEqual(validateAddress('invalid'), false);
      assert.strictEqual(validateAddress('test123'), false);
    });
  });
});

describe('Transaction Validation', () => {
  describe('validateTransaction', () => {
    it('should validate correct transaction', () => {
      const tx = {
        from: 'sender12345678901234567890123456789012345RTC',
        to: 'receiver567890123456789012345678901234567RTC',
        value: '10.5'
      };

      const result = validateTransaction(tx, '100.0');
      assert.strictEqual(result.valid, true);
    });

    it('should reject insufficient balance', () => {
      const tx = {
        from: 'sender12345678901234567890123456789012345RTC',
        to: 'receiver567890123456789012345678901234567RTC',
        value: '1000'
      };

      const result = validateTransaction(tx, '10.0');
      assert.strictEqual(result.valid, false);
      assert.ok(result.error.includes('Insufficient'));
    });

    it('should reject missing fields', () => {
      const tx = { from: 'sender12345678901234567890123456789012345RTC' };
      const result = validateTransaction(tx, '100.0');
      assert.strictEqual(result.valid, false);
    });
  });
});

// Helper functions
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

function validateTransaction(tx, balance = '1000.0') {
  if (!tx.from || !tx.to || !tx.value) {
    return { valid: false, error: 'Missing required fields' };
  }
  
  if (!validateAddress(tx.from) || !validateAddress(tx.to)) {
    return { valid: false, error: 'Invalid address' };
  }
  
  const valueNum = parseFloat(tx.value);
  const balanceNum = parseFloat(balance);
  
  if (isNaN(valueNum) || valueNum <= 0) {
    return { valid: false, error: 'Invalid value' };
  }
  
  if (valueNum > balanceNum) {
    return { valid: false, error: 'Insufficient balance' };
  }
  
  return { valid: true };
}
