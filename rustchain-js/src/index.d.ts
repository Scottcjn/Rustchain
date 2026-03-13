/**
 * RustChain JavaScript SDK - TypeScript Type Definitions
 * =======================================================
 * 
 * Type definitions for the RustChain blockchain client.
 * Provides type safety for JavaScript/TypeScript projects.
 * 
 * @packageDocumentation
 */

/**
 * Client configuration options
 */
export interface RustChainClientOptions {
  /** RustChain node URL (default: 'https://50.28.86.131') */
  nodeUrl?: string;
  /** Admin key for privileged operations */
  adminKey?: string | null;
  /** Request timeout in milliseconds (default: 10000) */
  timeout?: number;
}

/**
 * Health check response
 */
export interface HealthResponse {
  /** Node is healthy and operational */
  ok: boolean;
  /** Node version string */
  version: string;
  /** Uptime in seconds */
  uptime_s: number;
  /** Database read/write status */
  db_rw: boolean;
  /** Backup age in hours */
  backup_age_hours?: number;
  /** Current slot number */
  slot?: number;
}

/**
 * Miner information
 */
export interface MinerInfo {
  /** Miner wallet address */
  miner: string;
  /** Hardware antiquity multiplier */
  antiquity_multiplier: number;
  /** Device architecture (e.g., 'G4', 'X86') */
  device_arch: string;
  /** Device family */
  device_family: string;
  /** Hardware type description */
  hardware_type: string;
  /** Last attestation timestamp */
  last_attest?: number;
  /** Enrolled status */
  enrolled?: boolean;
}

/**
 * Wallet balance information
 */
export interface BalanceResponse {
  /** Wallet address or ID */
  miner_id: string;
  /** Current balance in RTC */
  balance_rtc: number;
  /** Wallet exists flag */
  exists: boolean;
  /** Total RTC earned */
  total_earned?: number;
  /** Epoch rewards */
  epoch_rewards?: number;
}

/**
 * Epoch information
 */
export interface EpochResponse {
  /** Current epoch number */
  epoch: number;
  /** Current slot within epoch */
  slot: number;
  /** Total blocks per epoch */
  blocks_per_epoch: number;
  /** Current epoch PoT (Proof of Time) */
  epoch_pot: number;
  /** Number of enrolled miners */
  enrolled_miners: number;
  /** Total RTC supply */
  total_supply_rtc: number;
}

/**
 * Lottery eligibility response
 */
export interface EligibilityResponse {
  /** Miner is eligible for lottery */
  eligible: boolean;
  /** Slot number */
  slot?: number;
  /** Slot producer address */
  slot_producer?: string;
  /** Rotation size */
  rotation_size?: number;
  /** Eligibility reason */
  reason?: string;
}

/**
 * Attestation payload
 */
export interface AttestationPayload {
  /** Miner wallet ID */
  miner_id: string;
  /** Device information */
  device: {
    arch: string;
    cores: number;
    fingerprint?: string;
  };
  /** Fingerprint check results */
  fingerprint: {
    checks: Record<string, boolean>;
    score?: number;
  };
  /** Unique nonce for replay protection */
  nonce: string;
  /** Optional signature */
  signature?: string;
}

/**
 * Attestation submission response
 */
export interface AttestationResponse {
  /** Submission successful */
  success: boolean;
  /** Transaction hash */
  tx_hash?: string;
  /** Epoch number */
  epoch?: number;
  /** Slot number */
  slot?: number;
  /** Applied multiplier */
  multiplier?: number;
  /** Error message if failed */
  error?: string;
}

/**
 * Transfer request parameters
 */
export interface TransferRequest {
  /** Source wallet ID */
  from: string;
  /** Destination wallet ID */
  to: string;
  /** Amount in RTC */
  amount: number;
  /** Transaction fee in RTC */
  fee?: number;
  /** Transaction signature */
  signature?: string;
  /** Private key for signing */
  private_key?: string;
}

