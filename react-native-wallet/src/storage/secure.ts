/**
 * Secure Wallet Storage (Hardened)
 *
 * Provides encrypted storage for wallet keys using AES-256-GCM
 * with PBKDF2/Argon2id key derivation
 *
 * Issue #785: Secure wallet storage hardening
 * - AES-256-GCM authenticated encryption
 * - PBKDF2-SHA256 with 600,000+ iterations
 * - Argon2id-like memory-hard KDF option
 * - Secure export with re-authentication
 * - Correct key derivation (no password in router)
 */

import * as SecureStore from 'expo-secure-store';
import { KeyPair, secretKeyToHex, keyPairFromHex, publicKeyToBase58 } from '../utils/crypto';
import { encryptWithPassword, decryptWithPassword, EncryptedData } from '../utils/aes-gcm';
import { KDFType } from '../utils/kdf';

/**
 * Wallet metadata stored alongside encrypted keys
 */
export interface WalletMetadata {
  name: string;
  address: string;
  createdAt: number;
  network?: string;
  kdfType?: KDFType;
}

/**
 * Stored wallet format
 */
export interface StoredWallet {
  metadata: WalletMetadata;
  encrypted: EncryptedData;
  version: number;
}

const WALLET_PREFIX = 'wallet:';
const WALLET_LIST_KEY = 'rustchain_wallets';
const STORAGE_VERSION = 2; // Version 2: AES-GCM + proper KDF

/**
 * Secure wallet storage manager
 */
export class WalletStorage {
  /**
   * Save a wallet with password encryption using AES-256-GCM
   * 
   * @param name - Wallet name
   * @param keyPair - Ed25519 key pair
   * @param password - User password (min 8 chars recommended)
   * @param kdfType - Key derivation function ('pbkdf2' or 'argon2id')
   * @returns Wallet address (Base58-encoded public key)
   */
  static async save(
    name: string,
    keyPair: KeyPair,
    password: string,
    kdfType: KDFType = 'pbkdf2'
  ): Promise<string> {
    // Validate password strength
    if (password.length < 8) {
      throw new Error('Password must be at least 8 characters');
    }

    const address = publicKeyToBase58(keyPair.publicKey);

    // Create wallet data to encrypt
    const walletData = JSON.stringify({
      secretKey: secretKeyToHex(keyPair.secretKey),
      address,
    });

    // Encrypt with AES-256-GCM
    const encrypted = await encryptWithPassword(walletData, password, kdfType);

    // Create stored wallet
    const stored: StoredWallet = {
      metadata: {
        name,
        address,
        createdAt: Date.now(),
        network: 'mainnet',
        kdfType,
      },
      encrypted,
      version: STORAGE_VERSION,
    };

    // Save to SecureStore
    const key = `${WALLET_PREFIX}${name}`;
    await SecureStore.setItemAsync(key, JSON.stringify(stored));

    // Update wallet list
    await this.addToWalletList(name);

    return address;
  }

  /**
   * Load a wallet by name and password
   * 
   * @param name - Wallet name
   * @param password - User password
   * @returns Decrypted key pair
   * @throws Error if wallet not found or password incorrect
   */
  static async load(name: string, password: string): Promise<KeyPair> {
    const key = `${WALLET_PREFIX}${name}`;
    const storedJson = await SecureStore.getItemAsync(key);

    if (!storedJson) {
      throw new Error(`Wallet "${name}" not found`);
    }

    let stored: StoredWallet;
    try {
      stored = JSON.parse(storedJson);
    } catch (e) {
      throw new Error('Invalid wallet data format');
    }

    // Decrypt with password
    let decryptedJson: string;
    try {
      decryptedJson = await decryptWithPassword(stored.encrypted, password);
    } catch (e) {
      // Decryption failed - wrong password or corrupted data
      throw new Error('Invalid password or corrupted wallet data');
    }

    let walletData: { secretKey: string; address: string };
    try {
      walletData = JSON.parse(decryptedJson);
    } catch (e) {
      throw new Error('Invalid wallet data format');
    }

    // Import key pair
    return keyPairFromHex(walletData.secretKey);
  }

  /**
   * Delete a wallet
   */
  static async delete(name: string): Promise<void> {
    const key = `${WALLET_PREFIX}${name}`;
    await SecureStore.deleteItemAsync(key);
    await this.removeFromWalletList(name);
  }

  /**
   * List all stored wallet names
   */
  static async list(): Promise<string[]> {
    const listJson = await SecureStore.getItemAsync(WALLET_LIST_KEY);
    if (!listJson) return [];
    return JSON.parse(listJson);
  }

  /**
   * Check if a wallet exists
   */
  static async exists(name: string): Promise<boolean> {
    const key = `${WALLET_PREFIX}${name}`;
    const stored = await SecureStore.getItemAsync(key);
    return stored !== null;
  }

  /**
   * Get wallet metadata without decrypting
   */
  static async getMetadata(name: string): Promise<WalletMetadata | null> {
    const key = `${WALLET_PREFIX}${name}`;
    const storedJson = await SecureStore.getItemAsync(key);
    if (!storedJson) return null;

    try {
      const stored: StoredWallet = JSON.parse(storedJson);
      return stored.metadata;
    } catch {
      return null;
    }
  }

