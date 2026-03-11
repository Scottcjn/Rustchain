/**
 * Crypto Utilities Tests (Hardened)
 *
 * Issue #785: Security hardening tests
 * - chain_id in signed payload
 * - Numeric validation
 * - Address validation
 */

import {
  generateKeyPair,
  keyPairFromHex,
  keyPairFromBase58,
  keyPairFromSeed,
  publicKeyToHex,
  publicKeyToBase58,
  publicKeyToRtcAddress,
  secretKeyToHex,
  signMessage,
  verifySignature,
  signString,
  verifySignatureHex,
  createSigningPayload,
  signTransactionPayload,
  verifyTransactionPayload,
  validateNumericString,
  validateTransactionAmount,
  validateTransactionFee,
  isValidAddress,
  constantTimeCompare,
} from '../crypto';

describe('Crypto Utilities (Hardened)', () => {
  const rtcA = `RTC${'a'.repeat(40)}`;
  const rtcB = `RTC${'b'.repeat(40)}`;

  describe('createSigningPayload', () => {
    it('should create payload with chain_id', () => {
      const txData = {
        from: rtcA,
        to: rtcB,
        amount: 100,
        nonce: 1,
        memo: 'Test',
      };
      const chainId = 'rustchain-mainnet';

      const payload = createSigningPayload(txData, chainId);

      expect(payload.chain_id).toBe(chainId);
      expect(payload.from).toBe(txData.from);
      expect(payload.to).toBe(txData.to);
      expect(payload.amount).toBe(txData.amount);
    });

    it('should include all required fields', () => {
      const txData = {
        from: rtcA,
        to: rtcB,
        amount: 100,
        nonce: 1,
      };
      const chainId = 'test-chain';

      const payload = createSigningPayload(txData, chainId);

      expect(payload).toHaveProperty('from');
      expect(payload).toHaveProperty('to');
      expect(payload).toHaveProperty('amount');
      expect(payload).toHaveProperty('nonce');
      expect(payload).toHaveProperty('chain_id');
    });
  });

  describe('signTransactionPayload and verifyTransactionPayload', () => {
    it('should sign and verify transaction with chain_id', () => {
      const keyPair = generateKeyPair();
      const txData = {
        from: rtcA,
        to: rtcB,
        amount: 100,
        nonce: 1,
      };
      const chainId = 'rustchain-mainnet';

      const signature = signTransactionPayload(txData, chainId, keyPair.secretKey);
      const valid = verifyTransactionPayload(txData, chainId, signature, keyPair.publicKey);

      expect(valid).toBe(true);
    });

    it('should fail verification with wrong chain_id', () => {
      const keyPair = generateKeyPair();
      const txData = {
        from: rtcA,
        to: rtcB,
        amount: 100,
        nonce: 1,
      };
      const chainId = 'rustchain-mainnet';
      const wrongChainId = 'rustchain-testnet';

      const signature = signTransactionPayload(txData, chainId, keyPair.secretKey);
      const valid = verifyTransactionPayload(txData, wrongChainId, signature, keyPair.publicKey);

      expect(valid).toBe(false);
    });

    it('should fail verification with tampered data', () => {
      const keyPair = generateKeyPair();
      const txData = {
        from: rtcA,
        to: rtcB,
        amount: 100,
        nonce: 1,
      };
      const chainId = 'rustchain-mainnet';

      const signature = signTransactionPayload(txData, chainId, keyPair.secretKey);

      // Tamper with amount
      const tamperedData = { ...txData, amount: 999 };
      const valid = verifyTransactionPayload(tamperedData, chainId, signature, keyPair.publicKey);

      expect(valid).toBe(false);
    });

    it('should fail verification with wrong public key', () => {
      const keyPair1 = generateKeyPair();
      const keyPair2 = generateKeyPair();
      const txData = {
        from: rtcA,
        to: rtcB,
        amount: 100,
        nonce: 1,
      };
      const chainId = 'rustchain-mainnet';

      const signature = signTransactionPayload(txData, chainId, keyPair1.secretKey);
      const valid = verifyTransactionPayload(txData, chainId, signature, keyPair2.publicKey);

      expect(valid).toBe(false);
    });
  });

  describe('validateNumericString', () => {
    it('should validate valid positive numbers', () => {
      expect(validateNumericString('100')).toEqual({ valid: true, value: 100 });
      expect(validateNumericString('0.5')).toEqual({ valid: true, value: 0.5 });
      expect(validateNumericString('123.456')).toEqual({ valid: true, value: 123.456 });
    });

    it('should reject empty values', () => {
      expect(validateNumericString('')).toEqual(
        expect.objectContaining({ valid: false })
      );
      expect(validateNumericString('   ')).toEqual(
        expect.objectContaining({ valid: false })
      );
    });

    it('should reject invalid formats', () => {
      expect(validateNumericString('abc')).toEqual(
        expect.objectContaining({ valid: false })
      );
      expect(validateNumericString('1.2.3')).toEqual(
        expect.objectContaining({ valid: false })
      );
      expect(validateNumericString('1e5')).toEqual(
        expect.objectContaining({ valid: false })
      );
    });

    it('should reject negative numbers by default', () => {
      expect(validateNumericString('-100')).toEqual(
        expect.objectContaining({ valid: false })
      );
    });

    it('should allow negative numbers when configured', () => {
      const result = validateNumericString('-100', { allowNegative: true });
      expect(result.valid).toBe(true);
      expect(result.value).toBe(-100);
    });

    it('should reject zero when allowZero is false', () => {
      expect(validateNumericString('0', { allowZero: false })).toEqual(
        expect.objectContaining({ valid: false })
      );
    });

    it('should enforce min value', () => {
      expect(validateNumericString('5', { min: 10 })).toEqual(
        expect.objectContaining({ valid: false })
      );
      expect(validateNumericString('15', { min: 10 })).toEqual(
        expect.objectContaining({ valid: true })
      );
    });

    it('should enforce max value', () => {
      expect(validateNumericString('15', { max: 10 })).toEqual(
        expect.objectContaining({ valid: false })
      );
      expect(validateNumericString('5', { max: 10 })).toEqual(
        expect.objectContaining({ valid: true })
      );
    });

    it('should enforce max decimal places', () => {
      expect(validateNumericString('1.234', { maxDecimals: 2 })).toEqual(
        expect.objectContaining({ valid: false })
      );
      expect(validateNumericString('1.23', { maxDecimals: 2 })).toEqual(
        expect.objectContaining({ valid: true })
      );
    });

    it('should trim whitespace', () => {
      expect(validateNumericString('  100  ')).toEqual(
        expect.objectContaining({ valid: true, value: 100 })
      );
    });

    it('should reject leading zeros (except 0.xxx)', () => {
      expect(validateNumericString('0100')).toEqual(
        expect.objectContaining({ valid: false })
      );
      expect(validateNumericString('0.5')).toEqual(
        expect.objectContaining({ valid: true })
      );
    });
  });

  describe('validateTransactionAmount', () => {
    it('should validate valid transaction amounts', () => {
      expect(validateTransactionAmount('100')).toEqual(
        expect.objectContaining({ valid: true })
      );
      expect(validateTransactionAmount('0.000001')).toEqual(
        expect.objectContaining({ valid: true })
      );
      expect(validateTransactionAmount('123.456789')).toEqual(
        expect.objectContaining({ valid: true })
      );
    });

    it('should reject zero', () => {
      expect(validateTransactionAmount('0')).toEqual(
        expect.objectContaining({ valid: false })
      );
    });

    it('should reject negative amounts', () => {
      expect(validateTransactionAmount('-100')).toEqual(
        expect.objectContaining({ valid: false })
      );
    });

    it('should reject more than 6 decimal places', () => {
      expect(validateTransactionAmount('1.2345678')).toEqual(
        expect.objectContaining({ valid: false })
      );
    });
  });

  describe('validateTransactionFee', () => {
    it('should validate valid fees', () => {
      expect(validateTransactionFee('0')).toEqual(
        expect.objectContaining({ valid: true })
      );
      expect(validateTransactionFee('1.5')).toEqual(
        expect.objectContaining({ valid: true })
      );
    });

    it('should allow zero fee', () => {
      expect(validateTransactionFee('0')).toEqual(
        expect.objectContaining({ valid: true })
      );
    });

    it('should reject negative fees', () => {
      expect(validateTransactionFee('-1')).toEqual(
        expect.objectContaining({ valid: false })
      );
    });
  });

  describe('isValidAddress', () => {
    it('should validate RTC addresses', () => {
      expect(isValidAddress(rtcA)).toBe(true);
    });

    it('should reject addresses with invalid hex payload', () => {
      expect(isValidAddress(`RTC${'z'.repeat(40)}`)).toBe(false);
    });

    it('should reject too-short addresses', () => {
      expect(isValidAddress('RTC123')).toBe(false);
    });

    it('should reject empty addresses', () => {
      expect(isValidAddress('')).toBe(false);
      expect(isValidAddress(null as any)).toBe(false);
      expect(isValidAddress(undefined as any)).toBe(false);
    });

    it('should reject non-RTC strings', () => {
      expect(isValidAddress('not-a-valid-address!!!')).toBe(false);
    });
  });

  describe('constantTimeCompare', () => {
    it('should return true for equal strings', () => {
      expect(constantTimeCompare('abc', 'abc')).toBe(true);
      expect(constantTimeCompare('', '')).toBe(true);
    });

    it('should return false for different strings', () => {
      expect(constantTimeCompare('abc', 'abd')).toBe(false);
      expect(constantTimeCompare('abc', 'abcd')).toBe(false);
    });

    it('should return false for different lengths', () => {
      expect(constantTimeCompare('a', 'aa')).toBe(false);
      expect(constantTimeCompare('', 'a')).toBe(false);
    });
  });

  describe('keyPairFromHex (hardened)', () => {
    it('should accept valid hex with 0x prefix', () => {
      const keyPair = generateKeyPair();
      const hex = '0x' + secretKeyToHex(keyPair.secretKey);
      
      const imported = keyPairFromHex(hex);
      expect(publicKeyToHex(imported.publicKey)).toBe(publicKeyToHex(keyPair.publicKey));
    });

    it('should reject invalid hex length', () => {
      expect(() => keyPairFromHex('abc123')).toThrow('64 or 128 hex characters');
    });

    it('should reject invalid hex characters', () => {
      expect(() => keyPairFromHex('g'.repeat(64))).toThrow();
    });
  });

  describe('keyPairFromBase58 (hardened)', () => {
    it('should reject invalid Base58 characters', () => {
      expect(() => keyPairFromBase58('0OIl')).toThrow('Invalid Base58');
    });

    it('should reject wrong length', () => {
      expect(() => keyPairFromBase58('short')).toThrow();
    });
  });

  describe('keyPairFromSeed and RTC address derivation', () => {
    it('should derive the same public key from a 32-byte seed', () => {
      const seed = new Uint8Array(32).fill(7);
      const pair = keyPairFromSeed(seed);
      expect(pair.publicKey.length).toBe(32);
      expect(pair.secretKey.length).toBe(64);
    });

    it('should derive an RTC address from a public key', async () => {
      const keyPair = generateKeyPair();
      const address = await publicKeyToRtcAddress(keyPair.publicKey);
      expect(address).toMatch(/^RTC[0-9a-f]{40}$/);
    });
  });
});
