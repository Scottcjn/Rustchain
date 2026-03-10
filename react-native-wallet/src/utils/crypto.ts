/**
 * RustChain Crypto Utilities (Hardened)
 *
 * Provides Ed25519 key generation, signing, and verification
 * with chain_id binding and numeric validation
 *
 * Issue #785: Security hardening
 * - chain_id in signed payload to prevent replay attacks
 * - Numeric validation hardening
 * - Strict type checking
 */

import nacl from 'tweetnacl';
import naclUtil from 'tweetnacl-util';
import base58 from 'bs58';

/**
 * KeyPair interface representing Ed25519 key pair
 */
export interface KeyPair {
  publicKey: Uint8Array;
  secretKey: Uint8Array;
}

/**
 * Generate a new Ed25519 key pair
 */
export function generateKeyPair(): KeyPair {
  const pair = nacl.sign.keyPair();
  return {
    publicKey: pair.publicKey,
    secretKey: pair.secretKey,
  };
}

/**
 * Create key pair from secret key bytes
 */
export function keyPairFromSecretKey(secretKey: Uint8Array): KeyPair {
  const pair = nacl.sign.keyPair.fromSecretKey(secretKey);
  return {
    publicKey: pair.publicKey,
    secretKey: pair.secretKey,
  };
}

/**
 * Create key pair from hex-encoded secret key
 * Validates hex format strictly
 * Note: Ed25519 secret key is 64 bytes (128 hex chars) - includes seed + public key
 */
export function keyPairFromHex(hex: string): KeyPair {
  // Strict hex validation - Ed25519 secret key is 64 bytes = 128 hex chars
  const cleanHex = hex.trim().replace(/^0x/, '');
  if (!/^[0-9a-fA-F]{128}$/.test(cleanHex)) {
    throw new Error('Invalid secret key: must be 128 hex characters (64 bytes)');
  }
  
  const secretKey = new Uint8Array(
    cleanHex.match(/.{1,2}/g)!.map(byte => parseInt(byte, 16))
  );
  return keyPairFromSecretKey(secretKey);
}

/**
 * Create key pair from Base58-encoded secret key
 */
export function keyPairFromBase58(base58Str: string): KeyPair {
  // Strict Base58 validation (no 0, O, I, l)
  if (!/^[1-9A-HJ-NP-Za-km-z]+$/.test(base58Str)) {
    throw new Error('Invalid Base58 format');
  }
  
  const secretKey = base58.decode(base58Str);
  if (secretKey.length !== 64) {
    throw new Error('Invalid secret key length');
  }
  return keyPairFromSecretKey(secretKey);
}

/**
 * Get public key as hex string
 */
export function publicKeyToHex(publicKey: Uint8Array): string {
  return Array.from(publicKey)
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');
}

/**
 * Get public key as Base58 string (wallet address)
 */
export function publicKeyToBase58(publicKey: Uint8Array): string {
  return base58.encode(publicKey);
}

/**
 * Get secret key as hex string
 */
export function secretKeyToHex(secretKey: Uint8Array): string {
  return Array.from(secretKey)
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');
}

/**
 * Get secret key as Base58 string
 */
export function secretKeyToBase58(secretKey: Uint8Array): string {
  return base58.encode(secretKey);
}

/**
 * Sign a message with the secret key
 */
export function signMessage(message: Uint8Array, secretKey: Uint8Array): Uint8Array {
  const signed = nacl.sign(message, secretKey);
  // Extract signature (first 64 bytes of signed message)
  return signed.slice(0, 64);
}

/**
 * Verify a signature against a message
 */
export function verifySignature(
  message: Uint8Array,
  signature: Uint8Array,
  publicKey: Uint8Array
): boolean {
  return nacl.sign.detached.verify(message, signature, publicKey);
}

/**
 * Sign a string message and return hex-encoded signature
 */
