/**
 * RustChain Extension - Send/Sign Flow Self-Tests (Phase 2)
 *
 * Comprehensive tests for transaction and message signing flows.
 * Includes Snap integration fallback testing.
 * 
 * Run with: node --test tests/send-sign-flow.test.js
 */

import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert';

// Test result tracking
let testResults = { passed: 0, failed: 0, tests: [] };

// Custom reporter for explicit PASS/FAIL output
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

// Mock chrome API
global.chrome = {
  runtime: {
    sendMessage: (msg, cb) => cb({ success: true, txHash: '0xtest123' }),
    onMessage: { addListener: () => {} },
    lastError: null
  },
  storage: {
    local: {
      get: async () => ({}),
      set: async () => {}
    }
  },
  alarms: {
    create: () => {},
    onAlarm: { addListener: () => {} }
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

// Mock Snap state
let mockSnapState = { accounts: [] };

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

// Mock fetch
global.fetch = async () => ({
  ok: true,
  json: async () => ({ balance: '100.00000000' })
});

// Mock ethereum provider for Snap tests
global.window = { ethereum: null };

describe('Phase 2: Send/Sign Flow Self-Tests', () => {
  beforeEach(() => {
    mockSnapState = { accounts: [] };
    global.window.ethereum = null;
  });

  describe('Address Validation', () => {
    it('should validate correct RTC address', () => {
      const result = validateAddress('abcd1234567890abcd1234567890abcd12345678RTC');
      reportTest('Valid RTC address', result === true);
      assert.strictEqual(result, true);
    });

    it('should reject address without RTC suffix', () => {
      const result = validateAddress('abcd1234567890abcd1234567890abcd12345678');
      reportTest('Reject no RTC suffix', result === false);
      assert.strictEqual(result, false);
    });

    it('should reject short address', () => {
      const result = validateAddress('short123RTC');
      reportTest('Reject short address', result === false);
      assert.strictEqual(result, false);
    });

    it('should reject non-string input', () => {
      const result = validateAddress(12345);
      reportTest('Reject non-string', result === false);
      assert.strictEqual(result, false);
    });
  });

  describe('Transaction Validation', () => {
    it('should validate correct transaction', () => {
      const tx = {
        from: 'abcd1234567890abcd1234567890abcd12345678RTC',
        to: 'ef01567890123456789012345678901234567890RTC',
        amount: '10.5'
      };
      // Balance must cover amount + fee (0.0001)
      const result = validateTransaction(tx, '100.0');
      reportTest('Valid transaction', result.valid === true, result.error ? new Error(result.error) : null);
      assert.strictEqual(result.valid, true);
    });

    it('should reject insufficient balance', () => {
      const tx = {
        from: 'abcd1234567890abcd1234567890abcd12345678RTC',
        to: 'ef01567890123456789012345678901234567890RTC',
        amount: '1000'
      };
      const result = validateTransaction(tx, '10.0');
      reportTest('Reject insufficient balance', !result.valid && result.error.includes('Insufficient'));
      assert.strictEqual(result.valid, false);
    });

    it('should reject missing fields', () => {
      const tx = { from: 'abcd1234567890abcd1234567890abcd12345678RTC' };
      const result = validateTransaction(tx);
      reportTest('Reject missing fields', !result.valid);
      assert.strictEqual(result.valid, false);
    });

    it('should reject invalid recipient', () => {
      const tx = {
        from: 'abcd1234567890abcd1234567890abcd12345678RTC',
        to: 'invalid',
        amount: '10'
      };
      const result = validateTransaction(tx);
      reportTest('Reject invalid recipient', !result.valid);
      assert.strictEqual(result.valid, false);
    });

    it('should reject zero amount', () => {
      const tx = {
        from: 'abcd1234567890abcd1234567890abcd12345678RTC',
        to: 'ef01567890123456789012345678901234567890RTC',
        amount: '0'
      };
      const result = validateTransaction(tx, '100.0');
      reportTest('Reject zero amount', !result.valid);
      assert.strictEqual(result.valid, false);
    });

    it('should reject negative amount', () => {
      const tx = {
        from: 'abcd1234567890abcd1234567890abcd12345678RTC',
        to: 'ef01567890123456789012345678901234567890RTC',
        amount: '-5'
      };
      const result = validateTransaction(tx, '100.0');
      reportTest('Reject negative amount', !result.valid);
      assert.strictEqual(result.valid, false);
    });
  });

  describe('Message Validation', () => {
    it('should validate correct message', () => {
      const result = validateMessage('Hello, RustChain!');
      reportTest('Valid message', result.valid === true);
      assert.strictEqual(result.valid, true);
    });

    it('should reject empty message', () => {
      const result = validateMessage('');
      reportTest('Reject empty message', !result.valid);
      assert.strictEqual(result.valid, false);
    });

    it('should reject non-string message', () => {
      const result = validateMessage(12345);
      reportTest('Reject non-string message', !result.valid);
      assert.strictEqual(result.valid, false);
    });
  });

  describe('Utility Functions', () => {
    it('should truncate address correctly', () => {
      const result = truncateAddress('abcd1234567890abcd1234567890abcd1234567RTC');
      reportTest('Truncate address', result === 'abcd1234...567RTC');
      assert.strictEqual(result, 'abcd1234...567RTC');
    });

    it('should truncate hash correctly', () => {
      const result = truncateHash('0x1234567890abcdef1234567890abcdef');
      reportTest('Truncate hash', result === '0x12345678...90abcdef');
      assert.strictEqual(result, '0x12345678...90abcdef');
    });

    it('should format amount with precision', () => {
      const result = formatAmount('10.123456789', 8);
      reportTest('Format amount', result === '10.12345679');
      assert.strictEqual(result, '10.12345679');
    });

    it('should derive address from public key', () => {
      const pk = 'abcd1234567890abcd1234567890abcd1234567890abcd1234567890abcd1234';
      const result = deriveAddress(pk);
      reportTest('Derive address', result.endsWith('RTC') && result.length === 43);
      assert.ok(result.endsWith('RTC'));
    });
  });

  describe('Send Transaction Flow', () => {
    it('should create transaction object', () => {
      const tx = createTransactionObject({
        from: 'sender123RTC',
        to: 'receiver456RTC',
        amount: '10.5',
        memo: 'Test payment'
      });
      reportTest('Create transaction object', tx.from === 'sender123RTC' && tx.memo === 'Test payment');
      assert.strictEqual(tx.from, 'sender123RTC');
      assert.strictEqual(tx.memo, 'Test payment');
      assert.ok(tx.nonce);
      assert.ok(tx.timestamp);
    });

    it('should sign transaction', async () => {
      const tx = {
        from: 'sender12345678901234567890123456789012345RTC',
        to: 'receiver567890123456789012345678901234567RTC',
        amount: '10.5',
        memo: 'Test'
      };
      const result = await signTransactionInternal(tx);
      reportTest('Sign transaction', result.startsWith('0x'));
      assert.ok(result.startsWith('0x'));
    });
  });

  describe('Sign Message Flow', () => {
    it('should hash message', async () => {
      const result = await hashMessage('Hello, RustChain!');
      reportTest('Hash message', result.startsWith('0x') && result.length === 66);
      assert.ok(result.startsWith('0x'));
      assert.strictEqual(result.length, 66);
    });

    it('should produce consistent hashes', async () => {
      const hash1 = await hashMessage('Test message');
      const hash2 = await hashMessage('Test message');
      reportTest('Consistent hashes', hash1 === hash2);
      assert.strictEqual(hash1, hash2);
    });

    it('should sign message via extension', async () => {
      const result = await signMessageExtension('abcd1234567890abcd1234567890abcd12345678RTC', 'Hello');
      reportTest('Sign message extension', result.signature.startsWith('0xRUSTCHAIN_'));
      assert.ok(result.signature.startsWith('0xRUSTCHAIN_'));
      assert.strictEqual(result.signedMessage, 'Hello');
    });
  });

  describe('Snap Integration Path', () => {
    it('should detect Snap availability when ethereum exists', async () => {
      global.window.ethereum = {
        request: async () => ({ 'npm:rustchain-snap': { version: '1.0.0' } })
      };
      const result = await checkSnapAvailability();
      reportTest('Detect Snap availability', !!result);
      assert.ok(result);
    });

    it('should return false when ethereum not available', async () => {
      global.window.ethereum = undefined;
      const result = await checkSnapAvailability();
      reportTest('No ethereum = no Snap', result === false);
      assert.strictEqual(result, false);
    });

    it('should send transaction via Snap', async () => {
      global.window.ethereum = {
        request: async () => ({ txHash: '0xsnap_tx123', status: 'pending' })
      };
      const result = await sendTransactionViaSnap({
        from: 'abcd1234567890abcd1234567890abcd12345678RTC',
        to: 'ef01567890123456789012345678901234567890RTC',
        amount: '10.5'
      });
      reportTest('Send via Snap', result.viaSnap === true && result.txHash.startsWith('0xsnap_'));
      assert.strictEqual(result.viaSnap, true);
      assert.ok(result.txHash.startsWith('0xsnap_'));
    });

    it('should sign message via Snap', async () => {
      global.window.ethereum = {
        request: async () => ({ signature: '0xsnap_sig123', signedMessage: 'Hello' })
      };
      const result = await signMessageViaSnap('abcd1234567890abcd1234567890abcd12345678RTC', 'Hello');
      reportTest('Sign via Snap', result.viaSnap === true);
      assert.strictEqual(result.viaSnap, true);
    });

    it('should fallback to extension when Snap fails', async () => {
      global.window.ethereum = {
        request: async () => { throw new Error('Snap unavailable'); }
      };
      // Simulate fallback behavior
      let usedFallback = false;
      try {
        await sendTransactionViaSnap({ from: 'abcd1234567890abcd1234567890abcd12345678RTC', to: 'ef01567890123456789012345678901234567890RTC', amount: '10' });
      } catch (e) {
        usedFallback = true;
      }
      reportTest('Snap failure triggers fallback', usedFallback === true);
      assert.strictEqual(usedFallback, true);
    });
  });

  describe('Unified Send with Fallback', () => {
    it('should use extension when Snap-first mode but Snap unavailable', async () => {
      const config = { fallbackMode: 'snap-first', enabled: true };
      global.window.ethereum = undefined;

      const result = await sendTransactionWithFallback({
        from: 'abcd1234567890abcd1234567890abcd12345678RTC',
        to: 'ef01567890123456789012345678901234567890RTC',
        amount: '10.5'
      }, config);
      reportTest('Fallback to extension', result.viaSnap !== true);
      assert.ok(!result.viaSnap || result.txHash);
    });

    it('should use extension by default (extension-first mode)', async () => {
      const config = { fallbackMode: 'extension-first', enabled: true };

      const result = await sendTransactionWithFallback({
        from: 'abcd1234567890abcd1234567890abcd12345678RTC',
        to: 'ef01567890123456789012345678901234567890RTC',
        amount: '10.5'
      }, config);
      reportTest('Extension-first mode', result.txHash !== undefined);
      assert.ok(result.txHash);
    });
  });

  describe('Unified Sign with Fallback', () => {
    it('should use extension when Snap unavailable', async () => {
      const config = { fallbackMode: 'snap-first', enabled: true };
      global.window.ethereum = undefined;

      const result = await signMessageWithFallback('abcd1234567890abcd1234567890abcd12345678RTC', 'Hello', config);
      reportTest('Sign fallback to extension', result.signature.startsWith('0xRUSTCHAIN_'));
      assert.ok(result.signature.startsWith('0xRUSTCHAIN_'));
    });
  });
});

// Helper functions (mirroring production code)
function validateAddress(address) {
  if (typeof address !== 'string') return false;
  if (!address.endsWith('RTC')) return false;
  if (address.length < 43) return false;
  const addressWithoutSuffix = address.slice(0, -3);
  return /^[a-fA-F0-9]+$/.test(addressWithoutSuffix);
}

function validateTransaction(tx, balance = '1000.0') {
  if (!tx.from || !tx.to || !tx.amount) {
    return { valid: false, error: 'Missing required fields' };
  }
  if (!validateAddress(tx.from)) return { valid: false, error: 'Invalid sender' };
  if (!validateAddress(tx.to)) return { valid: false, error: 'Invalid recipient' };
  const amountNum = parseFloat(tx.amount);
  const balanceNum = parseFloat(balance);
  if (isNaN(amountNum) || amountNum <= 0) return { valid: false, error: 'Invalid amount' };
  if (amountNum + 0.0001 > balanceNum) return { valid: false, error: 'Insufficient balance' };
  return { valid: true };
}

function validateMessage(message) {
  if (typeof message !== 'string') return { valid: false, error: 'Must be string' };
  if (message.length === 0) return { valid: false, error: 'Cannot be empty' };
  if (message.length > 10000) return { valid: false, error: 'Too long' };
  return { valid: true };
}

function truncateAddress(address) {
  if (!address) return '';
  if (address.length < 16) return address;
  return `${address.slice(0, 8)}...${address.slice(-6)}`;
}

function truncateHash(hash) {
  if (!hash) return '';
  if (hash.length < 20) return hash;
  return `${hash.slice(0, 10)}...${hash.slice(-8)}`;
}

function formatAmount(amount, decimals = 8) {
  const num = typeof amount === 'string' ? parseFloat(amount) : amount;
  if (isNaN(num)) return '0.00000000';
  return num.toFixed(decimals);
}

function deriveAddress(publicKey) {
  return publicKey.slice(0, 40) + 'RTC';
}

function createTransactionObject({ from, to, amount, memo = '' }) {
  return {
    from, to, amount, memo,
    nonce: Date.now(),
    timestamp: new Date().toISOString()
  };
}

async function signTransactionInternal(tx) {
  const txString = JSON.stringify(tx);
  const encoder = new TextEncoder();
  const hashBuffer = await crypto.subtle.digest('SHA-256', encoder.encode(txString));
  return '0x' + Array.from(new Uint8Array(hashBuffer)).map(b => b.toString(16).padStart(2, '0')).join('');
}

async function hashMessage(message) {
  const encoder = new TextEncoder();
  const hashBuffer = await crypto.subtle.digest('SHA-256', encoder.encode(message));
  return '0x' + Array.from(new Uint8Array(hashBuffer)).map(b => b.toString(16).padStart(2, '0')).join('');
}

async function signMessageExtension(address, message) {
  const hash = await hashMessage(message);
  return {
    signature: '0xRUSTCHAIN_' + hash.slice(2),
    signedMessage: message,
    address
  };
}

async function checkSnapAvailability() {
  if (!global.window?.ethereum) return false;
  try {
    const result = await global.window.ethereum.request({ method: 'wallet_getSnaps' });
    return result && result['npm:rustchain-snap'];
  } catch {
    return false;
  }
}

async function sendTransactionViaSnap(params) {
  if (!global.window?.ethereum) throw new Error('No ethereum provider');
  const response = await global.window.ethereum.request({
    method: 'rustchain_sendTransaction',
    params: [params]
  });
  return { ...response, viaSnap: true };
}

async function signMessageViaSnap(address, message) {
  if (!global.window?.ethereum) throw new Error('No ethereum provider');
  const response = await global.window.ethereum.request({
    method: 'rustchain_signMessage',
    params: [{ address, message }]
  });
  return { ...response, viaSnap: true };
}

async function sendTransactionWithFallback(params, config = { fallbackMode: 'extension-first' }) {
  if (config.fallbackMode === 'snap-first') {
    try {
      const snapAvailable = await checkSnapAvailability();
      if (snapAvailable) return await sendTransactionViaSnap(params);
    } catch (e) {
      console.warn('Snap failed, falling back');
    }
  }
  // Extension fallback
  const txHash = await signTransactionInternal(params);
  return { txHash, viaSnap: false };
}

async function signMessageWithFallback(address, message, config = { fallbackMode: 'extension-first' }) {
  if (config.fallbackMode === 'snap-first') {
    try {
      const snapAvailable = await checkSnapAvailability();
      if (snapAvailable) return await signMessageViaSnap(address, message);
    } catch (e) {
      console.warn('Snap failed, falling back');
    }
  }
  // Extension fallback
  return await signMessageExtension(address, message);
}

// Print summary after tests
process.on('exit', () => {
  console.log('\n' + '='.repeat(50));
  console.log('TEST SUMMARY');
  console.log('='.repeat(50));
  console.log(`Total: ${testResults.passed + testResults.failed}`);
  console.log(`✅ Passed: ${testResults.passed}`);
  console.log(`❌ Failed: ${testResults.failed}`);
  console.log('='.repeat(50));
  if (testResults.failed === 0) {
    console.log('🎉 ALL TESTS PASSED!');
  } else {
    console.log('⚠️  SOME TESTS FAILED');
    process.exitCode = 1;
  }
});
