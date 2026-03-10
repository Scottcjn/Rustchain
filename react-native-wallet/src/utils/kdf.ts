/**
 * Key Derivation Functions (KDF)
 *
 * Implements PBKDF2-SHA256 and Argon2id-like key derivation
 * for secure password-based key generation
 *
 * Issue #785: Secure wallet storage hardening
 */

import * as Crypto from 'expo-crypto';

/**
 * Check if running in test environment (dynamic check)
 */
function isTestEnvironment(): boolean {
  return typeof process !== 'undefined' && process.env.JEST_WORKER_ID !== undefined;
}

/**
 * PBKDF2 configuration
 */
export interface PBKDF2Config {
  iterations: number;
  dkLen: number;
  hashAlgorithm: Crypto.CryptoDigestAlgorithm;
}

/**
 * Get default PBKDF2 configuration based on environment
 */
function getDefaultPBKDF2Config(): PBKDF2Config {
  const isTest = isTestEnvironment();
  return {
    iterations: isTest ? 1000 : 600000,
    dkLen: 32,
    hashAlgorithm: Crypto.CryptoDigestAlgorithm.SHA256,
  };
}

/**
 * Argon2-like configuration (simulated using multiple PBKDF2 rounds)
 * True Argon2 is not available in React Native, so we use a memory-hard
 * approximation with multiple PBKDF2 passes
 */
export interface Argon2Config {
  iterations: number;
  memorySize: number; // Number of parallel PBKDF2 operations
  dkLen: number;
}

/**
 * Get default Argon2-like configuration based on environment
 * Higher security for sensitive operations like wallet export
 * Reduced iterations in test environment for faster tests
 */
function getDefaultArgon2Config(): Argon2Config {
  const isTest = isTestEnvironment();
  return {
    iterations: isTest ? 1 : 3,
    memorySize: isTest ? 2 : 4,
    dkLen: 32,
  };
}

/**
 * Get iteration scale factor for Argon2 simulation based on environment
 */
function getArgon2IterationScale(): number {
  return isTestEnvironment() ? 1000 : 200000;
}

/**
 * HMAC-SHA256 implementation using Expo Crypto
 */
async function hmacSha256(key: Uint8Array, message: Uint8Array): Promise<Uint8Array> {
  // HMAC = H((K' XOR opad) || H((K' XOR ipad) || message))
  const blockSize = 64; // SHA-256 block size

  // Hash key if longer than block size
  let keyHash: Uint8Array;
  if (key.length > blockSize) {
    const hashHex = await Crypto.digestStringAsync(
      Crypto.CryptoDigestAlgorithm.SHA256,
      Array.from(key).map(b => b.toString(16).padStart(2, '0')).join('')
    );
    const keyHashMatch = hashHex?.match(/.{1,2}/g);
    if (!keyHashMatch) {
      throw new Error('Failed to compute hash');
    }
    keyHash = new Uint8Array(keyHashMatch.map(b => parseInt(b, 16)));
  } else {
    keyHash = key;
  }

  // Pad key to block size
  const paddedKey = new Uint8Array(blockSize);
  paddedKey.set(keyHash);

  // Create inner and outer padding
  const ipad = new Uint8Array(blockSize);
  const opad = new Uint8Array(blockSize);
  for (let i = 0; i < blockSize; i++) {
    ipad[i] = paddedKey[i] ^ 0x36;
    opad[i] = paddedKey[i] ^ 0x5c;
  }

  // Inner hash: H((K' XOR ipad) || message)
  const innerData = new Uint8Array(blockSize + message.length);
  innerData.set(ipad);
  innerData.set(message, blockSize);

  const innerHashHex = await Crypto.digestStringAsync(
    Crypto.CryptoDigestAlgorithm.SHA256,
    Array.from(innerData).map(b => b.toString(16).padStart(2, '0')).join('')
  );
  const innerHashMatch = innerHashHex?.match(/.{1,2}/g);
  if (!innerHashMatch) {
    throw new Error('Failed to compute inner hash');
  }
  const innerHash = new Uint8Array(innerHashMatch.map(b => parseInt(b, 16)));

  // Outer hash: H((K' XOR opad) || innerHash)
  const outerData = new Uint8Array(blockSize + innerHash.length);
  outerData.set(opad);
  outerData.set(innerHash, blockSize);
  
  const outerHashHex = await Crypto.digestStringAsync(
    Crypto.CryptoDigestAlgorithm.SHA256,
    Array.from(outerData).map(b => b.toString(16).padStart(2, '0')).join('')
  );
  
  return new Uint8Array(outerHashHex.match(/.{1,2}/g)!.map(b => parseInt(b, 16)));
}

/**
 * PBKDF2-SHA256 key derivation
 * 
 * @param password - The password to derive key from
 * @param salt - Random salt (should be at least 16 bytes)
 * @param config - PBKDF2 configuration
 * @returns Derived key as Uint8Array
 */
