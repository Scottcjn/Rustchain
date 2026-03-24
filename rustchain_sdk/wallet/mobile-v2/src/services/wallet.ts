/**
 * Wallet Crypto Service
 *
 * BIP39 mnemonic generation/import, Ed25519 key derivation,
 * transaction signing, and address utilities.
 */

import * as Crypto from 'expo-crypto';
import nacl from 'tweetnacl';
import naclUtil from 'tweetnacl-util';
import base58 from 'bs58';
import * as bip39 from 'bip39';
import type {
  KeyPair,
  SigningPayload,
  NumericValidationResult,
  MicrounitValidationResult,
} from '../types';
import { MICRO_RTC_PER_RTC, RTC_DECIMALS } from '../types';

// ── Key Generation ──────────────────────────────────────────────────────────

/** Generate a BIP39 mnemonic phrase (128-bit entropy = 12 words). */
export function generateMnemonic(): string {
  return bip39.generateMnemonic();
}

/** Validate a BIP39 mnemonic phrase. */
export function validateMnemonic(mnemonic: string): boolean {
  return bip39.validateMnemonic(mnemonic.trim().toLowerCase());
}

/** Generate a new random Ed25519 key pair. */
export function generateKeyPair(): KeyPair {
  const pair = nacl.sign.keyPair();
  return { publicKey: pair.publicKey, secretKey: pair.secretKey };
}

/** Derive an Ed25519 key pair from a BIP39 mnemonic. */
export async function keyPairFromMnemonic(
  mnemonic: string,
  derivationPath: string = "m/44'/0'/0'/0'/0'"
): Promise<KeyPair> {
  const normalized = mnemonic.trim().toLowerCase();
  if (!bip39.validateMnemonic(normalized)) {
    throw new Error('Invalid BIP39 mnemonic');
  }
  // Derive seed: SHA-256(mnemonic + path) -> 32-byte Ed25519 seed
  const data = new TextEncoder().encode(`${normalized}:${derivationPath}`);
  const hash = await sha256Bytes(data);
  const seed = hash.slice(0, 32);
  return keyPairFromSeed(seed);
}

/** Create key pair from a 32-byte Ed25519 seed. */
export function keyPairFromSeed(seed: Uint8Array): KeyPair {
  if (seed.length !== 32) throw new Error('Seed must be 32 bytes');
  const pair = nacl.sign.keyPair.fromSeed(seed);
  return { publicKey: pair.publicKey, secretKey: pair.secretKey };
}

/** Create key pair from a 64-byte secret key. */
export function keyPairFromSecretKey(secretKey: Uint8Array): KeyPair {
  if (secretKey.length !== 64) throw new Error('Secret key must be 64 bytes');
  const pair = nacl.sign.keyPair.fromSecretKey(secretKey);
  return { publicKey: pair.publicKey, secretKey: pair.secretKey };
}

/** Create key pair from hex-encoded seed (64 chars) or secret key (128 chars). */
export function keyPairFromHex(hex: string): KeyPair {
  const clean = hex.trim().replace(/^0x/, '');
  if (!/^[0-9a-fA-F]+$/.test(clean)) {
    throw new Error('Invalid hex format');
  }
  if (clean.length !== 64 && clean.length !== 128) {
    throw new Error('Expected 64 or 128 hex characters');
  }
  const bytes = hexToBytes(clean);
  return bytes.length === 32 ? keyPairFromSeed(bytes) : keyPairFromSecretKey(bytes);
}

/** Create key pair from Base58-encoded key. */
export function keyPairFromBase58(b58: string): KeyPair {
  if (!/^[1-9A-HJ-NP-Za-km-z]+$/.test(b58)) {
    throw new Error('Invalid Base58 format');
  }
  const bytes = base58.decode(b58);
  if (bytes.length !== 32 && bytes.length !== 64) {
    throw new Error('Invalid key length');
  }
  return bytes.length === 32 ? keyPairFromSeed(bytes) : keyPairFromSecretKey(bytes);
}

