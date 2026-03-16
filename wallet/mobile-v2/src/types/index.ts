/**
 * RustChain Wallet — Shared TypeScript Types
 */

// ── Key Management ──────────────────────────────────────────────────────────

export interface KeyPair {
  publicKey: Uint8Array;
  secretKey: Uint8Array;
}

export interface WalletAccount {
  name: string;
  address: string;
  publicKeyHex: string;
  createdAt: number;
  network: NetworkId;
  hasMnemonic: boolean;
}

// ── Network ─────────────────────────────────────────────────────────────────

export type NetworkId = 'mainnet' | 'testnet' | 'devnet';

export interface NetworkConfig {
  rpcUrl: string;
  explorerUrl: string;
  chainId?: string;
}

export interface NetworkInfo {
  chain_id: string;
  network: string;
  block_height: number;
  peer_count: number;
  min_fee: number;
  version: string;
}

// ── Balance ─────────────────────────────────────────────────────────────────

export interface BalanceResponse {
  miner: string;
  amount_i64: number;
  amount_rtc: number;
  balance: number;
  unlocked: number;
  locked: number;
  nonce?: number;
}

// ── Transactions ────────────────────────────────────────────────────────────

export interface Transaction {
  from: string;
  to: string;
  amount: number;
  nonce: number;
  memo?: string;
  signature?: string;
  chain_id?: string;
  public_key?: string;
}

export interface TransactionOptions {
  from: string;
  to: string;
  amount: number;
  nonce: number;
  memo?: string;
}

export interface TransactionResponse {
  tx_hash: string;
  status: string;
  verified?: boolean;
  confirms_at?: number;
  message?: string;
}

export interface TransferHistoryItem {
  id: number;
  tx_id: string;
  tx_hash: string;
  from_addr: string;
  to_addr: string;
  amount: number;
  amount_i64: number;
  amount_rtc: number;
  timestamp: number;
  created_at: number;
  confirmed_at?: number | null;
  confirms_at?: number | null;
  status: 'pending' | 'confirmed' | 'failed';
  raw_status?: string;
  status_reason?: string | null;
  confirmations?: number;
  direction: 'sent' | 'received';
  counterparty: string;
  reason?: string;
  memo?: string | null;
}

// ── Dry-run ─────────────────────────────────────────────────────────────────

export interface DryRunResult {
  valid: boolean;
  errors: string[];
  estimatedFee: number;
  totalCost: number;
  senderBalance?: number;
  sufficientBalance: boolean;
}

// ── Storage ─────────────────────────────────────────────────────────────────

export type KDFType = 'pbkdf2' | 'argon2id';

export interface KDFParams {
  type: KDFType;
  salt: string;
  iterations?: number;
  memorySize?: number;
  dkLen: number;
}

export interface EncryptedData {
  ciphertext: string;
  iv: string;
  authTag: string;
  kdfParams: KDFParams;
}

export interface WalletMetadata {
  name: string;
  address: string;
  publicKeyHex?: string;
  createdAt: number;
  network?: string;
  kdfType?: KDFType;
  hasMnemonic?: boolean;
}

export interface StoredWallet {
  metadata: WalletMetadata;
  encrypted: EncryptedData;
  version: number;
}

// ── QR ──────────────────────────────────────────────────────────────────────

export type QRPayloadType = 'address' | 'payment_request' | 'unknown';

export interface QRPayload {
  type: QRPayloadType;
  data: string;
  raw: string;
  validated: boolean;
  warnings: string[];
}

export interface PaymentRequest {
  address: string;
  amount?: number;
  memo?: string;
  chain_id?: string;
}

// ── Biometric ───────────────────────────────────────────────────────────────

export type BiometricType =
  | 'FACE_ID'
  | 'TOUCH_ID'
  | 'IRIS'
  | 'FINGERPRINT'
  | 'FACE'
  | 'NONE';

export interface BiometricResult {
  success: boolean;
  error?: string;
  biometricType?: BiometricType;
  available: boolean;
}

// ── Signing ─────────────────────────────────────────────────────────────────

export interface SigningPayload {
  from: string;
  to: string;
  amount: number;
  nonce: number;
  memo?: string;
  chain_id?: string;
}

export interface NumericValidationResult {
  valid: boolean;
  error?: string;
  value?: number;
}

export interface MicrounitValidationResult extends NumericValidationResult {
  units?: number;
}

// ── Constants ───────────────────────────────────────────────────────────────

export const MICRO_RTC_PER_RTC = 1_000_000;
export const RTC_DECIMALS = 6;
