/**
 * RustChain API Client Tests (Hardened)
 *
 * Issue #785: Security hardening tests
 * - chain_id in signed payload
 * - Numeric validation
 */

import {
  RustChainClient,
  Network,
  dryRunTransfer,
  validateTransactionInput,
} from '../rustchain';
import { generateKeyPair, publicKeyToBase58 } from '../../utils/crypto';

// Mock fetch for testing
global.fetch = jest.fn();

describe('RustChainClient (Hardened)', () => {
  let client: RustChainClient;

  beforeEach(() => {
    client = new RustChainClient(Network.Mainnet);
    jest.clearAllMocks();
  });

  describe('getBalance', () => {
    it('should validate address format before request', async () => {
      await expect(
        client.getBalance('invalid')
      ).rejects.toThrow('Invalid wallet address format');
    });

    it('should fetch balance for valid address', async () => {
      const keyPair = generateKeyPair();
      const address = publicKeyToBase58(keyPair.publicKey);
      
      const mockBalance = {
        miner: address,
        balance: 100000000,
        unlocked: 100000000,
        locked: 0,
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockBalance,
      });

      const balance = await client.getBalance(address);

      expect(balance).toEqual(mockBalance);
    });
  });

  describe('getNetworkInfo and chain_id caching', () => {
    it('should fetch and cache chain_id', async () => {
      const mockInfo = {
        chain_id: 'rustchain-mainnet-v1',
        network: 'mainnet',
        block_height: 1000000,
        peer_count: 50,
        min_fee: 1000,
        version: '2.2.1',
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockInfo,
      });

      const info = await client.getNetworkInfo();

      expect(info.chain_id).toBe('rustchain-mainnet-v1');
      
      // Get chain_id again - should use cached value
      const chainId = await client.getChainId();
      expect(chainId).toBe('rustchain-mainnet-v1');
      
      // Should not have made another fetch
      expect(global.fetch).toHaveBeenCalledTimes(1);
    });

    it('should fetch chain_id on demand', async () => {
      const mockInfo = {
        chain_id: 'rustchain-testnet',
        network: 'testnet',
        block_height: 500000,
        peer_count: 10,
        min_fee: 1000,
        version: '2.2.1',
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockInfo,
      });

      const chainId = await client.getChainId();

      expect(chainId).toBe('rustchain-testnet');
    });
  });

  describe('signTransaction with chain_id', () => {
    it('should include chain_id in signed transaction', async () => {
      const keyPair = generateKeyPair();
      const mockInfo = {
        chain_id: 'rustchain-mainnet',
        network: 'mainnet',
        block_height: 1000000,
        peer_count: 50,
        min_fee: 1000,
        version: '2.2.1',
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockInfo,
      });

      const tx = client.buildTransaction({
        from: publicKeyToBase58(keyPair.publicKey),
        to: publicKeyToBase58(generateKeyPair().publicKey),
        amount: 100,
        fee: 10,
        nonce: 1,
      });

      const signedTx = await client.signTransaction(tx, keyPair);

      expect(signedTx.signature).toBeDefined();
      expect(signedTx.chain_id).toBe('rustchain-mainnet');
    });

    it('should bind signature to chain_id', async () => {
      const keyPair = generateKeyPair();
      
      // Mock different chain_ids
      const mainnetInfo = {
        chain_id: 'rustchain-mainnet',
        network: 'mainnet',
        block_height: 1000000,
        peer_count: 50,
        min_fee: 1000,
        version: '2.2.1',
      };

      const testnetInfo = {
        chain_id: 'rustchain-testnet',
        network: 'testnet',
        block_height: 500000,
        peer_count: 10,
        min_fee: 1000,
        version: '2.2.1',
      };

      (global.fetch as jest.Mock)
        .mockResolvedValueOnce({ ok: true, json: async () => mainnetInfo })
        .mockResolvedValueOnce({ ok: true, json: async () => testnetInfo });

      const tx = client.buildTransaction({
        from: publicKeyToBase58(keyPair.publicKey),
        to: publicKeyToBase58(generateKeyPair().publicKey),
        amount: 100,
        fee: 10,
        nonce: 1,
      });

      // Sign with mainnet chain_id
      const mainnetClient = new RustChainClient(Network.Mainnet);
      const signedMainnet = await mainnetClient.signTransaction(tx, keyPair);

      // Sign with testnet chain_id
      const testnetClient = new RustChainClient(Network.Testnet);
      const signedTestnet = await testnetClient.signTransaction(tx, keyPair);

      // Signatures should be different due to different chain_ids
      expect(signedMainnet.signature).not.toBe(signedTestnet.signature);
      expect(signedMainnet.chain_id).toBe('rustchain-mainnet');
      expect(signedTestnet.chain_id).toBe('rustchain-testnet');
    });
  });

  describe('submitTransaction', () => {
    it('should reject transaction without signature', async () => {
      const tx = {
        from: 'RTC123',
        to: 'RTC456',
        amount: 100,
        fee: 10,
        nonce: 1,
        timestamp: new Date().toISOString(),
      };

      await expect(
        client.submitTransaction(tx as any)
      ).rejects.toThrow('Transaction not signed');
    });

    it('should reject transaction without chain_id', async () => {
      const tx = {
        from: 'RTC123',
        to: 'RTC456',
        amount: 100,
        fee: 10,
        nonce: 1,
        timestamp: new Date().toISOString(),
        signature: 'abc123',
        // Missing chain_id
      };

      await expect(
        client.submitTransaction(tx as any)
      ).rejects.toThrow('missing chain_id');
    });

    it('should submit valid transaction', async () => {
      const mockResponse = {
        tx_hash: 'abc123def456',
        status: 'pending',
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const tx = {
        from: 'RTC123',
        to: 'RTC456',
        amount: 100,
        fee: 10,
        nonce: 1,
        timestamp: new Date().toISOString(),
        signature: 'abc123',
        chain_id: 'rustchain-mainnet',
      };

      const result = await client.submitTransaction(tx as any);

      expect(result).toEqual(mockResponse);
    });
  });

  describe('transfer', () => {
    it('should validate recipient address', async () => {
      const keyPair = generateKeyPair();

      await expect(
        client.transfer(keyPair, 'invalid', 100)
      ).rejects.toThrow('Invalid recipient address');
    });

    it('should perform complete transfer flow', async () => {
      const keyPair = generateKeyPair();
      const recipient = generateKeyPair();
      
      const mockBalance = {
        miner: publicKeyToBase58(keyPair.publicKey),
        balance: 100000000,
        unlocked: 100000000,
        locked: 0,
        nonce: 0,
      };

      const mockInfo = {
        chain_id: 'rustchain-mainnet',
        network: 'mainnet',
        block_height: 1000000,
        peer_count: 50,
        min_fee: 1000,
        version: '2.2.1',
      };

      const mockTxResponse = {
        tx_hash: 'tx123',
        status: 'pending',
      };

      (global.fetch as jest.Mock)
        .mockResolvedValueOnce({ ok: true, json: async () => mockBalance }) // getNonce
        .mockResolvedValueOnce({ ok: true, json: async () => mockInfo }) // getChainId
        .mockResolvedValueOnce({ ok: true, json: async () => mockTxResponse }); // submit

      const result = await client.transfer(keyPair, publicKeyToBase58(recipient.publicKey), 10000000);

      expect(result.tx_hash).toBe('tx123');
    });
  });
});

