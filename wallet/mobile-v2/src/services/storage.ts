/**
 * Secure Wallet Storage
 *
 * AES-256-GCM encrypted key storage backed by expo-secure-store.
 * PBKDF2-SHA256 key derivation with 600k iterations (production).
 */

import * as SecureStore from 'expo-secure-store';
import * as Crypto from 'expo-crypto';
import type {
  KeyPair,
  KDFType,
  KDFParams,
  EncryptedData,
  WalletMetadata,
  StoredWallet,
} from '../types';
import {
  secretKeyToHex,
  keyPairFromHex,
  publicKeyToHex,
  publicKeyToRtcAddress,
  publicKeyHexToRtcAddress,
  isValidAddress,
} from './wallet';

// ── Constants ───────────────────────────────────────────────────────────────

const WALLET_PREFIX = 'wallet:';
const WALLET_LIST_KEY = 'rustchain_wallets';
const MNEMONIC_PREFIX = 'mnemonic:';
const STORAGE_VERSION = 2;
const AES_KEY_SIZE = 32;
const GCM_IV_SIZE = 12;
const GCM_TAG_SIZE = 16;

function isTestEnv(): boolean {
  return typeof process !== 'undefined' && process.env.JEST_WORKER_ID !== undefined;
}

// ── KDF ─────────────────────────────────────────────────────────────────────

function generateSalt(len = 32): Uint8Array {
  return Crypto.getRandomValues(new Uint8Array(len));
}

function saltToHex(salt: Uint8Array): string {
  return Array.from(salt).map((b) => b.toString(16).padStart(2, '0')).join('');
}

function saltFromHex(hex: string): Uint8Array {
  return new Uint8Array(hex.match(/.{1,2}/g)!.map((b) => parseInt(b, 16)));
}

function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes).map((b) => b.toString(16).padStart(2, '0')).join('');
}

function hexToBytes(hex: string): Uint8Array {
  if (!hex) return new Uint8Array(0);
  return new Uint8Array(hex.match(/.{1,2}/g)!.map((b) => parseInt(b, 16)));
}

async function hmacSha256(key: Uint8Array, msg: Uint8Array): Promise<Uint8Array> {
  const blockSize = 64;
  let keyHash: Uint8Array;
  if (key.length > blockSize) {
    const h = await Crypto.digestStringAsync(
      Crypto.CryptoDigestAlgorithm.SHA256,
      bytesToHex(key)
    );
    keyHash = hexToBytes(h);
  } else {
    keyHash = key;
  }
  const padded = new Uint8Array(blockSize);
  padded.set(keyHash);

  const ipad = new Uint8Array(blockSize);
  const opad = new Uint8Array(blockSize);
  for (let i = 0; i < blockSize; i++) {
    ipad[i] = padded[i] ^ 0x36;
    opad[i] = padded[i] ^ 0x5c;
  }

  const inner = new Uint8Array(blockSize + msg.length);
  inner.set(ipad);
  inner.set(msg, blockSize);
  const innerHash = hexToBytes(
    await Crypto.digestStringAsync(Crypto.CryptoDigestAlgorithm.SHA256, bytesToHex(inner))
  );

  const outer = new Uint8Array(blockSize + innerHash.length);
  outer.set(opad);
  outer.set(innerHash, blockSize);
  return hexToBytes(
    await Crypto.digestStringAsync(Crypto.CryptoDigestAlgorithm.SHA256, bytesToHex(outer))
  );
}

async function pbkdf2(
  password: string,
  salt: Uint8Array,
  iterations: number,
  dkLen: number
): Promise<Uint8Array> {
  const pw = new TextEncoder().encode(password);
  const hashLen = 32;
  const blocks = Math.ceil(dkLen / hashLen);
  const dk = new Uint8Array(blocks * hashLen);

  for (let b = 1; b <= blocks; b++) {
    const blockIn = new Uint8Array(salt.length + 4);
    blockIn.set(salt);
    blockIn[salt.length] = (b >> 24) & 0xff;
    blockIn[salt.length + 1] = (b >> 16) & 0xff;
    blockIn[salt.length + 2] = (b >> 8) & 0xff;
    blockIn[salt.length + 3] = b & 0xff;

    let u = await hmacSha256(pw, blockIn);
    const result = new Uint8Array(u);
    for (let i = 2; i <= iterations; i++) {
      u = await hmacSha256(pw, u);
      for (let j = 0; j < u.length; j++) result[j] ^= u[j];
    }
    dk.set(result, (b - 1) * hashLen);
  }
  return dk.slice(0, dkLen);
}

