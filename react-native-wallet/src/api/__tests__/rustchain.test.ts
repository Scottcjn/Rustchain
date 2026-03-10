/**
 * RustChain API Client Tests
 */

import {
  RustChainClient,
  Network,
  NETWORK_CONFIG,
  dryRunTransfer,
  type DryRunResult,
} from '../rustchain';
import { generateKeyPair, publicKeyToBase58 } from '../../utils/crypto';

// Mock fetch for testing
global.fetch = jest.fn();

describe('RustChainClient', () => {
  let client: RustChainClient;
  let testAddress: string;

  beforeEach(() => {
    client = new RustChainClient(Network.Mainnet);
    jest.clearAllMocks();
    // Generate a valid Base58 address for tests
    testAddress = publicKeyToBase58(generateKeyPair().publicKey);
  });

  describe('constructor', () => {
    it('should create client with default mainnet config', () => {
      const defaultClient = new RustChainClient();
      expect(defaultClient).toBeDefined();
    });

    it('should create client with custom network', () => {
      const testnetClient = new RustChainClient(Network.Testnet);
      expect(testnetClient).toBeDefined();
    });

    it('should create client with custom URL', () => {
      const customClient = RustChainClient.withUrl('https://custom.node.com');
      expect(customClient).toBeDefined();
    });
  });

  describe('getBalance', () => {
    it('should fetch balance successfully', async () => {
      const mockBalance = {
        miner: testAddress,
        balance: 100000000,
        unlocked: 100000000,
        locked: 0,
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockBalance,
      });

      const balance = await client.getBalance(testAddress);

      expect(balance).toEqual(mockBalance);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining(`/wallet/balance?miner_id=${encodeURIComponent(testAddress)}`),
        expect.any(Object)
      );
    });

    it('should handle API errors', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: 'Not Found',
      });

      await expect(client.getBalance(testAddress)).rejects.toThrow();
    });

    it('should handle network errors', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(
        new Error('Network error')
      );

      await expect(client.getBalance(testAddress)).rejects.toThrow();
    });
  });

  describe('getNetworkInfo', () => {
    it('should fetch network info successfully', async () => {
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

      const info = await client.getNetworkInfo();

      expect(info).toEqual(mockInfo);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/stats'),
        expect.any(Object)
      );
    });
  });

  describe('getNonce', () => {
    it('should get nonce from balance response', async () => {
      const mockBalance = {
        miner: testAddress,
        balance: 100000000,
        unlocked: 100000000,
        locked: 0,
        nonce: 5,
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockBalance,
      });

      const nonce = await client.getNonce(testAddress);

      expect(nonce).toBe(5);
    });

    it('should return 0 if nonce not provided', async () => {
      const mockBalance = {
        miner: testAddress,
        balance: 100000000,
        unlocked: 100000000,
        locked: 0,
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockBalance,
      });

      const nonce = await client.getNonce(testAddress);

      expect(nonce).toBe(0);
    });
  });

  describe('estimateFee', () => {
    it('should estimate fee with different priorities', async () => {
      const mockInfo = {
        chain_id: 'rustchain-mainnet',
        network: 'mainnet',
        block_height: 1000000,
        peer_count: 50,
        min_fee: 1000,
        version: '2.2.1',
      };

      // estimateFee calls getMinFee which calls getNetworkInfo
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockInfo,
      });

      const lowFee = await client.estimateFee(1000, 'low');
      expect(lowFee).toBe(1000);

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockInfo,
      });

      const normalFee = await client.estimateFee(1000, 'normal');
      expect(normalFee).toBe(2000);

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockInfo,
      });

      const highFee = await client.estimateFee(1000, 'high');
      expect(highFee).toBe(5000);
    });
  });

  describe('buildTransaction', () => {
    it('should build a transaction', () => {
      const tx = client.buildTransaction({
        from: 'sender_address',
        to: 'recipient_address',
        amount: 1000,
        fee: 100,
        nonce: 1,
        memo: 'Test memo',
      });

      expect(tx.from).toBe('sender_address');
      expect(tx.to).toBe('recipient_address');
      expect(tx.amount).toBe(1000);
      expect(tx.fee).toBe(100);
      expect(tx.nonce).toBe(1);
      expect(tx.memo).toBe('Test memo');
      expect(tx.signature).toBeUndefined();
    });
  });

  describe('healthCheck', () => {
    it('should return true when API is reachable', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ chain_id: 'test' }),
      });

      const healthy = await client.healthCheck();
      expect(healthy).toBe(true);
    });

    it('should return false when API is unreachable', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Network error'));

      const healthy = await client.healthCheck();
      expect(healthy).toBe(false);
    });
  });
});

describe('dryRunTransfer', () => {
  let client: RustChainClient;
  let keyPair: ReturnType<typeof generateKeyPair>;

  beforeEach(() => {
    client = new RustChainClient(Network.Mainnet);
    keyPair = generateKeyPair();
    jest.clearAllMocks();
  });

  it('should validate transaction successfully', async () => {
    const recipient = publicKeyToBase58(generateKeyPair().publicKey);
    const senderAddress = publicKeyToBase58(keyPair.publicKey);

    // Mock fetch to return balance and network info
    (global.fetch as jest.Mock).mockImplementation((url: string) => {
      if (url.includes('miner_id')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            miner: senderAddress,
            balance: 1000000000, // Increased balance for safety
            unlocked: 1000000000,
            locked: 0,
          }),
        });
      }
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
    });

    const result = await dryRunTransfer(client, keyPair, recipient, 10000000);

    expect(result.valid).toBe(true);
    expect(result.sufficientBalance).toBe(true);
  });

  it('should detect insufficient balance', async () => {
    const recipient = publicKeyToBase58(generateKeyPair().publicKey);
    const senderAddress = publicKeyToBase58(keyPair.publicKey);

    // Mock fetch to return low balance and network info
    (global.fetch as jest.Mock).mockImplementation((url: string) => {
      if (url.includes('wallet/balance')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            miner: senderAddress,
            balance: 1000,
            unlocked: 1000,
            locked: 0,
          }),
        });
      }
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
    });

    const result = await dryRunTransfer(client, keyPair, recipient, 100000000);

    expect(result.valid).toBe(false);
    expect(result.sufficientBalance).toBe(false);
  });

  it('should detect invalid recipient address', async () => {
    const result = await dryRunTransfer(client, keyPair, 'invalid', 10000000);

    expect(result.valid).toBe(false);
    expect(result.errors.some(e => e.includes('Invalid recipient'))).toBe(true);
  });

  it('should detect zero amount', async () => {
    const recipient = publicKeyToBase58(generateKeyPair().publicKey);

    const result = await dryRunTransfer(client, keyPair, recipient, 0);

    expect(result.valid).toBe(false);
    expect(result.errors.some(e => e.includes('greater than 0'))).toBe(true);
  });
});
