/**
 * Crypto Utilities Tests
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
} from '../crypto';

describe('Crypto Utilities', () => {
  describe('generateKeyPair', () => {
    it('should generate a valid key pair', () => {
      const keyPair = generateKeyPair();
      
      expect(keyPair.publicKey).toBeDefined();
      expect(keyPair.secretKey).toBeDefined();
      expect(keyPair.publicKey.length).toBe(32);
      expect(keyPair.secretKey.length).toBe(64);
    });

    it('should generate unique key pairs', () => {
      const keyPair1 = generateKeyPair();
      const keyPair2 = generateKeyPair();
      
      expect(keyPair1.publicKey).not.toEqual(keyPair2.publicKey);
      expect(keyPair1.secretKey).not.toEqual(keyPair2.secretKey);
    });
  });

  describe('publicKeyToHex', () => {
    it('should convert public key to hex string', () => {
      const keyPair = generateKeyPair();
      const hex = publicKeyToHex(keyPair.publicKey);
      
      expect(hex.length).toBe(64);
      expect(/^[0-9a-f]+$/.test(hex)).toBe(true);
    });
  });

  describe('publicKeyToBase58', () => {
    it('should convert public key to Base58 string', () => {
      const keyPair = generateKeyPair();
      const base58 = publicKeyToBase58(keyPair.publicKey);
      
      expect(base58.length).toBeGreaterThanOrEqual(40);
      // Base58 doesn't contain 0, O, I, l
      expect(/[0OlI]/.test(base58)).toBe(false);
    });
  });

  describe('keyPairFromHex', () => {
    it('should create key pair from hex secret key', () => {
      const original = generateKeyPair();
      const hex = secretKeyToHex(original.secretKey);
      
      const imported = keyPairFromHex(hex);
      
      expect(publicKeyToHex(imported.publicKey)).toBe(publicKeyToHex(original.publicKey));
    });
  });

  describe('signMessage and verifySignature', () => {
    it('should sign and verify a message', () => {
      const keyPair = generateKeyPair();
      const message = new TextEncoder().encode('Hello, RustChain!');
      
      const signature = signMessage(message, keyPair.secretKey);
      const valid = verifySignature(message, signature, keyPair.publicKey);
      
      expect(signature.length).toBe(64);
      expect(valid).toBe(true);
    });

    it('should fail verification with wrong public key', () => {
      const keyPair1 = generateKeyPair();
      const keyPair2 = generateKeyPair();
      const message = new TextEncoder().encode('Test message');
      
      const signature = signMessage(message, keyPair1.secretKey);
      const valid = verifySignature(message, signature, keyPair2.publicKey);
      
      expect(valid).toBe(false);
    });

    it('should fail verification with tampered signature', () => {
      const keyPair = generateKeyPair();
      const message = new TextEncoder().encode('Test message');
      
      const signature = signMessage(message, keyPair.secretKey);
      const tampered = new Uint8Array(signature);
      tampered[0] ^= 0xFF;
      
      const valid = verifySignature(message, tampered, keyPair.publicKey);
      
      expect(valid).toBe(false);
    });
  });

  describe('signString and verifySignatureHex', () => {
    it('should sign and verify a string message', () => {
      const keyPair = generateKeyPair();
      const message = 'Hello, RustChain!';
      
      const signature = signString(message, keyPair.secretKey);
      const valid = verifySignatureHex(message, signature, keyPair.publicKey);
      
      expect(signature.length).toBe(128); // 64 bytes hex
      expect(valid).toBe(true);
    });
  });
});