async function deriveKey(password: string, params: KDFParams): Promise<Uint8Array> {
  const salt = saltFromHex(params.salt);
  const defaultIter = isTestEnv() ? 1000 : 600000;
  return pbkdf2(password, salt, params.iterations ?? defaultIter, params.dkLen);
}

// ── AES-GCM ────────────────────────────────────────────────────────────────

function hasWebCrypto(): boolean {
  return typeof crypto !== 'undefined' && crypto.subtle !== undefined;
}

async function aesGcmEncrypt(
  plaintext: Uint8Array,
  key: Uint8Array,
  iv: Uint8Array
): Promise<{ ciphertext: Uint8Array; authTag: Uint8Array }> {
  if (!hasWebCrypto()) throw new Error('AES-GCM requires Web Crypto API');
  const ck = await crypto.subtle.importKey('raw', key, { name: 'AES-GCM' }, false, ['encrypt']);
  const result = await crypto.subtle.encrypt({ name: 'AES-GCM', iv, tagLength: 128 }, ck, plaintext);
  const bytes = new Uint8Array(result);
  return {
    ciphertext: bytes.slice(0, bytes.length - GCM_TAG_SIZE),
    authTag: bytes.slice(bytes.length - GCM_TAG_SIZE),
  };
}

async function aesGcmDecrypt(
  ciphertext: Uint8Array,
  key: Uint8Array,
  iv: Uint8Array,
  authTag: Uint8Array
): Promise<Uint8Array> {
  if (!hasWebCrypto()) throw new Error('AES-GCM requires Web Crypto API');
  const ck = await crypto.subtle.importKey('raw', key, { name: 'AES-GCM' }, false, ['decrypt']);
  const combined = new Uint8Array(ciphertext.length + authTag.length);
  combined.set(ciphertext);
  combined.set(authTag, ciphertext.length);
  try {
    const result = await crypto.subtle.decrypt({ name: 'AES-GCM', iv, tagLength: 128 }, ck, combined);
    return new Uint8Array(result);
  } catch {
    throw new Error('Decryption failed: invalid password or corrupted data');
  }
}

async function encryptWithPassword(
  plaintext: string,
  password: string,
  kdfType: KDFType = 'pbkdf2'
): Promise<EncryptedData> {
  const iv = Crypto.getRandomValues(new Uint8Array(GCM_IV_SIZE));
  const salt = generateSalt(32);
  const iterations = isTestEnv() ? 1000 : 600000;
  const kdfParams: KDFParams = {
    type: kdfType,
    salt: saltToHex(salt),
    dkLen: AES_KEY_SIZE,
    iterations,
  };
  const key = await deriveKey(password, kdfParams);
  const ptBytes = new TextEncoder().encode(plaintext);
  const { ciphertext, authTag } = await aesGcmEncrypt(ptBytes, key, iv);

  return {
    ciphertext: bytesToHex(ciphertext),
    iv: bytesToHex(iv),
    authTag: bytesToHex(authTag),
    kdfParams,
  };
}

async function decryptWithPassword(
  encrypted: EncryptedData,
  password: string
): Promise<string> {
  const key = await deriveKey(password, encrypted.kdfParams);
  const ct = hexToBytes(encrypted.ciphertext);
  const iv = hexToBytes(encrypted.iv);
  const tag = hexToBytes(encrypted.authTag);
  const pt = await aesGcmDecrypt(ct, key, iv, tag);
  return new TextDecoder().decode(pt);
}

// ── Wallet Storage Manager ──────────────────────────────────────────────────

