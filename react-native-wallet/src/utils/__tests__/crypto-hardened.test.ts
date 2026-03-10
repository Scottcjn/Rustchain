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
  publicKeyToHex,
  publicKeyToBase58,
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
  describe('createSigningPayload', () => {
    it('should create payload with chain_id', () => {
      const txData = {
        from: 'RTC1234567890abcdefghijklmnopqrstuvwxyz',
        to: 'RTC0987654321zyxwvutsrqponmlkjihgfe',
        amount: 100,
        fee: 1,
        nonce: 1,
        timestamp: '2024-01-01T00:00:00Z',
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
        from: 'RTC123',
        to: 'RTC456',
        amount: 100,
        fee: 1,
        nonce: 1,
        timestamp: '2024-01-01T00:00:00Z',
      };
      const chainId = 'test-chain';

      const payload = createSigningPayload(txData, chainId);

      expect(payload).toHaveProperty('from');
      expect(payload).toHaveProperty('to');
      expect(payload).toHaveProperty('amount');
      expect(payload).toHaveProperty('fee');
      expect(payload).toHaveProperty('nonce');
      expect(payload).toHaveProperty('timestamp');
      expect(payload).toHaveProperty('chain_id');
    });
  });

  describe('signTransactionPayload and verifyTransactionPayload', () => {
    it('should sign and verify transaction with chain_id', () => {
      const keyPair = generateKeyPair();
      const txData = {
        from: publicKeyToBase58(keyPair.publicKey),
        to: publicKeyToBase58(generateKeyPair().publicKey),
        amount: 100,
        fee: 1,
        nonce: 1,
        timestamp: '2024-01-01T00:00:00Z',
      };
      const chainId = 'rustchain-mainnet';

      const signature = signTransactionPayload(txData, chainId, keyPair.secretKey);
      const valid = verifyTransactionPayload(txData, chainId, signature, keyPair.publicKey);

      expect(valid).toBe(true);
    });

    it('should fail verification with wrong chain_id', () => {
      const keyPair = generateKeyPair();
      const txData = {
        from: publicKeyToBase58(keyPair.publicKey),
        to: publicKeyToBase58(generateKeyPair().publicKey),
        amount: 100,
        fee: 1,
        nonce: 1,
        timestamp: '2024-01-01T00:00:00Z',
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
        from: publicKeyToBase58(keyPair.publicKey),
        to: publicKeyToBase58(generateKeyPair().publicKey),
        amount: 100,
        fee: 1,
        nonce: 1,
        timestamp: '2024-01-01T00:00:00Z',
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
        from: publicKeyToBase58(keyPair1.publicKey),
        to: publicKeyToBase58(keyPair2.publicKey),
        amount: 100,
        fee: 1,
        nonce: 1,
        timestamp: '2024-01-01T00:00:00Z',
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
      expect(validateTransactionAmount('0.00000001')).toEqual(
        expect.objectContaining({ valid: true })
      );
      expect(validateTransactionAmount('123.45678901')).toEqual(
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

    it('should reject more than 8 decimal places', () => {
      // 1.23456789 has exactly 8 decimal places, which is valid
      // 1.234567890 has 9 decimal places, which should be rejected
      expect(validateTransactionAmount('1.234567890')).toEqual(
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
    it('should validate correct Base58 addresses', () => {
      const keyPair = generateKeyPair();
      const address = publicKeyToBase58(keyPair.publicKey);
      
      expect(isValidAddress(address)).toBe(true);
    });

    it('should reject addresses with invalid Base58 characters', () => {
      expect(isValidAddress('RTC0OIl1234567890')).toBe(false); // Contains 0, O, I, l
    });

    it('should reject too-short addresses', () => {
      expect(isValidAddress('RTC123')).toBe(false);
    });

    it('should reject empty addresses', () => {
      expect(isValidAddress('')).toBe(false);
      expect(isValidAddress(null as any)).toBe(false);
      expect(isValidAddress(undefined as any)).toBe(false);
    });

    it('should reject non-Base58 decodable strings', () => {
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
      expect(() => keyPairFromHex('abc123')).toThrow('128 hex characters');
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
});
