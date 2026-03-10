/**
 * KDF (Key Derivation Function) Tests
 *
 * Issue #785: Security hardening tests
 */

import {
  pbkdf2,
  argon2id,
  generateSalt,
  saltToHex,
  saltFromHex,
  deriveKey,
  createPBKDF2Params,
  createArgon2idParams,
} from '../kdf';

describe('KDF - Key Derivation Functions', () => {
  describe('generateSalt', () => {
    it('should generate random salt of specified length', () => {
      const salt16 = generateSalt(16);
      expect(salt16.length).toBe(16);

      const salt32 = generateSalt(32);
      expect(salt32.length).toBe(32);

      const salt64 = generateSalt(64);
      expect(salt64.length).toBe(64);
    });

    it('should generate unique salts', () => {
      const salt1 = generateSalt(32);
      const salt2 = generateSalt(32);
      
      expect(salt1).not.toEqual(salt2);
    });
  });

  describe('saltToHex and saltFromHex', () => {
    it('should convert salt to hex and back', () => {
      const salt = generateSalt(32);
      const hex = saltToHex(salt);
      const recovered = saltFromHex(hex);

      expect(recovered).toEqual(salt);
      expect(hex.length).toBe(64); // 32 bytes = 64 hex chars
    });

    it('should handle different salt lengths', () => {
      for (const length of [16, 24, 32, 64]) {
        const salt = generateSalt(length);
        const hex = saltToHex(salt);
        const recovered = saltFromHex(hex);
        expect(recovered).toEqual(salt);
        expect(hex.length).toBe(length * 2);
      }
    });
  });

  describe('pbkdf2', () => {
    it('should derive a key from password and salt', async () => {
      const password = 'test_password_123';
      const salt = generateSalt(32);
      
      const key = await pbkdf2(password, salt);
      
      expect(key.length).toBe(32); // Default dkLen
      expect(key).toBeInstanceOf(Uint8Array);
    });

    it('should derive same key with same inputs', async () => {
      const password = 'test_password_123';
      const salt = generateSalt(32);
      
      const key1 = await pbkdf2(password, salt);
      const key2 = await pbkdf2(password, salt);
      
      expect(key1).toEqual(key2);
    });

    it('should derive different keys with different passwords', async () => {
      const salt = generateSalt(32);
      
      const key1 = await pbkdf2('password1', salt);
      const key2 = await pbkdf2('password2', salt);
      
      expect(key1).not.toEqual(key2);
    });

    it('should derive different keys with different salts', async () => {
      const password = 'test_password_123';
      const salt1 = generateSalt(32);
      const salt2 = generateSalt(32);
      
      const key1 = await pbkdf2(password, salt1);
      const key2 = await pbkdf2(password, salt2);
      
      expect(key1).not.toEqual(key2);
    });

    it('should support custom dkLen', async () => {
      const password = 'test_password_123';
      const salt = generateSalt(32);
      
      const key16 = await pbkdf2(password, salt, { dkLen: 16, iterations: 1000, hashAlgorithm: expect.anything() });
      expect(key16.length).toBe(16);
      
      const key64 = await pbkdf2(password, salt, { dkLen: 64, iterations: 1000, hashAlgorithm: expect.anything() });
      expect(key64.length).toBe(64);
    });
  });

  describe('argon2id', () => {
    it('should derive a key using Argon2id-like function', async () => {
      const password = 'test_password_123';
      const salt = generateSalt(32);
      
      const key = await argon2id(password, salt);
      
      expect(key.length).toBe(32); // Default dkLen
      expect(key).toBeInstanceOf(Uint8Array);
    });

    it('should derive same key with same inputs', async () => {
      const password = 'test_password_123';
      const salt = generateSalt(32);
      
      const key1 = await argon2id(password, salt);
      const key2 = await argon2id(password, salt);
      
      expect(key1).toEqual(key2);
    });

    it('should derive different keys with different passwords', async () => {
      const salt = generateSalt(32);
      
      const key1 = await argon2id('password1', salt);
      const key2 = await argon2id('password2', salt);
      
      expect(key1).not.toEqual(key2);
    });

    it('should derive different keys with different salts', async () => {
      const password = 'test_password_123';
      const salt1 = generateSalt(32);
      const salt2 = generateSalt(32);
      
      const key1 = await argon2id(password, salt1);
      const key2 = await argon2id(password, salt2);
      
      expect(key1).not.toEqual(key2);
    });

    it('should support custom parameters', async () => {
      const password = 'test_password_123';
      const salt = generateSalt(32);
      
      const key = await argon2id(password, salt, {
        iterations: 2,
        memorySize: 2,
        dkLen: 16,
      });
      
      expect(key.length).toBe(16);
    });
  });

  describe('deriveKey', () => {
    it('should derive key using PBKDF2', async () => {
      const password = 'test_password_123';
      const salt = generateSalt(32);
      
      const key = await deriveKey(password, {
        type: 'pbkdf2',
        salt: saltToHex(salt),
        dkLen: 32,
      });
      
      expect(key.length).toBe(32);
    });

    it('should derive key using Argon2id', async () => {
      const password = 'test_password_123';
      const salt = generateSalt(32);
      
      const key = await deriveKey(password, {
        type: 'argon2id',
        salt: saltToHex(salt),
        dkLen: 32,
      });
      
      expect(key.length).toBe(32);
    });

    it('should throw for unknown KDF type', async () => {
      const password = 'test_password_123';
      const salt = generateSalt(32);
      
      await expect(
        deriveKey(password, {
          type: 'unknown' as any,
          salt: saltToHex(salt),
          dkLen: 32,
        })
      ).rejects.toThrow('Unknown KDF type');
    });
  });

  describe('createPBKDF2Params', () => {
    it('should create PBKDF2 params with default values', () => {
      const params = createPBKDF2Params();
      
      expect(params.type).toBe('pbkdf2');
      expect(params.salt.length).toBe(64); // 32 bytes hex
      expect(params.dkLen).toBe(32);
      expect(params.iterations).toBeDefined();
    });

    it('should create PBKDF2 params with custom values', () => {
      const customSalt = generateSalt(16);
      const params = createPBKDF2Params(customSalt, 100000, 16);
      
      expect(params.type).toBe('pbkdf2');
      expect(params.salt).toBe(saltToHex(customSalt));
      expect(params.dkLen).toBe(16);
      expect(params.iterations).toBe(100000);
    });
  });

  describe('createArgon2idParams', () => {
    it('should create Argon2id params with default values', () => {
      const params = createArgon2idParams();
      
      expect(params.type).toBe('argon2id');
      expect(params.salt.length).toBe(64); // 32 bytes hex
      expect(params.dkLen).toBe(32);
      expect(params.iterations).toBeDefined();
      expect(params.memorySize).toBeDefined();
    });

    it('should create Argon2id params with custom values', () => {
      const customSalt = generateSalt(16);
      const params = createArgon2idParams(customSalt, 2, 8, 64);
      
      expect(params.type).toBe('argon2id');
      expect(params.salt).toBe(saltToHex(customSalt));
      expect(params.dkLen).toBe(64);
      expect(params.iterations).toBe(2);
      expect(params.memorySize).toBe(8);
    });
  });

  describe('Security Properties', () => {
    it('PBKDF2 should be computationally expensive (takes time)', async () => {
      const password = 'test_password_123';
      const salt = generateSalt(32);
      
      const start = Date.now();
      await pbkdf2(password, salt, {
        iterations: 10000, // Reduced for test speed
        dkLen: 32,
        hashAlgorithm: expect.anything(),
      });
      const duration = Date.now() - start;
      
      // Should take some time (at least 1ms for 10k iterations)
      expect(duration).toBeGreaterThan(0);
    });

    it('Argon2id should be more expensive than PBKDF2', async () => {
      const password = 'test_password_123';
      const salt = generateSalt(32);
      
      const start1 = Date.now();
      await pbkdf2(password, salt, {
        iterations: 1000,
        dkLen: 32,
        hashAlgorithm: expect.anything(),
      });
      const pbkdf2Time = Date.now() - start1;
      
      const start2 = Date.now();
      await argon2id(password, salt, {
        iterations: 1,
        memorySize: 2,
        dkLen: 32,
      });
      const argon2Time = Date.now() - start2;
      
      // Argon2id with multiple lanes should take longer
      expect(argon2Time).toBeGreaterThanOrEqual(pbkdf2Time);
    });
  });
});