// ── Address Utilities ───────────────────────────────────────────────────────

/** Derive RTC address from public key: "RTC" + sha256(pubkey)[:40]. */
export async function publicKeyToRtcAddress(publicKey: Uint8Array): Promise<string> {
  const digest = await sha256Bytes(publicKey);
  const hex = bytesToHex(digest);
  return `RTC${hex.slice(0, 40)}`;
}

/** Derive RTC address from hex-encoded public key. */
export async function publicKeyHexToRtcAddress(pubHex: string): Promise<string> {
  const clean = pubHex.trim().replace(/^0x/, '');
  if (!/^[0-9a-fA-F]{64}$/.test(clean)) {
    throw new Error('Public key must be 64 hex chars');
  }
  return publicKeyToRtcAddress(hexToBytes(clean));
}

/** Validate RTC address format. */
export function isValidAddress(address: string): boolean {
  return typeof address === 'string' && /^RTC[0-9a-fA-F]{40}$/.test(address.trim());
}

/** Validate chain_id format. */
export function isValidChainId(chainId: string): boolean {
  return /^[A-Za-z0-9._-]{1,64}$/.test(chainId);
}

// ── Encoding Helpers ────────────────────────────────────────────────────────

export function publicKeyToHex(pk: Uint8Array): string {
  return bytesToHex(pk);
}

export function secretKeyToHex(sk: Uint8Array): string {
  return bytesToHex(sk);
}

export function publicKeyToBase58(pk: Uint8Array): string {
  return base58.encode(pk);
}

export function secretKeyToBase58(sk: Uint8Array): string {
  return base58.encode(sk);
}

// ── Signing ─────────────────────────────────────────────────────────────────

/** Sign raw bytes, return the 64-byte Ed25519 signature. */
export function signMessage(message: Uint8Array, secretKey: Uint8Array): Uint8Array {
  const signed = nacl.sign(message, secretKey);
  return signed.slice(0, 64);
}

/** Verify a detached Ed25519 signature. */
export function verifySignature(
  message: Uint8Array,
  signature: Uint8Array,
  publicKey: Uint8Array
): boolean {
  return nacl.sign.detached.verify(message, signature, publicKey);
}

/** Sign a UTF-8 string, return hex-encoded signature. */
export function signString(message: string, secretKey: Uint8Array): string {
  const msgBytes = naclUtil.decodeUTF8(message);
  const sig = signMessage(msgBytes, secretKey);
  return bytesToHex(sig);
}

/** Verify a hex-encoded signature against a string message. */
export function verifySignatureHex(
  message: string,
  signatureHex: string,
  publicKey: Uint8Array
): boolean {
  const msgBytes = naclUtil.decodeUTF8(message);
  const sig = hexToBytes(signatureHex);
  return verifySignature(msgBytes, sig, publicKey);
}

/**
 * Create a canonical signing payload with optional chain_id.
 * Keys are sorted alphabetically, undefined values omitted.
 */
function canonicalize(payload: SigningPayload): string {
  const obj: Record<string, string | number> = {};
  for (const key of Object.keys(payload).sort()) {
    const val = payload[key as keyof SigningPayload];
    if (val !== undefined) {
      obj[key] = val;
    }
  }
  return JSON.stringify(obj);
}

/** Sign a transaction payload (with chain_id binding). Returns hex signature. */
export function signTransactionPayload(
  tx: Omit<SigningPayload, 'chain_id'>,
  chainId: string | undefined,
  secretKey: Uint8Array
): string {
  const payload: SigningPayload = { ...tx };
  if (chainId) payload.chain_id = chainId;
  return signString(canonicalize(payload), secretKey);
}

