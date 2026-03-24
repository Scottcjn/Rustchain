/**
 * RustChain API Client Security Tests
 */

import {
  RustChainClient,
  Network,
  validateTransactionInput,
} from '../rustchain';
import {
  generateKeyPair,
  publicKeyToHex,
  signTransactionPayload,
  verifyTransactionPayload,
} from '../../utils/crypto';

global.fetch = jest.fn();

const RTC_A = `RTC${'a'.repeat(40)}`;
const RTC_B = `RTC${'b'.repeat(40)}`;

describe('RustChainClient (Hardened)', () => {
  let client: RustChainClient;

  beforeEach(() => {
    client = new RustChainClient(Network.Mainnet);
    jest.clearAllMocks();
  });

  describe('chain_id-aware signing', () => {
    it('should fetch and cache the chain_id before signing', async () => {
      const keyPair = generateKeyPair();

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          chain_id: 'rustchain-mainnet-v2',
          network: 'mainnet',
          block_height: 1,
          peer_count: 1,
          min_fee: 0,
          version: '2.2.1',
        }),
      });

      const signed = await client.signTransaction(
        {
          from: RTC_A,
          to: RTC_B,
          amount: 1.5,
          nonce: 123,
        },
        keyPair
      );

      expect(signed.chain_id).toBe('rustchain-mainnet-v2');
      expect(signed.public_key).toBe(publicKeyToHex(keyPair.publicKey));

      const valid = verifyTransactionPayload(
        {
          from: RTC_A,
          to: RTC_B,
          amount: 1.5,
          nonce: 123,
        },
        signed.chain_id,
        signed.signature!,
        keyPair.publicKey
      );
      expect(valid).toBe(true);
    });

    it('should bind signatures to chain_id', () => {
      const keyPair = generateKeyPair();

      const payload = {
        from: RTC_A,
        to: RTC_B,
        amount: 1.5,
        nonce: 123,
      };

      const mainnetSig = signTransactionPayload(payload, 'rustchain-mainnet-v2', keyPair.secretKey);
      const testnetSig = signTransactionPayload(payload, 'rustchain-testnet-v1', keyPair.secretKey);

      expect(mainnetSig).not.toBe(testnetSig);
      expect(
        verifyTransactionPayload(payload, 'rustchain-mainnet-v2', mainnetSig, keyPair.publicKey)
      ).toBe(true);
      expect(
        verifyTransactionPayload(payload, 'rustchain-testnet-v1', mainnetSig, keyPair.publicKey)
      ).toBe(false);
    });
  });

  describe('signed-transfer submission validation', () => {
    it('should reject transactions without a public key', async () => {
      await expect(
        client.submitTransaction({
          from: RTC_A,
          to: RTC_B,
          amount: 1.5,
          nonce: 123,
          signature: '11'.repeat(64),
          chain_id: 'rustchain-mainnet-v2',
        })
      ).rejects.toThrow('public key');
    });

    it('should reject unsafe nonces before sending', async () => {
      await expect(
        client.submitTransaction({
          from: RTC_A,
          to: RTC_B,
          amount: 1.5,
          nonce: 0,
          signature: '11'.repeat(64),
          public_key: '22'.repeat(32),
          chain_id: 'rustchain-mainnet-v2',
        })
      ).rejects.toThrow('nonce must be a safe positive integer');
    });
  });
});

describe('validateTransactionInput', () => {
  it('should accept valid RTC inputs', () => {
    const result = validateTransactionInput('10.5', '0');
    expect(result.valid).toBe(true);
    expect(result.parsedAmount).toBe(10.5);
    expect(result.parsedFee).toBe(0);
  });

  it('should reject too many decimals for RustChain amounts', () => {
    const result = validateTransactionInput('1.2345678');
    expect(result.valid).toBe(false);
  });

  it('should reject malformed numeric strings', () => {
    const result = validateTransactionInput('1e5', 'abc');
    expect(result.valid).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);
  });
});
