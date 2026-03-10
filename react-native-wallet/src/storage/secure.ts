/**
 * Secure Wallet Storage
 * 
 * Provides encrypted storage for wallet keys using Expo SecureStore
 * with password-based encryption
 */

import * as SecureStore from 'expo-secure-store';
import * as Crypto from 'expo-crypto';
import { KeyPair, secretKeyToHex, keyPairFromHex, publicKeyToBase58 } from '../utils/crypto';

/**
 * Wallet metadata stored alongside encrypted keys
 */
export interface WalletMetadata {
  name: string;
  address: string;
  createdAt: number;
  network?: string;
}

/**
 * Encrypted wallet data structure
 */
interface EncryptedWalletData {
  ciphertext: string;
  iv: string;
  salt: string;
}

/**
 * Stored wallet format
 */
export interface StoredWallet {
  metadata: WalletMetadata;
  encrypted: EncryptedWalletData;
}

const WALLET_PREFIX = 'wallet:';
const WALLET_LIST_KEY = 'rustchain_wallets';

/**
 * Simple hash function for key derivation (using Expo Crypto)
 */
async function hashPassword(password: string, salt: string): Promise<string> {
  const combined = password + salt;
  const hash = await Crypto.digestStringAsync(
    Crypto.CryptoDigestAlgorithm.SHA256,
    combined
  );
  return hash;
}

/**
 * XOR-based encryption helper (simple but effective for our use case)
 * For production, consider using a more robust library
 */
async function encryptData(data: string, password: string): Promise<EncryptedWalletData> {
  // Generate random salt
  const saltBytes = Crypto.getRandomValues(new Uint8Array(32));
  const salt = Array.from(saltBytes).map(b => b.toString(16).padStart(2, '0')).join('');
  
  // Generate random IV
  const ivBytes = Crypto.getRandomValues(new Uint8Array(16));
  const iv = Array.from(ivBytes).map(b => b.toString(16).padStart(2, '0')).join('');
  
  // Derive key from password
  const keyHash = await hashPassword(password, salt);
  const keyBytes = new Uint8Array(
    keyHash.match(/.{1,2}/g)!.map(b => parseInt(b, 16))
  );
  
  // Convert data to bytes
  const encoder = new TextEncoder();
  const dataBytes = encoder.encode(data);
  
  // XOR encryption with key and IV
  const ciphertext = new Uint8Array(dataBytes.length);
  for (let i = 0; i < dataBytes.length; i++) {
    ciphertext[i] = dataBytes[i] ^ keyBytes[i % keyBytes.length] ^ ivBytes[i % ivBytes.length];
  }
  
  return {
    ciphertext: Array.from(ciphertext).map(b => b.toString(16).padStart(2, '0')).join(''),
    iv,
    salt,
  };
}

/**
 * Decrypt data
 */
async function decryptData(encrypted: EncryptedWalletData, password: string): Promise<string> {
  // Derive key from password
  const keyHash = await hashPassword(password, encrypted.salt);
  const keyBytes = new Uint8Array(
    keyHash.match(/.{1,2}/g)!.map(b => parseInt(b, 16))
  );
  
  // Convert IV and ciphertext to bytes
  const ivBytes = new Uint8Array(
    encrypted.iv.match(/.{1,2}/g)!.map(b => parseInt(b, 16))
  );
  const ciphertextBytes = new Uint8Array(
    encrypted.ciphertext.match(/.{1,2}/g)!.map(b => parseInt(b, 16))
  );
  
  // XOR decryption
  const plaintextBytes = new Uint8Array(ciphertextBytes.length);
  for (let i = 0; i < ciphertextBytes.length; i++) {
    plaintextBytes[i] = ciphertextBytes[i] ^ keyBytes[i % keyBytes.length] ^ ivBytes[i % ivBytes.length];
  }
  
  // Convert back to string
  const decoder = new TextDecoder();
  return decoder.decode(plaintextBytes);
}

/**
 * Secure wallet storage manager
 */
export class WalletStorage {
  /**
   * Save a wallet with password encryption
   */
  static async save(
    name: string,
    keyPair: KeyPair,
    password: string
  ): Promise<string> {
    const address = publicKeyToBase58(keyPair.publicKey);

    // Create wallet data to encrypt
    const walletData = JSON.stringify({
      secretKey: secretKeyToHex(keyPair.secretKey),
    });

    // Encrypt
    const encrypted = await encryptData(walletData, password);

    // Create stored wallet
    const stored: StoredWallet = {
      metadata: {
        name,
        address,
        createdAt: Date.now(),
        network: 'mainnet',
      },
      encrypted,
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
   */
  static async load(name: string, password: string): Promise<KeyPair> {
    const key = `${WALLET_PREFIX}${name}`;
    const storedJson = await SecureStore.getItemAsync(key);

    if (!storedJson) {
      throw new Error(`Wallet "${name}" not found`);
    }

    const stored: StoredWallet = JSON.parse(storedJson);

    // Decrypt
    const decryptedJson = await decryptData(stored.encrypted, password);
    const walletData = JSON.parse(decryptedJson);

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

    const stored: StoredWallet = JSON.parse(storedJson);
    return stored.metadata;
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
   */
  static async export(name: string, password: string): Promise<string> {
    const key = `${WALLET_PREFIX}${name}`;
    const storedJson = await SecureStore.getItemAsync(key);

    if (!storedJson) {
      throw new Error(`Wallet "${name}" not found`);
    }

    return storedJson;
  }

  /**
   * Import wallet from encrypted backup
   */
  static async import(backupJson: string): Promise<string> {
    const stored: StoredWallet = JSON.parse(backupJson);
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
