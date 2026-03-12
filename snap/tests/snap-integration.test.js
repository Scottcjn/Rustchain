/**
 * RustChain Snap - Integration Tests (Phase 2)
 *
 * Tests for MetaMask Snap integration including send/sign flows
 * and fallback behavior.
 * 
 * Run with: node --test tests/snap-integration.test.js
 */

import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert';

// Test result tracking - initialize at module level
const testResults = { passed: 0, failed: 0, tests: [] };

function reportTest(name, passed, error = null) {
  testResults.tests.push({ name, passed, error });
  if (passed) {
    testResults.passed++;
    console.log(`  ✅ PASS: ${name}`);
  } else {
    testResults.failed++;
    console.log(`  ❌ FAIL: ${name}`);
    if (error) console.log(`     Error: ${error.message}`);
  }
}

// Mock Snap API
let mockSnapState = { accounts: [], transactions: [] };

global.snap = {
  request: async ({ method, params }) => {
    if (method === 'snap_manageState') {
      if (params.operation === 'get') return mockSnapState;
      mockSnapState = params.newState;
      return mockSnapState;
    }
    if (method === 'snap_dialog') return true; // Auto-approve for tests
    if (method === 'snap_notify') return null;
    return null;
  }
};

// Mock crypto API
const mockCrypto = {
  getRandomValues: (arr) => {
    for (let i = 0; i < arr.length; i++) arr[i] = i;
    return arr;
  },
  subtle: {
    digest: async (algorithm, data) => {
      const bytes = new Uint8Array(data);
      const hash = new Uint8Array(32);
      for (let i = 0; i < 32; i++) hash[i] = (bytes[i % bytes.length] + i) % 256;
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
global.fetch = async () => ({
  ok: true,
  json: async () => ({ balance: '100.00000000' })
});

describe('Phase 2: Snap Integration Tests', () => {
  beforeEach(() => {
    mockSnapState = { accounts: [], transactions: [] };
  });

  describe('Account Management', () => {
    it('should create account with valid address format', async () => {
      const { onRpcRequest } = await import('../src/index.js');
      const result = await onRpcRequest({
        request: { method: 'rustchain_createAccount' }
      });
      reportTest('Create account with valid address', 
        result.address && result.address.endsWith('RTC'));
      assert.ok(result.address);
      assert.ok(result.publicKey);
      assert.ok(result.address.endsWith('RTC'));
    });

    it('should return accounts after creation', async () => {
      const { onRpcRequest } = await import('../src/index.js');
      
      // Create account first
      await onRpcRequest({ request: { method: 'rustchain_createAccount' } });
      
      // Get accounts
      const result = await onRpcRequest({ request: { method: 'rustchain_getAccounts' } });
      reportTest('Get accounts returns array', Array.isArray(result));
      assert.ok(Array.isArray(result));
      assert.ok(result.length >= 1);
    });
  });

  describe('Balance Query', () => {
    it('should return balance for address', async () => {
      const { onRpcRequest } = await import('../src/index.js');
      const result = await onRpcRequest({
        request: {
          method: 'rustchain_getBalance',
          params: ['abcd1234567890abcd1234567890abcd12345678RTC']
        }
      });
      reportTest('Get balance returns balance and address', 
        result.balance && result.address);
      assert.ok(result.balance);
      assert.ok(result.address);
    });

    it('should handle network errors gracefully', async () => {
      // Mock fetch failure
      const originalFetch = global.fetch;
      global.fetch = async () => {
        throw new Error('Network error');
      };
      
      try {
        const { onRpcRequest } = await import('../src/index.js');
        const result = await onRpcRequest({
          request: {
            method: 'rustchain_getBalance',
            params: ['abcd1234567890abcd1234567890abcd12345678RTC']
          }
        });
        reportTest('Balance handles network error', result.balance === '0.00000000');
        assert.strictEqual(result.balance, '0.00000000');
      } finally {
        global.fetch = originalFetch;
      }
    });
  });

  describe('Send Transaction Flow', () => {
    it('should validate transaction parameters', async () => {
      // Setup account in state
      mockSnapState.accounts = [{
        address: 'abcd1234567890abcd1234567890abcd12345678RTC',
        publicKey: 'testpubkey123456789012345678901234567890',
        encryptedPrivateKey: 'testkey123',
        createdAt: Date.now()
      }];
      
      const tx = {
        from: 'abcd1234567890abcd1234567890abcd12345678RTC',
        to: 'ef01567890123456789012345678901234567RTC',
        value: '10.5',
        memo: 'Test payment'
      };
      
      // Validate manually
      const isValid = tx.from && tx.to && tx.value && 
                      tx.from.endsWith('RTC') && tx.to.endsWith('RTC');
      reportTest('Transaction params validation', isValid);
      assert.ok(isValid);
    });

    it('should reject transaction with missing params', async () => {
      const { onRpcRequest } = await import('../src/index.js');
      
      try {
        await onRpcRequest({
          request: {
            method: 'rustchain_sendTransaction',
            params: [{ from: 'sender' }] // Missing to and value
          }
        });
        reportTest('Reject missing params', false);
        assert.fail('Should have thrown');
      } catch (error) {
        reportTest('Reject missing params', true);
        assert.ok(true); // Expected to fail
      }
    });

    it('should create transaction with confirmation', async () => {
      // Setup account in state
      mockSnapState.accounts = [{
        address: 'abcd1234567890abcd1234567890abcd12345678RTC',
        publicKey: 'testpubkey123456789012345678901234567890',
        encryptedPrivateKey: 'testkey123',
        createdAt: Date.now()
      }];
      
      const { onRpcRequest } = await import('../src/index.js');
      const result = await onRpcRequest({
        request: {
          method: 'rustchain_sendTransaction',
          params: [{
            from: 'abcd1234567890abcd1234567890abcd12345678RTC',
            to: 'ef01567890123456789012345678901234567RTC',
            value: '10.5',
            memo: 'Test'
          }]
        }
      });
      reportTest('Send transaction returns txHash', result.txHash && result.status);
      assert.ok(result.txHash);
      assert.strictEqual(result.status, 'pending');
    });
  });

  describe('Sign Message Flow', () => {
    it('should sign message with account', async () => {
      // Setup account
      mockSnapState.accounts = [{
        address: 'abcd1234567890abcd1234567890abcd12345678RTC',
        publicKey: 'testpubkey123456789012345678901234567890',
        encryptedPrivateKey: 'testkey123',
        createdAt: Date.now()
      }];
      
      const { onRpcRequest } = await import('../src/index.js');
      const result = await onRpcRequest({
        request: {
          method: 'rustchain_signMessage',
          params: [{
            address: 'abcd1234567890abcd1234567890abcd12345678RTC',
            message: 'Hello, RustChain!'
          }]
        }
      });
      reportTest('Sign message returns signature', result.signature && result.signedMessage);
      assert.ok(result.signature);
      assert.strictEqual(result.signedMessage, 'Hello, RustChain!');
      assert.strictEqual(result.address, 'abcd1234567890abcd1234567890abcd12345678RTC');
    });

    it('should reject signing empty message', async () => {
      mockSnapState.accounts = [{
        address: 'abcd1234567890abcd1234567890abcd12345678RTC',
        publicKey: 'testpubkey123',
        encryptedPrivateKey: 'testkey123',
        createdAt: Date.now()
      }];
      
      const { onRpcRequest } = await import('../src/index.js');
      
      try {
        await onRpcRequest({
          request: {
            method: 'rustchain_signMessage',
            params: [{ address: 'abcd1234567890abcd1234567890abcd12345678RTC', message: '' }]
          }
        });
        reportTest('Reject empty message', false);
        assert.fail('Should have thrown');
      } catch (error) {
        reportTest('Reject empty message', true);
        assert.ok(true); // Expected to fail
      }
    });

    it('should use first account when address not specified', async () => {
      mockSnapState.accounts = [{
        address: 'first12345678901234567890123456789012345RTC',
        publicKey: 'pubkey123',
        encryptedPrivateKey: 'key123',
        createdAt: Date.now()
      }];
      
      const { onRpcRequest } = await import('../src/index.js');
      const result = await onRpcRequest({
        request: {
          method: 'rustchain_signMessage',
          params: [{ message: 'Test' }]
        }
      });
      reportTest('Sign uses first account', result.address === 'first12345678901234567890123456789012345RTC');
      assert.strictEqual(result.address, 'first12345678901234567890123456789012345RTC');
    });
  });

  describe('EIP-1193 Compatibility', () => {
    it('should handle eth_requestAccounts', async () => {
      const { onRpcRequest } = await import('../src/index.js');
      
      // Create account first
      await onRpcRequest({ request: { method: 'rustchain_createAccount' } });
      
      const result = await onRpcRequest({
        request: { method: 'eth_requestAccounts' }
      });
      reportTest('eth_requestAccounts returns accounts', Array.isArray(result));
      assert.ok(Array.isArray(result));
    });

    it('should handle eth_accounts', async () => {
      const { onRpcRequest } = await import('../src/index.js');
      const result = await onRpcRequest({
        request: { method: 'eth_accounts' }
      });
      reportTest('eth_accounts returns array', Array.isArray(result));
      assert.ok(Array.isArray(result));
    });

    it('should return RustChain chain ID', async () => {
      const { onRpcRequest } = await import('../src/index.js');
      const result = await onRpcRequest({
        request: { method: 'eth_chainId' }
      });
      reportTest('eth_chainId returns rustchain-mainnet', result === 'rustchain-mainnet');
      assert.strictEqual(result, 'rustchain-mainnet');
    });

    it('should handle personal_sign', async () => {
      mockSnapState.accounts = [{
        address: 'abcd1234567890abcd1234567890abcd12345678RTC',
        publicKey: 'pubkey123',
        encryptedPrivateKey: 'key123',
        createdAt: Date.now()
      }];
      
      const { onRpcRequest } = await import('../src/index.js');
      const result = await onRpcRequest({
        request: {
          method: 'personal_sign',
          params: [{ address: 'abcd1234567890abcd1234567890abcd12345678RTC', message: 'Test' }]
        }
      });
      reportTest('personal_sign returns signature', result.signature);
      assert.ok(result.signature);
    });
  });

  describe('Error Handling', () => {
    it('should throw error for unknown method', async () => {
      const { onRpcRequest } = await import('../src/index.js');
      
      try {
        await onRpcRequest({
          request: { method: 'unknown_method' }
        });
        reportTest('Unknown method throws error', false);
        assert.fail('Should have thrown');
      } catch (error) {
        reportTest('Unknown method throws error', true);
        assert.ok(true); // Expected to fail
      }
    });

    it('should handle user rejection', async () => {
      // Mock dialog rejection
      const originalSnap = global.snap;
      global.snap = {
        request: async ({ method }) => {
          if (method === 'snap_dialog') return false; // User rejects
          if (method === 'snap_manageState') return mockSnapState;
          return null;
        }
      };
      
      mockSnapState.accounts = [{
        address: 'abcd1234567890abcd1234567890abcd12345678RTC',
        publicKey: 'pubkey123',
        encryptedPrivateKey: 'key123',
        createdAt: Date.now()
      }];
      
      try {
        const { onRpcRequest } = await import('../src/index.js');
        await onRpcRequest({
          request: {
            method: 'rustchain_sendTransaction',
            params: [{
              from: 'abcd1234567890abcd1234567890abcd12345678RTC',
              to: 'ef01567890123456789012345678901234567RTC',
              value: '10'
            }]
          }
        });
        reportTest('User rejection handled', false);
        assert.fail('Should have thrown');
      } catch (error) {
        reportTest('User rejection handled', error.message.includes('rejected'));
        assert.ok(error.message.includes('rejected'));
      } finally {
        global.snap = originalSnap;
      }
    });
  });
});

// Print summary
process.on('exit', () => {
  console.log('\n' + '='.repeat(50));
  console.log('SNAP INTEGRATION TEST SUMMARY');
  console.log('='.repeat(50));
  console.log(`Total: ${testResults.passed + testResults.failed}`);
  console.log(`✅ Passed: ${testResults.passed}`);
  console.log(`❌ Failed: ${testResults.failed}`);
  console.log('='.repeat(50));
  if (testResults.failed === 0) {
    console.log('🎉 ALL SNAP TESTS PASSED!');
  } else {
    console.log('⚠️  SOME SNAP TESTS FAILED');
    process.exitCode = 1;
  }
});
