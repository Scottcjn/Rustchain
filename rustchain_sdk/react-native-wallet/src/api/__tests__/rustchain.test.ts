/**
 * RustChain API Client Tests
 */

import {
  RustChainClient,
  Network,
  dryRunTransfer,
  getNetworkConfig,
  getDefaultNetwork,
} from '../rustchain';
import { generateKeyPair } from '../../utils/crypto';

global.fetch = jest.fn();

const TEST_ADDRESS = `RTC${'a'.repeat(40)}`;
const RECIPIENT_ADDRESS = `RTC${'b'.repeat(40)}`;

describe('Environment Configuration', () => {
  describe('getNetworkConfig', () => {
    it('should return default mainnet config', () => {
      const config = getNetworkConfig(Network.Mainnet);
      expect(config.rpcUrl).toBe('https://rustchain.org');
      expect(config.explorerUrl).toBe('https://rustchain.org/explorer');
    });

    it('should return correct testnet config', () => {
      const config = getNetworkConfig(Network.Testnet);
      expect(config.rpcUrl).toBe('https://testnet-rpc.rustchain.org');
      expect(config.explorerUrl).toBe('https://testnet-explorer.rustchain.org');
    });

    it('should return mainnet by default', () => {
      expect(getDefaultNetwork()).toBe(Network.Mainnet);
    });
  });
});

describe('RustChainClient', () => {
  let client: RustChainClient;

  beforeEach(() => {
    client = new RustChainClient(Network.Mainnet);
    jest.clearAllMocks();
  });

  describe('getBalance', () => {
    it('should normalize the live balance response', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          miner_id: TEST_ADDRESS,
          amount_i64: 1_500_000,
          amount_rtc: 1.5,
        }),
      });

      const balance = await client.getBalance(TEST_ADDRESS);

      expect(balance).toEqual({
        miner: TEST_ADDRESS,
        amount_i64: 1_500_000,
        amount_rtc: 1.5,
        balance: 1_500_000,
        unlocked: 1_500_000,
        locked: 0,
        nonce: undefined,
      });
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining(`/wallet/balance?address=${encodeURIComponent(TEST_ADDRESS)}`),
        expect.any(Object)
      );
    });

    it('should reject invalid addresses before sending a request', async () => {
      await expect(client.getBalance('invalid')).rejects.toThrow('Invalid wallet address format');
      expect(global.fetch).not.toHaveBeenCalled();
    });
  });

  describe('network info', () => {
    it('should fetch and cache the chain id', async () => {
      const info = {
        chain_id: 'rustchain-mainnet-v2',
        network: 'mainnet',
        block_height: 1000000,
        peer_count: 50,
        min_fee: 0,
        version: '2.2.1',
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => info,
      });

      const first = await client.getNetworkInfo();
      const cached = await client.getChainId();

      expect(first.chain_id).toBe(info.chain_id);
      expect(cached).toBe(info.chain_id);
      expect(global.fetch).toHaveBeenCalledTimes(1);
    });

    it('should estimate zero fee for signed transfers', async () => {
      await expect(client.estimateFee(1_000_000)).resolves.toBe(0);
    });
  });

  describe('buildTransaction', () => {
    it('should build the canonical signed-transfer payload', () => {
      const tx = client.buildTransaction({
        from: TEST_ADDRESS,
        to: RECIPIENT_ADDRESS,
        amount: 1.25,
        nonce: 123,
        memo: 'Test memo',
      });

      expect(tx).toEqual({
        from: TEST_ADDRESS,
        to: RECIPIENT_ADDRESS,
        amount: 1.25,
        nonce: 123,
        memo: 'Test memo',
      });
    });
  });

  describe('submitTransaction', () => {
    it('should post to /wallet/transfer/signed', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          ok: true,
          phase: 'pending',
          tx_hash: 'abc123',
          verified: true,
          confirms_at: 1234567890,
          message: 'Transfer pending.',
        }),
      });

      const result = await client.submitTransaction({
        from: TEST_ADDRESS,
        to: RECIPIENT_ADDRESS,
        amount: 1.5,
        nonce: 12345,
        memo: 'hello',
        chain_id: 'rustchain-mainnet-v2',
        public_key: '11'.repeat(32),
        signature: '22'.repeat(64),
      });

      expect(result).toEqual({
        tx_hash: 'abc123',
        status: 'pending',
        verified: true,
        confirms_at: 1234567890,
        message: 'Transfer pending.',
      });

      const [, requestInit] = (global.fetch as jest.Mock).mock.calls[0];
      const payload = JSON.parse(String(requestInit.body));
      expect(payload).toEqual({
        from_address: TEST_ADDRESS,
        to_address: RECIPIENT_ADDRESS,
        amount_rtc: 1.5,
        nonce: 12345,
        memo: 'hello',
        public_key: '11'.repeat(32),
        signature: '22'.repeat(64),
        chain_id: 'rustchain-mainnet-v2',
      });
    });
  });

  describe('transfer', () => {
    it('should perform the live signed-transfer flow', async () => {
      const keyPair = generateKeyPair();

      (global.fetch as jest.Mock)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            chain_id: 'rustchain-mainnet-v2',
            network: 'mainnet',
            block_height: 1000000,
            peer_count: 50,
            min_fee: 0,
            version: '2.2.1',
          }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            ok: true,
            phase: 'pending',
            tx_hash: 'tx123',
            verified: true,
          }),
        });

      const result = await client.transfer(keyPair, RECIPIENT_ADDRESS, 1_500_000, {
        memo: 'mobile wallet',
      });

      expect(result.tx_hash).toBe('tx123');
      expect(result.status).toBe('pending');
      expect(global.fetch).toHaveBeenNthCalledWith(
        2,
        expect.stringContaining('/wallet/transfer/signed'),
        expect.any(Object)
      );
    });

    it('should reject invalid recipients', async () => {
      const keyPair = generateKeyPair();
      await expect(client.transfer(keyPair, 'invalid', 1_000_000)).rejects.toThrow('Invalid recipient address');
    });
  });

  describe('healthCheck', () => {
    it('should return true when API is reachable', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ chain_id: 'rustchain-mainnet-v2' }),
      });

      await expect(client.healthCheck()).resolves.toBe(true);
    });

    it('should return false when API is unreachable', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Network error'));
      await expect(client.healthCheck()).resolves.toBe(false);
    });
  });
});