describe('validateTransactionInput', () => {
  it('should validate valid amount and fee', () => {
    const result = validateTransactionInput('100.5', '1.5');

    expect(result.valid).toBe(true);
    expect(result.errors.length).toBe(0);
    expect(result.parsedAmount).toBe(100.5);
    expect(result.parsedFee).toBe(1.5);
  });

  it('should validate amount without fee', () => {
    const result = validateTransactionInput('50');

    expect(result.valid).toBe(true);
    expect(result.parsedAmount).toBe(50);
    expect(result.parsedFee).toBeUndefined();
  });

  it('should reject invalid amount', () => {
    const result = validateTransactionInput('abc');

    expect(result.valid).toBe(false);
    expect(result.errors.some(e => e.includes('Amount'))).toBe(true);
  });

  it('should reject zero amount', () => {
    const result = validateTransactionInput('0');

    expect(result.valid).toBe(false);
    expect(result.errors.some(e => e.includes('Amount'))).toBe(true);
  });

  it('should reject negative amount', () => {
    const result = validateTransactionInput('-100');

    expect(result.valid).toBe(false);
  });

  it('should reject invalid fee', () => {
    const result = validateTransactionInput('100', 'abc');

    expect(result.valid).toBe(false);
    expect(result.errors.some(e => e.includes('Fee'))).toBe(true);
  });

  it('should accept zero fee', () => {
    const result = validateTransactionInput('100', '0');

    expect(result.valid).toBe(true);
    expect(result.parsedFee).toBe(0);
  });

  it('should reject amount with too many decimals', () => {
    // 1.23456789 has exactly 8 decimal places, which is valid
    // 1.234567890 has 9 decimal places, which should be rejected
    const result = validateTransactionInput('1.234567890');

    expect(result.valid).toBe(false);
  });

  it('should handle empty fee string', () => {
    const result = validateTransactionInput('100', '');

    expect(result.valid).toBe(true);
    expect(result.parsedFee).toBeUndefined();
  });

  it('should handle whitespace', () => {
    const result = validateTransactionInput('  100  ', '  1.5  ');

    expect(result.valid).toBe(true);
    expect(result.parsedAmount).toBe(100);
    expect(result.parsedFee).toBe(1.5);
  });
});