export class WalletStorage {
  /** Save wallet with AES-256-GCM encryption. Returns RTC address. */
  static async save(
    name: string,
    keyPair: KeyPair,
    password: string,
    kdfType: KDFType = 'pbkdf2',
    mnemonic?: string
  ): Promise<string> {
    if (password.length < 8) throw new Error('Password must be at least 8 characters');

    const address = await publicKeyToRtcAddress(keyPair.publicKey);
    const pubHex = publicKeyToHex(keyPair.publicKey);

    const walletData = JSON.stringify({
      secretKey: secretKeyToHex(keyPair.secretKey),
      address,
    });
    const encrypted = await encryptWithPassword(walletData, password, kdfType);

    const stored: StoredWallet = {
      metadata: {
        name,
        address,
        publicKeyHex: pubHex,
        createdAt: Date.now(),
        network: 'mainnet',
        kdfType,
        hasMnemonic: !!mnemonic,
      },
      encrypted,
      version: STORAGE_VERSION,
    };

    await SecureStore.setItemAsync(`${WALLET_PREFIX}${name}`, JSON.stringify(stored));

    // If mnemonic provided, encrypt and store separately
    if (mnemonic) {
      const encMnemonic = await encryptWithPassword(mnemonic, password, kdfType);
      await SecureStore.setItemAsync(`${MNEMONIC_PREFIX}${name}`, JSON.stringify(encMnemonic));
    }

    await this.addToList(name);
    return address;
  }

  /** Load and decrypt wallet. */
  static async load(name: string, password: string): Promise<KeyPair> {
    const json = await SecureStore.getItemAsync(`${WALLET_PREFIX}${name}`);
    if (!json) throw new Error(`Wallet "${name}" not found`);

    let stored: StoredWallet;
    try {
      stored = JSON.parse(json);
    } catch {
      throw new Error('Invalid wallet data');
    }

    let decrypted: string;
    try {
      decrypted = await decryptWithPassword(stored.encrypted, password);
    } catch {
      throw new Error('Invalid password or corrupted wallet');
    }

    let data: { secretKey: string; address: string };
    try {
      data = JSON.parse(decrypted);
    } catch {
      throw new Error('Corrupted wallet data');
    }

    return keyPairFromHex(data.secretKey);
  }

  /** Load encrypted mnemonic (if stored). */
  static async loadMnemonic(name: string, password: string): Promise<string | null> {
    const json = await SecureStore.getItemAsync(`${MNEMONIC_PREFIX}${name}`);
    if (!json) return null;
    try {
      const enc: EncryptedData = JSON.parse(json);
      return await decryptWithPassword(enc, password);
    } catch {
      throw new Error('Invalid password or corrupted mnemonic');
    }
  }

  static async delete(name: string): Promise<void> {
    await SecureStore.deleteItemAsync(`${WALLET_PREFIX}${name}`);
    await SecureStore.deleteItemAsync(`${MNEMONIC_PREFIX}${name}`);
    await this.removeFromList(name);
  }

  static async list(): Promise<string[]> {
    const json = await SecureStore.getItemAsync(WALLET_LIST_KEY);
    if (!json) return [];
    return JSON.parse(json);
  }

  static async exists(name: string): Promise<boolean> {
    const val = await SecureStore.getItemAsync(`${WALLET_PREFIX}${name}`);
    return val !== null;
  }

  static async getMetadata(name: string): Promise<WalletMetadata | null> {
    const json = await SecureStore.getItemAsync(`${WALLET_PREFIX}${name}`);
    if (!json) return null;
    try {
      const stored: StoredWallet = JSON.parse(json);
      // Normalize address if needed
      if (!isValidAddress(stored.metadata.address) && stored.metadata.publicKeyHex) {
        stored.metadata.address = await publicKeyHexToRtcAddress(stored.metadata.publicKeyHex);
        await SecureStore.setItemAsync(`${WALLET_PREFIX}${name}`, JSON.stringify(stored));
      }
      return stored.metadata;
    } catch {
      return null;
    }
  }

  /** Export wallet backup (requires password verification). */
  static async export(name: string, password: string): Promise<string> {
    await this.load(name, password); // verify password
    const json = await SecureStore.getItemAsync(`${WALLET_PREFIX}${name}`);
    if (!json) throw new Error(`Wallet "${name}" not found`);
    return json;
  }

  /** Import wallet from backup JSON. */
  static async import(backupJson: string): Promise<string> {
    let stored: StoredWallet;
    try {
      stored = JSON.parse(backupJson);
    } catch {
      throw new Error('Invalid backup format');
    }
    if (!stored.metadata || !stored.encrypted || !stored.version) {
      throw new Error('Invalid backup structure');
    }
    const key = `${WALLET_PREFIX}${stored.metadata.name}`;
    if (await SecureStore.getItemAsync(key)) {
      throw new Error(`Wallet "${stored.metadata.name}" already exists`);
    }
    await SecureStore.setItemAsync(key, backupJson);
    await this.addToList(stored.metadata.name);
    return stored.metadata.name;
  }