/**
 * Transfer response
 */
export interface TransferResponse {
  /** Transfer successful */
  success: boolean;
  /** Pending transaction ID */
  pending_id?: string;
  /** Transaction hash */
  tx_hash?: string;
  /** Fee deducted */
  fee?: number;
  /** New balance after transfer */
  new_balance?: number;
  /** Error message if failed */
  error?: string;
}

/**
 * Wallet validation result
 */
export interface WalletValidationResult {
  /** Wallet name is valid */
  isValid: boolean;
  /** Validation message */
  message: string;
}

/**
 * Base RustChain error
 */
export class RustChainError extends Error {
  constructor(message: string, statusCode?: number | null, response?: any);
  statusCode: number | null;
  response: any | null;
  toString(): string;
}

/**
 * Wallet operation error
 */
export class WalletError extends RustChainError {
  constructor(message: string, statusCode?: number | null, response?: any);
}

/**
 * Transaction operation error
 */
export class TransactionError extends RustChainError {
  constructor(message: string, statusCode?: number | null, response?: any);
}

/**
 * Network connectivity error
 */
export class NetworkError extends RustChainError {
  constructor(message: string, statusCode?: number | null, response?: any);
}

/**
 * Authentication/authorization error
 */
export class AuthenticationError extends RustChainError {
  constructor(message: string, statusCode?: number | null, response?: any);
}

/**
 * RustChain blockchain API client
 * 
 * @example
 * ```typescript
 * const client = new RustChainClient({
 *   nodeUrl: 'https://50.28.86.131',
 *   adminKey: 'your-admin-key'
 * });
 * 
 * const balance = await client.getBalance('my-wallet');
 * console.log(`Balance: ${balance.balance_rtc} RTC`);
 * ```
 */
export class RustChainClient {
  /**
   * Create a RustChain client
   * @param options - Client configuration options
   */
  constructor(options?: RustChainClientOptions);
  
  /** Node URL */
  nodeUrl: string;
  /** Admin key */
  adminKey: string | null;
  /** Request timeout */
  timeout: number;
  
  /**
   * Check node health status
   * @returns Health check response
   * 
   * @example
   * ```typescript
   * const health = await client.healthCheck();
   * console.log(`Node version: ${health.version}`);
   * ```
   */
  healthCheck(): Promise<HealthResponse>;
  
  /**
   * Get list of active miners
   * @returns Array of miner information
   * 
   * @example
   * ```typescript
   * const miners = await client.getMiners();
   * console.log(`Total miners: ${miners.length}`);
   * ```
   */
  getMiners(): Promise<MinerInfo[]>;
  
  /**
   * Get wallet balance
   * @param minerId - Wallet ID to query
   * @returns Balance information
   * 
   * @example
   * ```typescript
   * const balance = await client.getBalance('my-wallet');
   * console.log(`Balance: ${balance.balance_rtc} RTC`);
   * ```
   */
  getBalance(minerId: string): Promise<BalanceResponse>;
  
  /**
   * Check if wallet exists
   * @param minerId - Wallet ID to check
   * @returns True if wallet exists
   */
  walletExists(minerId: string): Promise<boolean>;
  
  /**
   * Get current epoch information
   * @returns Epoch information
   * 
   * @example
   * ```typescript
   * const epoch = await client.getEpoch();
   * console.log(`Current epoch: ${epoch.epoch}`);
   * ```
   */
  getEpoch(): Promise<EpochResponse>;
  
  /**
   * Check lottery eligibility for a miner
   * @param minerId - Wallet ID to check
   * @returns Eligibility response
   * 
   * @example
   * ```typescript
   * const eligibility = await client.checkEligibility('my-wallet');
   * console.log(`Eligible: ${eligibility.eligible}`);
   * ```
   */
  checkEligibility(minerId: string): Promise<EligibilityResponse>;
  