describe('dryRunTransfer (Hardened)', () => {
  let client: RustChainClient;
  let keyPair: ReturnType<typeof generateKeyPair>;

  beforeEach(() => {
    client = new RustChainClient(Network.Mainnet);
    keyPair = generateKeyPair();
    jest.clearAllMocks();
  });

  it('should reject invalid recipient address', async () => {
    const result = await dryRunTransfer(client, keyPair, 'invalid', 10000000);

    expect(result.valid).toBe(false);
    expect(result.errors.some(e => e.includes('Invalid recipient'))).toBe(true);
  });

  it('should reject zero amount', async () => {
    const recipient = publicKeyToBase58(generateKeyPair().publicKey);
    const result = await dryRunTransfer(client, keyPair, recipient, 0);

    expect(result.valid).toBe(false);
    expect(result.errors.some(e => e.includes('greater than 0'))).toBe(true);
  });

  it('should reject negative amount', async () => {
    const recipient = publicKeyToBase58(generateKeyPair().publicKey);
    const result = await dryRunTransfer(client, keyPair, recipient, -100);

    expect(result.valid).toBe(false);
  });

  it('should validate successfully with valid input', async () => {
    const recipient = publicKeyToBase58(generateKeyPair().publicKey);
    const senderAddress = publicKeyToBase58(keyPair.publicKey);

    // Mock getBalance to return sufficient balance
    (global.fetch as jest.Mock).mockImplementation((url: string) => {
      if (url.includes('wallet/balance')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            miner: senderAddress,
            balance: 1000000000, // 10 RTC - plenty for the test
            unlocked: 1000000000,
            locked: 0,
          }),
        });
      }
      if (url.includes('api/stats')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            chain_id: 'rustchain-mainnet',
            network: 'mainnet',
            block_height: 1000000,
            peer_count: 50,
            min_fee: 1000,
            version: '2.2.1',
          }),
        });
      }
      return Promise.resolve({ ok: false });
    });

    const result = await dryRunTransfer(client, keyPair, recipient, 10000000);

    // Log errors for debugging
    if (!result.valid) {
      console.log('Validation errors:', result.errors);
    }

    expect(result.valid).toBe(true);
    expect(result.sufficientBalance).toBe(true);
  });
});