/** Verify a transaction signature. */
export function verifyTransactionPayload(
  tx: Omit<SigningPayload, 'chain_id'>,
  chainId: string | undefined,
  signature: string,
  publicKey: Uint8Array
): boolean {
  const payload: SigningPayload = { ...tx };
  if (chainId) payload.chain_id = chainId;
  return verifySignatureHex(canonicalize(payload), signature, publicKey);
}

// ── Numeric Validation ──────────────────────────────────────────────────────

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
  const { min, max, allowZero = true, allowNegative = false, maxDecimals } = options;

  if (!value || typeof value !== 'string') {
    return { valid: false, error: 'Value is required' };
  }
  const trimmed = value.trim();
  if (!trimmed) return { valid: false, error: 'Value cannot be empty' };

  const re = allowNegative
    ? /^-?(0|[1-9]\d*)(\.\d+)?$/
    : /^(0|[1-9]\d*)(\.\d+)?$/;
  if (!re.test(trimmed)) return { valid: false, error: 'Invalid number format' };

  const num = Number(trimmed);
  if (!Number.isFinite(num)) return { valid: false, error: 'Number must be finite' };
  if (num === 0 && !allowZero) return { valid: false, error: 'Value cannot be zero' };
  if (num < 0 && !allowNegative) return { valid: false, error: 'Value cannot be negative' };
  if (min !== undefined && num < min) return { valid: false, error: `Must be at least ${min}` };
  if (max !== undefined && num > max) return { valid: false, error: `Must be at most ${max}` };

  if (maxDecimals !== undefined) {
    const dec = trimmed.split('.')[1];
    if (dec && dec.length > maxDecimals) {
      return { valid: false, error: `Max ${maxDecimals} decimal places` };
    }
  }

  return { valid: true, value: num };
}

export function validateTransactionAmount(amount: string): NumericValidationResult {
  return validateNumericString(amount, {
    min: 0,
    allowZero: false,
    allowNegative: false,
    maxDecimals: RTC_DECIMALS,
  });
}

export function validateTransactionFee(fee: string): NumericValidationResult {
  return validateNumericString(fee, {
    min: 0,
    allowZero: true,
    allowNegative: false,
    maxDecimals: RTC_DECIMALS,
  });
}

/** Parse an RTC amount string to micro-RTC integer units. */
export function parseRtcAmountToMicrounits(
  value: string,
  options: { allowZero?: boolean } = {}
): MicrounitValidationResult {
  const v = validateNumericString(value, {
    min: 0,
    allowZero: options.allowZero ?? false,
    allowNegative: false,
    maxDecimals: RTC_DECIMALS,
  });
  if (!v.valid) return v;

  const trimmed = value.trim();
  const [whole, frac = ''] = trimmed.split('.');
  const padded = (frac + '000000').slice(0, RTC_DECIMALS);
  const units = Number(whole) * MICRO_RTC_PER_RTC + Number(padded || '0');

  if (!Number.isSafeInteger(units)) {
    return { valid: false, error: 'Amount exceeds safe integer range' };
  }

  return { ...v, units };
}

// ── Internal Helpers ────────────────────────────────────────────────────────

async function sha256Bytes(data: Uint8Array): Promise<Uint8Array> {
  if (typeof (Crypto as any).digest === 'function') {
    const digest = await (Crypto as any).digest(
      Crypto.CryptoDigestAlgorithm.SHA256,
      data
    );
    return new Uint8Array(digest);
  }
  if (typeof crypto !== 'undefined' && crypto.subtle) {
    const digest = await crypto.subtle.digest('SHA-256', data);
    return new Uint8Array(digest);
  }
  throw new Error('No SHA-256 implementation available');
}

function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

function hexToBytes(hex: string): Uint8Array {
  if (!hex || hex.length === 0) return new Uint8Array(0);
  return new Uint8Array(hex.match(/.{1,2}/g)!.map((b) => parseInt(b, 16)));
}

/** Constant-time string comparison. */
export function constantTimeCompare(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let result = 0;
  for (let i = 0; i < a.length; i++) {
    result |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return result === 0;
}
