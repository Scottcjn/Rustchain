/**
 * RustChain Crypto Utilities
 * 
 * Provides Ed25519 key generation, signing, and verification
 * using tweetnacl library for React Native compatibility
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
 */
export function keyPairFromHex(hex: string): KeyPair {
  const secretKey = new Uint8Array(
    hex.match(/.{1,2}/g)!.map(byte => parseInt(byte, 16))
  );
  return keyPairFromSecretKey(secretKey);
}

/**
 * Create key pair from Base58-encoded secret key
 */
export function keyPairFromBase58(base58Str: string): KeyPair {
  const secretKey = base58.decode(base58Str);
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