export async function pbkdf2(
  password: string,
  salt: Uint8Array,
  config?: PBKDF2Config
): Promise<Uint8Array> {
  const actualConfig = config ?? getDefaultPBKDF2Config();
  const passwordBytes = new TextEncoder().encode(password);
  const dkLen = actualConfig.dkLen;
  const hashLen = 32; // SHA-256 output length
  const blocksNeeded = Math.ceil(dkLen / hashLen);

  const derivedKey = new Uint8Array(blocksNeeded * hashLen);

  for (let blockNum = 1; blockNum <= blocksNeeded; blockNum++) {
    // Create initial block: salt || block_number (big-endian)
    const blockInput = new Uint8Array(salt.length + 4);
    blockInput.set(salt);
    blockInput[salt.length] = (blockNum >> 24) & 0xff;
    blockInput[salt.length + 1] = (blockNum >> 16) & 0xff;
    blockInput[salt.length + 2] = (blockNum >> 8) & 0xff;
    blockInput[salt.length + 3] = blockNum & 0xff;

    // U_1 = PRF(Password, Salt || INT_32_BE(i))
    let u = await hmacSha256(passwordBytes, blockInput);
    let result = new Uint8Array(u);

    // U_2 ... U_c
    for (let iteration = 2; iteration <= actualConfig.iterations; iteration++) {
      u = await hmacSha256(passwordBytes, u);
      // XOR with previous result
      for (let j = 0; j < u.length; j++) {
        result[j] ^= u[j];
      }
    }
    
    derivedKey.set(result, (blockNum - 1) * hashLen);
  }
  
  return derivedKey.slice(0, dkLen);
}

/**
 * Argon2id-like key derivation (memory-hard approximation)
 * 
 * This is a simulation of Argon2id using multiple PBKDF2 operations
 * in parallel to approximate memory-hardness. For production use with
 * native modules, consider using a true Argon2 implementation.
 * 
 * @param password - The password to derive key from
 * @param salt - Random salt (should be at least 16 bytes)
 * @param config - Argon2 configuration
 * @returns Derived key as Uint8Array
 */
export async function argon2id(
  password: string,
  salt: Uint8Array,
  config?: Argon2Config
): Promise<Uint8Array> {
  const actualConfig = config ?? getDefaultArgon2Config();
  const iterationScale = getArgon2IterationScale();
  
  // Generate multiple "lanes" of PBKDF2 derivations
  const lanePromises: Promise<Uint8Array>[] = [];

  for (let lane = 0; lane < actualConfig.memorySize; lane++) {
    // Create unique salt for each lane by XORing with lane number
    const laneSalt = new Uint8Array(salt);
    for (let i = 0; i < Math.min(4, laneSalt.length); i++) {
      laneSalt[i] ^= (lane >> (i * 8)) & 0xff;
    }

    lanePromises.push(pbkdf2(password, laneSalt, {
      iterations: actualConfig.iterations * iterationScale, // Scale iterations
      dkLen: actualConfig.dkLen,
      hashAlgorithm: Crypto.CryptoDigestAlgorithm.SHA256,
    }));
  }

  // Wait for all lanes to complete
  const laneResults = await Promise.all(lanePromises);

  // XOR all lanes together for final key
  const finalKey = new Uint8Array(actualConfig.dkLen);
  for (const laneResult of laneResults) {
    for (let i = 0; i < actualConfig.dkLen; i++) {
      finalKey[i] ^= laneResult[i];
    }
  }
  
  return finalKey;
}

/**
 * Generate a cryptographically secure random salt
 * 
 * @param length - Salt length in bytes (default: 32)
 * @returns Random salt as Uint8Array
 */
export function generateSalt(length: number = 32): Uint8Array {
  return Crypto.getRandomValues(new Uint8Array(length));
}

/**
 * Convert salt to hex string for storage
 */
export function saltToHex(salt: Uint8Array): string {
  return Array.from(salt).map(b => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Convert hex string back to salt
 */
export function saltFromHex(hex: string): Uint8Array {
  return new Uint8Array(hex.match(/.{1,2}/g)!.map(b => parseInt(b, 16)));
}

/**
 * Key derivation type for storage
 */
export type KDFType = 'pbkdf2' | 'argon2id';

/**
 * KDF parameters stored alongside encrypted data
 */
export interface KDFParams {
  type: KDFType;
  salt: string; // hex-encoded
  iterations?: number;
  memorySize?: number;
  dkLen: number;
}

/**
 * Derive a key using the specified KDF type
 */
export async function deriveKey(
  password: string,
  params: KDFParams
): Promise<Uint8Array> {
  const salt = saltFromHex(params.salt);

  switch (params.type) {
    case 'pbkdf2': {
      const defaultConfig = getDefaultPBKDF2Config();
      return pbkdf2(password, salt, {
        iterations: params.iterations ?? defaultConfig.iterations,
        dkLen: params.dkLen,
        hashAlgorithm: Crypto.CryptoDigestAlgorithm.SHA256,
      });
    }
    case 'argon2id': {
      const defaultConfig = getDefaultArgon2Config();
      return argon2id(password, salt, {
        iterations: params.iterations ?? defaultConfig.iterations,
        memorySize: params.memorySize ?? defaultConfig.memorySize,
        dkLen: params.dkLen,
      });
    }
    default:
      throw new Error(`Unknown KDF type: ${(params as any).type}`);
  }
}

/**
 * Create KDF parameters for PBKDF2
 */
export function createPBKDF2Params(
  salt?: Uint8Array,
  iterations?: number,
  dkLen: number = 32
): KDFParams {
  const defaultConfig = getDefaultPBKDF2Config();
  return {
    type: 'pbkdf2',
    salt: saltToHex(salt ?? generateSalt(32)),
    iterations: iterations ?? defaultConfig.iterations,
    dkLen,
  };
}

/**
 * Create KDF parameters for Argon2id
 */
export function createArgon2idParams(
  salt?: Uint8Array,
  iterations?: number,
  memorySize?: number,
  dkLen: number = 32
): KDFParams {
  const defaultConfig = getDefaultArgon2Config();
  return {
    type: 'argon2id',
    salt: saltToHex(salt ?? generateSalt(32)),
    iterations: iterations ?? defaultConfig.iterations,
    memorySize: memorySize ?? defaultConfig.memorySize,
    dkLen,
  };
}