describe('dryRunTransfer', () => {
  let client: RustChainClient;

  beforeEach(() => {
    client = new RustChainClient(Network.Mainnet);
    jest.clearAllMocks();
  });

  it('should validate a valid transfer', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        miner_id: TEST_ADDRESS,
        amount_i64: 5_000_000,
        amount_rtc: 5,
      }),
    });

    const result = await dryRunTransfer(client, TEST_ADDRESS, RECIPIENT_ADDRESS, 1_500_000);

    expect(result.valid).toBe(true);
    expect(result.sufficientBalance).toBe(true);
    expect(result.estimatedFee).toBe(0);
  });

  it('should detect insufficient balance', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        miner_id: TEST_ADDRESS,
        amount_i64: 500_000,
        amount_rtc: 0.5,
      }),
    });

    const result = await dryRunTransfer(client, TEST_ADDRESS, RECIPIENT_ADDRESS, 1_500_000);

    expect(result.valid).toBe(false);
    expect(result.sufficientBalance).toBe(false);
  });

  it('should reject invalid recipient addresses', async () => {
    const result = await dryRunTransfer(client, TEST_ADDRESS, 'invalid', 1_500_000);
    expect(result.valid).toBe(false);
    expect(result.errors.some((error) => error.includes('Invalid recipient'))).toBe(true);
  });

  it('should reject zero amounts', async () => {
    const result = await dryRunTransfer(client, TEST_ADDRESS, RECIPIENT_ADDRESS, 0);
    expect(result.valid).toBe(false);
    expect(result.errors.some((error) => error.includes('positive safe integer'))).toBe(true);
  });
});