  /**
   * Add wallet to list
   */
  private static async addToWalletList(name: string): Promise<void> {
    const list = await this.list();
    if (!list.includes(name)) {
      list.push(name);
      await SecureStore.setItemAsync(WALLET_LIST_KEY, JSON.stringify(list));
    }
  }

  /**
   * Remove wallet from list
   */
  private static async removeFromWalletList(name: string): Promise<void> {
    const list = await this.list();
    const filtered = list.filter(n => n !== name);
    await SecureStore.setItemAsync(WALLET_LIST_KEY, JSON.stringify(filtered));
  }

  /**
   * Export wallet as encrypted backup string
   * Requires re-authentication with password for security
   * 
   * @param name - Wallet name
   * @param password - User password for re-authentication
   * @returns Encrypted wallet backup JSON
   */
  static async export(name: string, password: string): Promise<string> {
    // First verify password by attempting to load
    await this.load(name, password);
    
    const key = `${WALLET_PREFIX}${name}`;
    const storedJson = await SecureStore.getItemAsync(key);

    if (!storedJson) {
      throw new Error(`Wallet "${name}" not found`);
    }

    return storedJson;
  }

  /**
   * Import wallet from encrypted backup
   * 
   * @param backupJson - Encrypted wallet backup JSON
   * @returns Wallet name
   */
  static async import(backupJson: string): Promise<string> {
    let stored: StoredWallet;
    try {
      stored = JSON.parse(backupJson);
    } catch (e) {
      throw new Error('Invalid backup format');
    }

    // Validate structure
    if (!stored.metadata || !stored.encrypted || !stored.version) {
      throw new Error('Invalid backup structure');
    }

    const key = `${WALLET_PREFIX}${stored.metadata.name}`;

    // Check if already exists
    const existing = await SecureStore.getItemAsync(key);
    if (existing) {
      throw new Error(`Wallet "${stored.metadata.name}" already exists`);
    }

    // Save
    await SecureStore.setItemAsync(key, backupJson);
    await this.addToWalletList(stored.metadata.name);

    return stored.metadata.name;
  }

  /**
   * Change wallet password
   * Requires old password for verification
   * 
   * @param name - Wallet name
   * @param oldPassword - Current password
   * @param newPassword - New password
   */
  static async changePassword(
    name: string,
    oldPassword: string,
    newPassword: string
  ): Promise<void> {
    if (newPassword.length < 8) {
      throw new Error('New password must be at least 8 characters');
    }

    // Load wallet with old password
    const keyPair = await this.load(name, oldPassword);
    
    // Get metadata
    const metadata = await this.getMetadata(name);
    if (!metadata) {
      throw new Error('Wallet not found');
    }

    // Re-encrypt with new password
    const walletData = JSON.stringify({
      secretKey: secretKeyToHex(keyPair.secretKey),
      address: metadata.address,
    });

    const kdfType = metadata.kdfType ?? 'pbkdf2';
    const encrypted = await encryptWithPassword(walletData, newPassword, kdfType);

    const stored: StoredWallet = {
      metadata: {
        ...metadata,
        kdfType,
      },
      encrypted,
      version: STORAGE_VERSION,
    };

    const key = `${WALLET_PREFIX}${name}`;
    await SecureStore.setItemAsync(key, JSON.stringify(stored));
  }

  /**
   * Verify wallet password without loading the key
   * 
   * @param name - Wallet name
   * @param password - Password to verify
   * @returns true if password is correct
   */
  static async verifyPassword(name: string, password: string): Promise<boolean> {
    try {
      await this.load(name, password);
      return true;
    } catch {
      return false;
    }
  }
}

/**
 * Nonce storage for replay protection
 */
export class NonceStore {
  private static KEY_PREFIX = 'nonce:';

  /**
   * Mark a nonce as used
   */
  static async markUsed(address: string, nonce: number): Promise<void> {
    const key = `${this.KEY_PREFIX}${address}`;
    const existingJson = await SecureStore.getItemAsync(key);
    const nonces: number[] = existingJson ? JSON.parse(existingJson) : [];

    if (!nonces.includes(nonce)) {
      nonces.push(nonce);
      // Limit stored nonces to prevent unbounded growth
      if (nonces.length > 1000) {
        nonces.shift(); // Remove oldest
      }
      await SecureStore.setItemAsync(key, JSON.stringify(nonces));
    }
  }

  /**
   * Check if a nonce has been used
   */
  static async isUsed(address: string, nonce: number): Promise<boolean> {
    const key = `${this.KEY_PREFIX}${address}`;
    const existingJson = await SecureStore.getItemAsync(key);
    if (!existingJson) return false;

    const nonces: number[] = JSON.parse(existingJson);
    return nonces.includes(nonce);
  }

  /**
   * Get next suggested nonce
   */
  static async getNextNonce(address: string): Promise<number> {
    const key = `${this.KEY_PREFIX}${address}`;
    const existingJson = await SecureStore.getItemAsync(key);
    if (!existingJson) return 0;

    const nonces: number[] = JSON.parse(existingJson);
    if (nonces.length === 0) return 0;

    return Math.max(...nonces) + 1;
  }

  /**
   * Validate nonce (not used)
   */
  static async validateNonce(address: string, nonce: number): Promise<boolean> {
    return !(await this.isUsed(address, nonce));
  }
}