  /**
   * Submit hardware attestation
   * @param payload - Attestation payload
   * @returns Attestation response
   * 
   * @example
   * ```typescript
   * const result = await client.submitAttestation({
   *   miner_id: 'my-wallet',
   *   device: { arch: 'G4', cores: 1 },
   *   fingerprint: { checks: {} },
   *   nonce: 'unique-nonce'
   * });
   * ```
   */
  submitAttestation(payload: AttestationPayload): Promise<AttestationResponse>;
  
  /**
   * Transfer RTC between wallets
   * @param fromWallet - Source wallet ID
   * @param toWallet - Destination wallet ID
   * @param amount - Amount in RTC
   * @param adminKey - Optional admin key override
   * @returns Transfer response
   * 
   * @example
   * ```typescript
   * const result = await client.transferRtc('wallet1', 'wallet2', 10.0);
   * console.log(`TX ID: ${result.pending_id}`);
   * ```
   */
  transferRtc(
    fromWallet: string,
    toWallet: string,
    amount: number,
    adminKey?: string
  ): Promise<TransferResponse>;
  
  /**
   * Register a new wallet
   * @param minerId - Wallet ID to register
   * @param adminKey - Optional admin key
   * @returns Registration result
   */
  registerWallet(minerId: string, adminKey?: string): Promise<{ success: boolean; miner_id: string }>;
}

/**
 * High-level wallet operations
 * 
 * @example
 * ```typescript
 * const wallet = new Wallet(client);
 * const [isValid, message] = wallet.validateName('my-wallet');
 * ```
 */
export class Wallet {
  /**
   * Create Wallet instance
   * @param client - RustChainClient instance
   */
  constructor(client: RustChainClient);
  
  /**
   * Validate wallet name
   * @param name - Proposed wallet name
   * @returns [isValid, message] tuple
   * 
   * @example
   * ```typescript
   * const [isValid, msg] = wallet.validateName('my-wallet');
   * if (isValid) {
   *   console.log('✓ Valid wallet name');
   * } else {
   *   console.log(`✗ ${msg}`);
   * }
   * ```
   */
  validateName(name: string): [boolean, string];
  
  /**
   * Check if wallet exists
   * @param minerId - Wallet ID to check
   * @returns True if exists
   */
  exists(minerId: string): Promise<boolean>;
  
  /**
   * Get wallet balance
   * @param minerId - Wallet ID
   * @returns Balance in RTC
   */
  getBalance(minerId: string): Promise<number>;
  
  /**
   * Register new wallet
   * @param minerId - Wallet ID to register
   * @param adminKey - Optional admin key
   * @returns Registration result
   */
  register(minerId: string, adminKey?: string): Promise<any>;
}

/**
 * High-level transaction operations
 * 
 * @example
 * ```typescript
 * const tx = new Transaction(client);
 * const result = await tx.send('wallet1', 'wallet2', 10.0);
 * ```
 */
export class Transaction {
  /**
   * Create Transaction instance
   * @param client - RustChainClient instance
   */
  constructor(client: RustChainClient);
  
  /**
   * Send RTC between wallets
   * @param fromWallet - Source wallet ID
   * @param toWallet - Destination wallet ID
   * @param amountRtc - Amount in RTC
   * @param adminKey - Optional admin key override
   * @returns Transfer response
   * 
   * @example
   * ```typescript
   * const result = await tx.send('wallet1', 'wallet2', 10.0);
   * console.log(`Transaction ID: ${result.pending_id}`);
   * ```
   */
  send(
    fromWallet: string,
    toWallet: string,
    amountRtc: number,
    adminKey?: string | null
  ): Promise<TransferResponse>;
  
  /**
   * Validate transaction parameters
   * @param fromWallet - Source wallet ID
   * @param toWallet - Destination wallet ID
   * @param amount - Amount in RTC
   * @returns Validation result
   */
  validate(
    fromWallet: string,
    toWallet: string,
    amount: number
  ): { valid: boolean; error?: string };
}

// Export version
export const VERSION: string;