  /** Change password for a wallet. */
  static async changePassword(
    name: string,
    oldPassword: string,
    newPassword: string
  ): Promise<void> {
    if (newPassword.length < 8) throw new Error('New password must be at least 8 characters');
    const keyPair = await this.load(name, oldPassword);
    const metadata = await this.getMetadata(name);
    if (!metadata) throw new Error('Wallet not found');

    // Re-encrypt wallet
    const walletData = JSON.stringify({
      secretKey: secretKeyToHex(keyPair.secretKey),
      address: metadata.address,
    });
    const kdfType = metadata.kdfType ?? 'pbkdf2';
    const encrypted = await encryptWithPassword(walletData, newPassword, kdfType);
    const stored: StoredWallet = {
      metadata: { ...metadata, publicKeyHex: metadata.publicKeyHex ?? publicKeyToHex(keyPair.publicKey), kdfType },
      encrypted,
      version: STORAGE_VERSION,
    };
    await SecureStore.setItemAsync(`${WALLET_PREFIX}${name}`, JSON.stringify(stored));

    // Re-encrypt mnemonic if present
    const mnemonic = await this.loadMnemonic(name, oldPassword).catch(() => null);
    if (mnemonic) {
      const encMnemonic = await encryptWithPassword(mnemonic, newPassword, kdfType);
      await SecureStore.setItemAsync(`${MNEMONIC_PREFIX}${name}`, JSON.stringify(encMnemonic));
    }
  }

  static async verifyPassword(name: string, password: string): Promise<boolean> {
    try {
      await this.load(name, password);
      return true;
    } catch {
      return false;
    }
  }

  private static async addToList(name: string): Promise<void> {
    const list = await this.list();
    if (!list.includes(name)) {
      list.push(name);
      await SecureStore.setItemAsync(WALLET_LIST_KEY, JSON.stringify(list));
    }
  }

  private static async removeFromList(name: string): Promise<void> {
    const list = await this.list();
    await SecureStore.setItemAsync(
      WALLET_LIST_KEY,
      JSON.stringify(list.filter((n) => n !== name))
    );
  }
}

// ── Nonce Store ─────────────────────────────────────────────────────────────

export class NonceStore {
  private static KEY_PREFIX = 'nonce:';
  private static queue: Promise<void> = Promise.resolve();

  private static async withLock<T>(fn: () => Promise<T>): Promise<T> {
    const prev = this.queue;
    let release!: () => void;
    this.queue = new Promise<void>((r) => (release = r));
    await prev;
    try {
      return await fn();
    } finally {
      release();
    }
  }

  static async getNextNonce(address: string): Promise<number> {
    const json = await SecureStore.getItemAsync(`${this.KEY_PREFIX}${address}`);
    if (!json) return Date.now();
    const nonces: number[] = JSON.parse(json);
    return nonces.length ? Math.max(Date.now(), Math.max(...nonces) + 1) : Date.now();
  }

  static async reserveNextNonce(address: string, suggested = Date.now()): Promise<number> {
    return this.withLock(async () => {
      const json = await SecureStore.getItemAsync(`${this.KEY_PREFIX}${address}`);
      const nonces: number[] = json ? JSON.parse(json) : [];
      let candidate = Math.max(
        Math.trunc(suggested),
        nonces.length ? Math.max(...nonces) + 1 : 1
      );
      while (nonces.includes(candidate)) candidate++;
      nonces.push(candidate);
      if (nonces.length > 1000) nonces.shift();
      await SecureStore.setItemAsync(`${this.KEY_PREFIX}${address}`, JSON.stringify(nonces));
      return candidate;
    });
  }

  static async markUsed(address: string, nonce: number): Promise<void> {
    await this.withLock(async () => {
      const json = await SecureStore.getItemAsync(`${this.KEY_PREFIX}${address}`);
      const nonces: number[] = json ? JSON.parse(json) : [];
      if (!nonces.includes(nonce)) {
        nonces.push(nonce);
        if (nonces.length > 1000) nonces.shift();
        await SecureStore.setItemAsync(`${this.KEY_PREFIX}${address}`, JSON.stringify(nonces));
      }
    });
  }

  static async isUsed(address: string, nonce: number): Promise<boolean> {
    const json = await SecureStore.getItemAsync(`${this.KEY_PREFIX}${address}`);
    if (!json) return false;
    return (JSON.parse(json) as number[]).includes(nonce);
  }
}