export function signString(message: string, secretKey: Uint8Array): string {
  const messageBytes = naclUtil.decodeUTF8(message);
  const signature = signMessage(messageBytes, secretKey);
  return Array.from(signature)
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');
}

/**
 * Verify a hex-encoded signature
 */
export function verifySignatureHex(
  message: string,
  signatureHex: string,
  publicKey: Uint8Array
): boolean {
  const messageBytes = naclUtil.decodeUTF8(message);
  const signature = new Uint8Array(
    signatureHex.match(/.{1,2}/g)!.map(byte => parseInt(byte, 16))
  );
  return verifySignature(messageBytes, signature, publicKey);
}

/**
 * Transaction signing payload with chain_id binding
 * Issue #785: Include chain_id in signed payload to prevent cross-chain replay attacks
 */
export interface SigningPayload {
  from: string;
  to: string;
  amount: number;
  fee: number;
  nonce: number;
  timestamp: string;
  memo?: string;
  chain_id: string;
}

/**
 * Create a signing payload with chain_id
 * 
 * @param txData - Transaction data
 * @param chainId - Chain ID to bind signature to
 * @returns Canonical signing payload
 */
export function createSigningPayload(
  txData: Omit<SigningPayload, 'chain_id'>,
  chainId: string
): SigningPayload {
  return {
    from: txData.from,
    to: txData.to,
    amount: txData.amount,
    fee: txData.fee,
    nonce: txData.nonce,
    timestamp: txData.timestamp,
    memo: txData.memo,
    chain_id: chainId,
  };
}

/**
 * Sign a transaction payload with chain_id binding
 * 
 * @param payload - Transaction payload (without chain_id)
 * @param chainId - Chain ID
 * @param secretKey - Secret key
 * @returns Hex-encoded signature
 */
export function signTransactionPayload(
  payload: Omit<SigningPayload, 'chain_id'>,
  chainId: string,
  secretKey: Uint8Array
): string {
  const signingData = createSigningPayload(payload, chainId);
  const payloadString = JSON.stringify(signingData);
  return signString(payloadString, secretKey);
}

/**
 * Verify a transaction signature with chain_id
 * 
 * @param payload - Transaction payload (without chain_id)
 * @param chainId - Chain ID
 * @param signature - Hex-encoded signature
 * @param publicKey - Public key
 * @returns true if signature is valid
 */
export function verifyTransactionPayload(
  payload: Omit<SigningPayload, 'chain_id'>,
  chainId: string,
  signature: string,
  publicKey: Uint8Array
): boolean {
  const signingData = createSigningPayload(payload, chainId);
  const payloadString = JSON.stringify(signingData);
  return verifySignatureHex(payloadString, signature, publicKey);
}

/**
 * Numeric validation utilities
 * Issue #785: Hardened numeric validation
 */
export interface NumericValidationResult {
  valid: boolean;
  error?: string;
  value?: number;
}

/**
 * Validate and parse a numeric string
 * 
 * @param value - String value to validate
 * @param options - Validation options
 * @returns Validation result
 */
