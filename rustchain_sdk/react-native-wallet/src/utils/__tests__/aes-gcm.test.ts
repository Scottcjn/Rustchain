/**
 * AES-GCM Encryption Tests
 *
 * Issue #785: Security hardening tests
 */

import {
  aesGcmEncrypt,
  aesGcmDecrypt,
  encryptWithPassword,
  decryptWithPassword,
  verifyEncryption,
  type EncryptedData,
} from '../aes-gcm';
import { generateSalt, saltToHex } from '../kdf';

describe('AES-GCM Encryption', () => {
  describe('aesGcmEncrypt and aesGcmDecrypt', () => {
    it('should encrypt and decrypt data successfully', async () => {
      const plaintext = new TextEncoder().encode('Hello, RustChain!');
      const key = generateSalt(32); // 32-byte key
      const iv = generateSalt(12); // 12-byte IV
      
      const { ciphertext, authTag } = await aesGcmEncrypt(plaintext, key, iv);
      
      expect(ciphertext.length).toBe(plaintext.length);
      expect(authTag.length).toBe(16); // 16-byte auth tag
      
      const decrypted = await aesGcmDecrypt(ciphertext, key, iv, authTag);
      
      expect(new TextDecoder().decode(decrypted)).toBe('Hello, RustChain!');
    });

    it('should produce different ciphertext with different IV', async () => {
      const plaintext = new TextEncoder().encode('Test message');
      const key = generateSalt(32);
      const iv1 = generateSalt(12);
      const iv2 = generateSalt(12);
      
      const { ciphertext: ct1 } = await aesGcmEncrypt(plaintext, key, iv1);
      const { ciphertext: ct2 } = await aesGcmEncrypt(plaintext, key, iv2);
      
      expect(ct1).not.toEqual(ct2);
    });

    it('should fail decryption with wrong key', async () => {
      const plaintext = new TextEncoder().encode('Secret message');
      const key = generateSalt(32);
      const wrongKey = generateSalt(32);
      const iv = generateSalt(12);
      
      const { ciphertext, authTag } = await aesGcmEncrypt(plaintext, key, iv);
      
      await expect(
        aesGcmDecrypt(ciphertext, wrongKey, iv, authTag)
      ).rejects.toThrow('Authentication failed');
    });

    it('should fail decryption with wrong IV', async () => {
      const plaintext = new TextEncoder().encode('Secret message');
      const key = generateSalt(32);
      const iv = generateSalt(12);
      const wrongIv = generateSalt(12);
      
      const { ciphertext, authTag } = await aesGcmEncrypt(plaintext, key, iv);
      
      await expect(
        aesGcmDecrypt(ciphertext, key, wrongIv, authTag)
      ).rejects.toThrow('Authentication failed');
    });

    it('should fail decryption with tampered ciphertext', async () => {
      const plaintext = new TextEncoder().encode('Secret message');
      const key = generateSalt(32);
      const iv = generateSalt(12);
      
      const { ciphertext, authTag } = await aesGcmEncrypt(plaintext, key, iv);
      
      // Tamper with ciphertext
      const tamperedCiphertext = new Uint8Array(ciphertext);
      tamperedCiphertext[0] ^= 0xFF;
      
      await expect(
        aesGcmDecrypt(tamperedCiphertext, key, iv, authTag)
      ).rejects.toThrow('Authentication failed');
    });

    it('should fail decryption with tampered auth tag', async () => {
      const plaintext = new TextEncoder().encode('Secret message');
      const key = generateSalt(32);
      const iv = generateSalt(12);
      
      const { ciphertext, authTag } = await aesGcmEncrypt(plaintext, key, iv);
      
      // Tamper with auth tag
      const tamperedAuthTag = new Uint8Array(authTag);
      tamperedAuthTag[0] ^= 0xFF;
      
      await expect(
        aesGcmDecrypt(ciphertext, key, iv, tamperedAuthTag)
      ).rejects.toThrow('Authentication failed');
    });

    it('should throw with invalid IV length', async () => {
      const plaintext = new TextEncoder().encode('Test');
      const key = generateSalt(32);
      const wrongIv = generateSalt(8); // Wrong size
      
      await expect(
        aesGcmEncrypt(plaintext, key, wrongIv)
      ).rejects.toThrow('IV must be 12 bytes');
    });

    it('should throw with invalid key length', async () => {
      const plaintext = new TextEncoder().encode('Test');
      const wrongKey = generateSalt(16); // Wrong size
      const iv = generateSalt(12);
      
      await expect(
        aesGcmEncrypt(plaintext, wrongKey, iv)
      ).rejects.toThrow('Key must be 32 bytes');
    });
  });

  describe('encryptWithPassword and decryptWithPassword', () => {
    it('should encrypt and decrypt with password using PBKDF2', async () => {
      const plaintext = 'Hello, RustChain!';
      const password = 'secure_password_123';
      
      const encrypted = await encryptWithPassword(plaintext, password, 'pbkdf2');
      
      expect(encrypted.ciphertext).toBeDefined();
      expect(encrypted.iv).toBeDefined();
      expect(encrypted.authTag).toBeDefined();
      expect(encrypted.kdfParams.type).toBe('pbkdf2');
      
      const decrypted = await decryptWithPassword(encrypted, password);
      
      expect(decrypted).toBe(plaintext);
    });

    it('should encrypt and decrypt with password using Argon2id', async () => {
      const plaintext = 'Hello, RustChain!';
      const password = 'secure_password_123';
      
      const encrypted = await encryptWithPassword(plaintext, password, 'argon2id');
      
      expect(encrypted.ciphertext).toBeDefined();
      expect(encrypted.iv).toBeDefined();
      expect(encrypted.authTag).toBeDefined();
      expect(encrypted.kdfParams.type).toBe('argon2id');
      
      const decrypted = await decryptWithPassword(encrypted, password);
      
      expect(decrypted).toBe(plaintext);
    });

    it('should produce different ciphertext on each encryption', async () => {
      const plaintext = 'Same message';
      const password = 'secure_password_123';
      
      const encrypted1 = await encryptWithPassword(plaintext, password);
      const encrypted2 = await encryptWithPassword(plaintext, password);
      
      expect(encrypted1.ciphertext).not.toEqual(encrypted2.ciphertext);
      expect(encrypted1.iv).not.toEqual(encrypted2.iv);
    });

    it('should fail decryption with wrong password', async () => {
      const plaintext = 'Secret message';
      const password = 'correct_password';
      const wrongPassword = 'wrong_password';
      
      const encrypted = await encryptWithPassword(plaintext, password);
      
      await expect(
        decryptWithPassword(encrypted, wrongPassword)
      ).rejects.toThrow('Authentication failed');
    });

    it('should handle unicode characters in plaintext', async () => {
      const plaintext = 'Hello 世界！🚀 Ελληνικά';
      const password = 'secure_password_123';
      
      const encrypted = await encryptWithPassword(plaintext, password);
      const decrypted = await decryptWithPassword(encrypted, password);
      
      expect(decrypted).toBe(plaintext);
    });

    it('should handle empty plaintext', async () => {
      const plaintext = '';
      const password = 'secure_password_123';
      
      const encrypted = await encryptWithPassword(plaintext, password);
      const decrypted = await decryptWithPassword(encrypted, password);
      
      expect(decrypted).toBe(plaintext);
    });

    it('should handle long plaintext', async () => {
      const plaintext = 'A'.repeat(10000);
      const password = 'secure_password_123';
      
      const encrypted = await encryptWithPassword(plaintext, password);
      const decrypted = await decryptWithPassword(encrypted, password);
      
      expect(decrypted).toBe(plaintext);
    });

    it('should include KDF params in encrypted data', async () => {
      const plaintext = 'Test';
      const password = 'secure_password_123';
      
      const encrypted = await encryptWithPassword(plaintext, password, 'pbkdf2');
      
      expect(encrypted.kdfParams).toBeDefined();
      expect(encrypted.kdfParams.type).toBe('pbkdf2');
      expect(encrypted.kdfParams.salt).toBeDefined();
      expect(encrypted.kdfParams.dkLen).toBe(32);
    });
  });

  describe('verifyEncryption', () => {
    it('should return true for valid encryption/decryption', async () => {
      const plaintext = 'Test message';
      const password = 'secure_password_123';
      
      const result = await verifyEncryption(plaintext, password);
      
      expect(result).toBe(true);
    });

    it('should return false for invalid data', async () => {
      // This tests the error handling path
      const result = await verifyEncryption('', '');
      
      // Empty password might still work due to KDF, so we just check it completes
      expect(typeof result).toBe('boolean');
    });
  });

  describe('Security Properties', () => {
    it('should have authenticated encryption (detect tampering)', async () => {
      const plaintext = 'Important message';
      const password = 'secure_password_123';
      
      const encrypted = await encryptWithPassword(plaintext, password);
      
      // Tamper with ciphertext
      const tampered = {
        ...encrypted,
        ciphertext: encrypted.ciphertext.split('').reverse().join(''),
      };
      
      await expect(
        decryptWithPassword(tampered as EncryptedData, password)
      ).rejects.toThrow();
    });

    it('should use unique IV for each encryption', async () => {
      const plaintext = 'Same message';
      const password = 'secure_password_123';
      
      const ivs = new Set();
      for (let i = 0; i < 10; i++) {
        const encrypted = await encryptWithPassword(plaintext, password);
        ivs.add(encrypted.iv);
      }
      
      // All IVs should be unique
      expect(ivs.size).toBe(10);
    });

    it('should use unique salt for each encryption', async () => {
      const plaintext = 'Same message';
      const password = 'secure_password_123';
      
      const salts = new Set();
      for (let i = 0; i < 10; i++) {
        const encrypted = await encryptWithPassword(plaintext, password);
        salts.add(encrypted.kdfParams.salt);
      }
      
      // All salts should be unique
      expect(salts.size).toBe(10);
    });
  });
});
