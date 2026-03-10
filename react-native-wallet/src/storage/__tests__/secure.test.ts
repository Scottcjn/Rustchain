/**
 * Secure Wallet Storage Tests (Hardened)
 *
 * Issue #785: Security hardening tests
 * - AES-GCM encryption
 * - PBKDF2/Argon2 KDF
 * - Secure export with re-authentication
 */

import * as SecureStore from 'expo-secure-store';
import { WalletStorage, NonceStore } from '../secure';
import { generateKeyPair, publicKeyToBase58, secretKeyToHex } from '../../utils/crypto';
import { encryptWithPassword } from '../../utils/aes-gcm';

// Mock SecureStore
jest.mock('expo-secure-store', () => ({
  setItemAsync: jest.fn(),
  getItemAsync: jest.fn(),
  deleteItemAsync: jest.fn(),
}));

describe('WalletStorage (Hardened)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('save', () => {
    it('should save wallet with AES-GCM encryption', async () => {
      const keyPair = generateKeyPair();
      const name = 'Test Wallet';
      const password = 'secure_password_123';

      (SecureStore.setItemAsync as jest.Mock).mockResolvedValue(undefined);

      const address = await WalletStorage.save(name, keyPair, password);

      expect(address).toBe(publicKeyToBase58(keyPair.publicKey));
      expect(SecureStore.setItemAsync).toHaveBeenCalled();
    });

    it('should use PBKDF2 KDF by default', async () => {
      const keyPair = generateKeyPair();
      const name = 'Test Wallet';
      const password = 'secure_password_123';

      (SecureStore.setItemAsync as jest.Mock).mockResolvedValue(undefined);

      await WalletStorage.save(name, keyPair, password);

      const call = (SecureStore.setItemAsync as jest.Mock).mock.calls[0];
      const stored = JSON.parse(call[1]);
      
      expect(stored.encrypted.kdfParams.type).toBe('pbkdf2');
    });

    it('should support Argon2id KDF', async () => {
      const keyPair = generateKeyPair();
      const name = 'Test Wallet';
      const password = 'secure_password_123';

      (SecureStore.setItemAsync as jest.Mock).mockResolvedValue(undefined);

      await WalletStorage.save(name, keyPair, password, 'argon2id');

      const call = (SecureStore.setItemAsync as jest.Mock).mock.calls[0];
      const stored = JSON.parse(call[1]);
      
      expect(stored.encrypted.kdfParams.type).toBe('argon2id');
    });

    it('should reject weak passwords', async () => {
      const keyPair = generateKeyPair();
      const name = 'Test Wallet';
      const password = 'short';

      await expect(
        WalletStorage.save(name, keyPair, password)
      ).rejects.toThrow('at least 8 characters');
    });

    it('should store wallet metadata', async () => {
      const keyPair = generateKeyPair();
      const name = 'Test Wallet';
      const password = 'secure_password_123';

      (SecureStore.setItemAsync as jest.Mock).mockResolvedValue(undefined);

      await WalletStorage.save(name, keyPair, password);

      const call = (SecureStore.setItemAsync as jest.Mock).mock.calls[0];
      const stored = JSON.parse(call[1]);
      
      expect(stored.metadata.name).toBe(name);
      expect(stored.metadata.address).toBe(publicKeyToBase58(keyPair.publicKey));
      expect(stored.metadata.createdAt).toBeDefined();
      expect(stored.version).toBe(2); // Storage version 2
    });
  });

  describe('load', () => {
    it('should load wallet with correct password', async () => {
      const keyPair = generateKeyPair();
      const name = 'Test Wallet';
      const password = 'secure_password_123';
      const address = publicKeyToBase58(keyPair.publicKey);

      // Create actual encrypted data
      const walletData = JSON.stringify({
        secretKey: secretKeyToHex(keyPair.secretKey),
        address,
      });
      const encrypted = await encryptWithPassword(walletData, password, 'pbkdf2');

      const storedWallet = {
        metadata: { name, address, createdAt: Date.now(), network: 'mainnet', kdfType: 'pbkdf2' as const },
        encrypted,
        version: 2,
      };

      (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(JSON.stringify(storedWallet));

      const loadedKeyPair = await WalletStorage.load(name, password);

      expect(loadedKeyPair.publicKey).toEqual(keyPair.publicKey);
      expect(loadedKeyPair.secretKey).toEqual(keyPair.secretKey);
    });

    it('should reject wrong password', async () => {
      const name = 'Test Wallet';
      const correctPassword = 'correct_password';
      const wrongPassword = 'wrong_password';

      // Create encrypted data with correct password
      const keyPair = generateKeyPair();
      const address = publicKeyToBase58(keyPair.publicKey);
      const walletData = JSON.stringify({
        secretKey: secretKeyToHex(keyPair.secretKey),
        address,
      });
      const encrypted = await encryptWithPassword(walletData, correctPassword, 'pbkdf2');

      const storedWallet = {
        metadata: { name, address, createdAt: Date.now(), network: 'mainnet', kdfType: 'pbkdf2' as const },
        encrypted,
        version: 2,
      };

      (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(JSON.stringify(storedWallet));

      await expect(
        WalletStorage.load(name, wrongPassword)
      ).rejects.toThrow('Invalid password');
    });

    it('should reject non-existent wallet', async () => {
      (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(null);

      await expect(
        WalletStorage.load('NonExistent', 'password')
      ).rejects.toThrow('not found');
    });

    it('should reject corrupted data', async () => {
      (SecureStore.getItemAsync as jest.Mock).mockResolvedValue('invalid json');

      await expect(
        WalletStorage.load('Test', 'password')
      ).rejects.toThrow('Invalid wallet data format');
    });
  });

  describe('export (secure with re-auth)', () => {
    it('should export wallet after verifying password', async () => {
      const keyPair = generateKeyPair();
      const name = 'Test Wallet';
      const password = 'secure_password_123';
      const address = publicKeyToBase58(keyPair.publicKey);

      // Create encrypted data
      const walletData = JSON.stringify({
        secretKey: secretKeyToHex(keyPair.secretKey),
        address,
      });
      const encrypted = await encryptWithPassword(walletData, password, 'pbkdf2');

      const storedWallet = {
        metadata: { name, address, createdAt: Date.now(), network: 'mainnet', kdfType: 'pbkdf2' as const },
        encrypted,
        version: 2,
      };

      (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(JSON.stringify(storedWallet));

      const exported = await WalletStorage.export(name, password);
      const parsed = JSON.parse(exported);

      expect(parsed.metadata.name).toBe(name);
      expect(parsed.encrypted).toBeDefined();
    });

    it('should reject export with wrong password', async () => {
      const name = 'Test Wallet';
      const correctPassword = 'correct_password';
      const wrongPassword = 'wrong_password';

      const keyPair = generateKeyPair();
      const address = publicKeyToBase58(keyPair.publicKey);
      const walletData = JSON.stringify({
        secretKey: secretKeyToHex(keyPair.secretKey),
        address,
      });
      const encrypted = await encryptWithPassword(walletData, correctPassword, 'pbkdf2');

      const storedWallet = {
        metadata: { name, address, createdAt: Date.now(), network: 'mainnet', kdfType: 'pbkdf2' as const },
        encrypted,
        version: 2,
      };

      (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(JSON.stringify(storedWallet));

      await expect(
        WalletStorage.export(name, wrongPassword)
      ).rejects.toThrow();
    });
  });

  describe('import', () => {
    it('should import wallet from backup', async () => {
      const keyPair = generateKeyPair();
      const name = 'Imported Wallet';
      const address = publicKeyToBase58(keyPair.publicKey);
      const password = 'secure_password_123';

      // Create encrypted backup
      const walletData = JSON.stringify({
        secretKey: secretKeyToHex(keyPair.secretKey),
        address,
      });
      const encrypted = await encryptWithPassword(walletData, password, 'pbkdf2');

      const backup = JSON.stringify({
        metadata: { name, address, createdAt: Date.now(), network: 'mainnet', kdfType: 'pbkdf2' as const },
        encrypted,
        version: 2,
      });

      (SecureStore.setItemAsync as jest.Mock).mockResolvedValue(undefined);
      (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(null); // Not exists

      const importedName = await WalletStorage.import(backup);

      expect(importedName).toBe(name);
      expect(SecureStore.setItemAsync).toHaveBeenCalled();
    });

    it('should reject duplicate import', async () => {
      const name = 'Existing Wallet';
      const backup = JSON.stringify({
        metadata: { name, address: 'RTC123', createdAt: Date.now(), kdfType: 'pbkdf2' },
        encrypted: { ciphertext: '', iv: '', authTag: '', kdfParams: { type: 'pbkdf2', salt: '', dkLen: 32 } },
        version: 2,
      });

      (SecureStore.getItemAsync as jest.Mock).mockResolvedValue('existing data');

      await expect(
        WalletStorage.import(backup)
      ).rejects.toThrow('already exists');
    });

    it('should reject invalid backup format', async () => {
      await expect(
        WalletStorage.import('invalid json')
      ).rejects.toThrow('Invalid backup format');
    });

    it('should reject backup missing required fields', async () => {
      const backup = JSON.stringify({
        metadata: { name: 'Test' },
        // Missing encrypted and version
      });

      await expect(
        WalletStorage.import(backup)
      ).rejects.toThrow('Invalid backup structure');
    });
  });

  describe('changePassword', () => {
    it('should change password successfully', async () => {
      const keyPair = generateKeyPair();
      const name = 'Test Wallet';
      const oldPassword = 'old_password_123';
      const newPassword = 'new_password_456';
      const address = publicKeyToBase58(keyPair.publicKey);

      // Create encrypted data with old password
      const walletData = JSON.stringify({
        secretKey: secretKeyToHex(keyPair.secretKey),
        address,
      });
      const encrypted = await encryptWithPassword(walletData, oldPassword, 'pbkdf2');

      const storedWallet = {
        metadata: { name, address, createdAt: Date.now(), network: 'mainnet', kdfType: 'pbkdf2' as const },
        encrypted,
        version: 2,
      };

      // Mock: load() -> getMetadata() -> list() -> setItemAsync()
      (SecureStore.getItemAsync as jest.Mock)
        .mockResolvedValueOnce(JSON.stringify(storedWallet)) // For load
        .mockResolvedValueOnce(JSON.stringify(storedWallet)) // For getMetadata
        .mockResolvedValueOnce(JSON.stringify([name])); // For list
      (SecureStore.setItemAsync as jest.Mock).mockResolvedValue(undefined);

      await WalletStorage.changePassword(name, oldPassword, newPassword);

      expect(SecureStore.setItemAsync).toHaveBeenCalled();
    });

    it('should reject weak new password', async () => {
      const name = 'Test Wallet';

      await expect(
        WalletStorage.changePassword(name, 'old_password', 'weak')
      ).rejects.toThrow('at least 8 characters');
    });
  });

  describe('verifyPassword', () => {
    it('should return true for correct password', async () => {
      const keyPair = generateKeyPair();
      const name = 'Test Wallet';
      const password = 'secure_password_123';
      const address = publicKeyToBase58(keyPair.publicKey);

      const walletData = JSON.stringify({
        secretKey: secretKeyToHex(keyPair.secretKey),
        address,
      });
      const encrypted = await encryptWithPassword(walletData, password, 'pbkdf2');

      const storedWallet = {
        metadata: { name, address, createdAt: Date.now(), network: 'mainnet', kdfType: 'pbkdf2' as const },
        encrypted,
        version: 2,
      };

      // Reset mock and set up for this test
      (SecureStore.getItemAsync as jest.Mock).mockReset();
      (SecureStore.getItemAsync as jest.Mock).mockImplementation(() => 
        Promise.resolve(JSON.stringify(storedWallet))
      );

      const valid = await WalletStorage.verifyPassword(name, password);

      expect(valid).toBe(true);
    });

    it('should return false for wrong password', async () => {
      const keyPair = generateKeyPair();
      const name = 'Test Wallet';
      const password = 'secure_password_123';
      const address = publicKeyToBase58(keyPair.publicKey);

      const walletData = JSON.stringify({
        secretKey: secretKeyToHex(keyPair.secretKey),
        address,
      });
      const encrypted = await encryptWithPassword(walletData, password, 'pbkdf2');

      const storedWallet = {
        metadata: { name, address, createdAt: Date.now(), network: 'mainnet', kdfType: 'pbkdf2' as const },
        encrypted,
        version: 2,
      };

      // Reset mock and set up for this test
      (SecureStore.getItemAsync as jest.Mock).mockReset();
      (SecureStore.getItemAsync as jest.Mock).mockImplementation(() => 
        Promise.resolve(JSON.stringify(storedWallet))
      );

      const valid = await WalletStorage.verifyPassword(name, 'wrong_password');

      expect(valid).toBe(false);
    });
  });
});

describe('NonceStore', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('markUsed and isUsed', () => {
    it('should mark nonce as used', async () => {
      const address = 'RTC123';
      const nonce = 5;

      (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(null);
      (SecureStore.setItemAsync as jest.Mock).mockResolvedValue(undefined);

      await NonceStore.markUsed(address, nonce);

      expect(SecureStore.setItemAsync).toHaveBeenCalled();
    });

    it('should detect used nonce', async () => {
      const address = 'RTC123';
      const nonce = 5;

      (SecureStore.getItemAsync as jest.Mock)
        .mockResolvedValueOnce(JSON.stringify([5, 6, 7])) // For isUsed
        .mockResolvedValueOnce(null); // For cleanup

      const isUsed = await NonceStore.isUsed(address, nonce);

      expect(isUsed).toBe(true);
    });

    it('should return false for unused nonce', async () => {
      const address = 'RTC123';
      const nonce = 10;

      (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(JSON.stringify([5, 6, 7]));

      const isUsed = await NonceStore.isUsed(address, nonce);

      expect(isUsed).toBe(false);
    });
  });

  describe('getNextNonce', () => {
    it('should return 0 for new address', async () => {
      (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(null);

      const nonce = await NonceStore.getNextNonce('RTC123');

      expect(nonce).toBe(0);
    });

    it('should return max + 1 for existing nonces', async () => {
      (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(JSON.stringify([1, 5, 3, 10]));

      const nonce = await NonceStore.getNextNonce('RTC123');

      expect(nonce).toBe(11);
    });
  });

  describe('validateNonce', () => {
    it('should return true for unused nonce', async () => {
      (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(JSON.stringify([1, 2, 3]));

      const valid = await NonceStore.validateNonce('RTC123', 10);

      expect(valid).toBe(true);
    });

    it('should return false for used nonce', async () => {
      (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(JSON.stringify([1, 2, 3, 10]));

      const valid = await NonceStore.validateNonce('RTC123', 10);

      expect(valid).toBe(false);
    });
  });
});