export function validateNumericString(
  value: string,
  options: {
    min?: number;
    max?: number;
    allowZero?: boolean;
    allowNegative?: boolean;
    maxDecimals?: number;
  } = {}
): NumericValidationResult {
  const {
    min,
    max,
    allowZero = true,
    allowNegative = false,
    maxDecimals,
  } = options;

  // Check for empty/null/undefined
  if (!value || typeof value !== 'string') {
    return { valid: false, error: 'Value is required' };
  }

  // Trim whitespace
  const trimmed = value.trim();
  if (!trimmed) {
    return { valid: false, error: 'Value cannot be empty' };
  }

  // Check for valid number format (no scientific notation, no leading zeros except for 0.xxx)
  const numberRegex = allowNegative
    ? /^-?(0|[1-9]\d*)(\.\d+)?$/
    : /^(0|[1-9]\d*)(\.\d+)?$/;
  
  if (!numberRegex.test(trimmed)) {
    return { valid: false, error: 'Invalid number format' };
  }

  // Parse the number
  const numValue = Number(trimmed);
  
  // Check for NaN
  if (Number.isNaN(numValue)) {
    return { valid: false, error: 'Not a valid number' };
  }

  // Check for Infinity
  if (!Number.isFinite(numValue)) {
    return { valid: false, error: 'Number must be finite' };
  }

  // Check zero
  if (numValue === 0 && !allowZero) {
    return { valid: false, error: 'Value cannot be zero' };
  }

  // Check negative
  if (numValue < 0 && !allowNegative) {
    return { valid: false, error: 'Value cannot be negative' };
  }

  // Check min
  if (min !== undefined && numValue < min) {
    return { valid: false, error: `Value must be at least ${min}` };
  }

  // Check max
  if (max !== undefined && numValue > max) {
    return { valid: false, error: `Value must be at most ${max}` };
  }

  // Check decimal places
  if (maxDecimals !== undefined) {
    const decimalPart = trimmed.split('.')[1];
    if (decimalPart && decimalPart.length > maxDecimals) {
      return { valid: false, error: `Value cannot have more than ${maxDecimals} decimal places` };
    }
  }

  return { valid: true, value: numValue };
}

/**
 * Validate amount for transaction
 * 
 * @param amount - Amount string
 * @returns Validation result
 */
export function validateTransactionAmount(amount: string): NumericValidationResult {
  return validateNumericString(amount, {
    min: 0,
    allowZero: false,
    allowNegative: false,
    maxDecimals: 8, // Standard crypto precision
  });
}

/**
 * Validate fee for transaction
 * 
 * @param fee - Fee string
 * @returns Validation result
 */
export function validateTransactionFee(fee: string): NumericValidationResult {
  return validateNumericString(fee, {
    min: 0,
    allowZero: true,
    allowNegative: false,
    maxDecimals: 8,
  });
}

/**
 * Derive a key pair from a mnemonic-like seed (simplified BIP39-style)
 * Note: For production, use a proper BIP39/BIP32 library
 */
export async function deriveKeyPairFromMnemonic(
  mnemonic: string,
  derivationPath: string = "m/44'/0'/0'/0'/0'"
): Promise<KeyPair> {
  // Simple derivation using SHA-256 hash of mnemonic + path
  const encoder = new TextEncoder();
  const data = encoder.encode(`${mnemonic}:${derivationPath}`);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = new Uint8Array(hashBuffer);

  // Use first 32 bytes as seed for key pair
  const seed = hashArray.slice(0, 32);

  // Hash again to ensure uniform distribution
  const seedHashBuffer = await crypto.subtle.digest('SHA-256', seed);
  const seedHashArray = new Uint8Array(seedHashBuffer);

  return keyPairFromSecretKey(seedHashArray);
}

/**
 * Validate wallet address format
 * 
 * @param address - Wallet address to validate
 * @returns true if valid Base58 address
 */
export function isValidAddress(address: string): boolean {
  if (!address || typeof address !== 'string') {
    return false;
  }
  
  // Check minimum length (Base58 encoded 32-byte public key is ~43-44 chars)
  if (address.length < 40) {
    return false;
  }
  
  // Check Base58 format (no 0, O, I, l)
  if (!/^[1-9A-HJ-NP-Za-km-z]+$/.test(address)) {
    return false;
  }
  
  try {
    const decoded = base58.decode(address);
    // Valid Ed25519 public key is 32 bytes
    return decoded.length === 32;
  } catch {
    return false;
  }
}

/**
 * Constant-time string comparison to prevent timing attacks
 */
export function constantTimeCompare(a: string, b: string): boolean {
  if (a.length !== b.length) {
    return false;
  }
  
  let result = 0;
  for (let i = 0; i < a.length; i++) {
    result |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  
  return result === 0;
}
