/**
 * RustChain API Client (Hardened)
 *
 * Provides methods for interacting with RustChain node API:
 * - Balance queries
 * - Transaction submission
 * - Network info
 *
 * Issue #785: Security hardening
 * - chain_id in signed payload
 * - Numeric validation
 * - Strict payload validation
 */

import { NonceStore } from '../storage/secure';
import {
  KeyPair,
  isValidAddress,
  isValidChainId,
  publicKeyToHex,
  publicKeyToRtcAddress,
  signTransactionPayload,
  validateTransactionAmount,
  validateTransactionFee,
  MICRO_RTC_PER_RTC,
} from '../utils/crypto';

/**
 * Network configuration
 * Environment variables can override default URLs via .env.local:
 * - EXPO_PUBLIC_RUSTCHAIN_NODE_URL - Custom node URL
 * - EXPO_PUBLIC_NETWORK - Default network (mainnet/testnet/devnet)
 */
export enum Network {
  Mainnet = 'mainnet',
  Testnet = 'testnet',
  Devnet = 'devnet',
}

// Default network configuration
const DEFAULT_NETWORK_CONFIG: Record<Network, { rpcUrl: string; explorerUrl: string }> = {
  [Network.Mainnet]: {
    rpcUrl: 'https://rustchain.org',
    explorerUrl: 'https://rustchain.org/explorer',
  },
  [Network.Testnet]: {
    rpcUrl: 'https://testnet-rpc.rustchain.org',
    explorerUrl: 'https://testnet-explorer.rustchain.org',
  },
  [Network.Devnet]: {
    rpcUrl: 'https://devnet-rpc.rustchain.org',
    explorerUrl: 'https://devnet-explorer.rustchain.org',
  },
};

/**
 * Get network configuration with environment variable overrides
 */
export function getNetworkConfig(network: Network = Network.Mainnet) {
  // Check for custom node URL from environment
  const customUrl = process.env.EXPO_PUBLIC_RUSTCHAIN_NODE_URL;
  
  if (customUrl && network === Network.Mainnet) {
    return {
      rpcUrl: customUrl,
      explorerUrl: DEFAULT_NETWORK_CONFIG[network].explorerUrl,
    };
  }
  
  return DEFAULT_NETWORK_CONFIG[network];
}

export const NETWORK_CONFIG: Record<Network, { rpcUrl: string; explorerUrl: string }> = {
  [Network.Mainnet]: getNetworkConfig(Network.Mainnet),
  [Network.Testnet]: getNetworkConfig(Network.Testnet),
  [Network.Devnet]: getNetworkConfig(Network.Devnet),
};

/**
 * Get the configured default network from environment
 */
export function getDefaultNetwork(): Network {
  const envNetwork = process.env.EXPO_PUBLIC_NETWORK;
  switch (envNetwork) {
    case 'testnet':
      return Network.Testnet;
    case 'devnet':
      return Network.Devnet;
    case 'mainnet':
    default:
      return Network.Mainnet;
  }
}

/**
 * Balance response from API
 */
export interface BalanceResponse {
  miner: string;
  amount_i64: number;
  amount_rtc: number;
  balance: number;
  unlocked: number;
  locked: number;
  nonce?: number;
}

/**
 * Transaction response from API
 */
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

/**
 * Network info response
 */
export interface NetworkInfo {
  chain_id: string;
  network: string;
  block_height: number;
  peer_count: number;
  min_fee: number;
  version: string;
}

/**
 * Transaction structure for RustChain
 */
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

/**
 * Transaction builder options
 */
export interface TransactionOptions {
  from: string;
  to: string;
  amount: number;
  nonce: number;
  memo?: string;
}

/**
 * Error types for API operations
 */
export class RustChainApiError extends Error {
  constructor(
    message: string,
    public statusCode?: number,
    public originalError?: Error
  ) {
    super(message);
    this.name = 'RustChainApiError';
  }
}

/**
 * RustChain API Client class
 */
export class RustChainClient {
  private baseUrl: string;
  private timeout: number;
  private chainId: string | null = null;

  constructor(network: Network = getDefaultNetwork(), timeout: number = 30000) {
    this.baseUrl = getNetworkConfig(network).rpcUrl;
    this.timeout = timeout;
  }

  private normalizeBalanceResponse(raw: any, address: string): BalanceResponse {
    const amount_i64 = Number.isSafeInteger(raw?.amount_i64)
      ? raw.amount_i64
      : Number.isSafeInteger(raw?.balance)
        ? raw.balance
        : 0;
    const amount_rtc = typeof raw?.amount_rtc === 'number'
      ? raw.amount_rtc
      : amount_i64 / MICRO_RTC_PER_RTC;

    return {
      miner: String(raw?.miner ?? raw?.miner_id ?? address),
      amount_i64,
      amount_rtc,
      balance: amount_i64,
      unlocked: Number.isSafeInteger(raw?.unlocked) ? raw.unlocked : amount_i64,
      locked: Number.isSafeInteger(raw?.locked) ? raw.locked : 0,
      nonce: Number.isSafeInteger(raw?.nonce) ? raw.nonce : undefined,
    };
  }

  private normalizeTransactionResponse(raw: any): TransactionResponse {
    return {
      tx_hash: String(raw?.tx_hash ?? ''),
      status: String(raw?.status ?? raw?.phase ?? (raw?.ok ? 'pending' : 'unknown')),
      verified: raw?.verified === true,
      confirms_at: Number.isSafeInteger(raw?.confirms_at) ? raw.confirms_at : undefined,
      message: typeof raw?.message === 'string' ? raw.message : undefined,
    };
  }

  /**
   * Create client with custom URL
   */
  static withUrl(url: string, timeout: number = 30000): RustChainClient {
    const client = new RustChainClient(Network.Mainnet, timeout);
    client.baseUrl = url;
    return client;
  }

  /**
   * Make HTTP request to API
   */
  private async request<T>(
    method: string,
    endpoint: string,
    data?: any
  ): Promise<T> {
    const url = `${this.baseUrl}/${endpoint.replace(/^\//, '')}`;

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const options: RequestInit = {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        signal: controller.signal,
      };

      if (data && (method === 'POST' || method === 'PUT')) {
        options.body = JSON.stringify(data);
      }

      const response = await fetch(url, options);
      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new RustChainApiError(
          `HTTP ${response.status}: ${response.statusText}`,
          response.status
        );
      }

      const result = await response.json();
      return result as T;
    } catch (error) {
      clearTimeout(timeoutId);
      if (error instanceof RustChainApiError) {
        throw error;
      }
      if (error instanceof Error && error.name === 'AbortError') {
        throw new RustChainApiError('Request timeout', 408);
      }
      throw new RustChainApiError(
        `Request failed: ${error instanceof Error ? error.message : String(error)}`,
        undefined,
        error instanceof Error ? error : undefined
      );
    }
  }

  /**
   * Get balance for a wallet address
   */
  async getBalance(address: string): Promise<BalanceResponse> {
    // Validate address format
    if (!isValidAddress(address)) {
      throw new RustChainApiError('Invalid wallet address format');
    }
    
    const result = await this.request<any>('GET', `/wallet/balance?address=${encodeURIComponent(address)}`);
    return this.normalizeBalanceResponse(result, address);
  }

  async getTransferHistory(address: string, limit: number = 50): Promise<TransferHistoryItem[]> {
    if (!isValidAddress(address)) {
      throw new RustChainApiError('Invalid wallet address format');
    }
    const safeLimit = Math.max(1, Math.min(Math.trunc(limit || 50), 200));
    return this.request<TransferHistoryItem[]>(
      'GET',
      `/wallet/history?address=${encodeURIComponent(address)}&limit=${safeLimit}`
    );
  }

  /**
   * Get network information (includes chain_id)
   */
  async getNetworkInfo(): Promise<NetworkInfo> {
    const info = await this.request<NetworkInfo>('GET', '/api/stats');
    
    // Cache chain_id for signing
    if (info.chain_id) {
      this.chainId = info.chain_id;
    }
    
    return info;
  }

  /**
   * Get current nonce for an address
   */
  async getNonce(address: string): Promise<number> {
    return NonceStore.getNextNonce(address);
  }

  /**
   * Get minimum transaction fee
   */
  async getMinFee(): Promise<number> {
    const info = await this.getNetworkInfo();
    return info.min_fee;
  }

  /**
   * Get cached chain_id (fetches if not cached)
   */
  async getChainId(): Promise<string> {
    if (!this.chainId) {
      await this.getNetworkInfo();
    }
    return this.chainId!;
  }

  /**
   * Estimate fee for a transaction
   */
  async estimateFee(amount: number, priority: 'low' | 'normal' | 'high' | 'instant' = 'normal'): Promise<number> {
    return 0;
  }

  /**
   * Build a transaction (unsigned)
   */
  buildTransaction(options: TransactionOptions): Transaction {
    return {
      from: options.from,
      to: options.to,
      amount: options.amount,
      nonce: options.nonce,
      memo: options.memo,
    };
  }

  /**
   * Sign a transaction with chain_id binding
   * Issue #785: Include chain_id in signed payload
   */
  async signTransaction(tx: Transaction, keyPair: KeyPair): Promise<Transaction> {
    // Get chain_id for signing
    const chainId = await this.getChainId();
    if (!isValidChainId(chainId)) {
      throw new RustChainApiError('Invalid chain_id returned by network');
    }
    
    // Create signing payload with chain_id
    const signature = signTransactionPayload(
      {
        from: tx.from,
        to: tx.to,
        amount: tx.amount,
        nonce: tx.nonce,
        memo: tx.memo,
      },
      chainId,
      keyPair.secretKey
    );

    return {
      ...tx,
      signature,
      chain_id: chainId,
      public_key: publicKeyToHex(keyPair.publicKey),
    };
  }

  /**
   * Submit a signed transaction
   */
  async submitTransaction(tx: Transaction): Promise<TransactionResponse> {
    if (!tx.signature) {
      throw new RustChainApiError('Transaction not signed');
    }
    if (!tx.public_key || !/^[0-9a-fA-F]{64}$/.test(tx.public_key)) {
      throw new RustChainApiError('Transaction missing public key');
    }
    if (!Number.isSafeInteger(tx.nonce) || tx.nonce <= 0) {
      throw new RustChainApiError('Transaction nonce must be a safe positive integer');
    }
    if (typeof tx.amount !== 'number' || !Number.isFinite(tx.amount) || tx.amount <= 0) {
      throw new RustChainApiError('Transaction amount must be a positive finite RTC value');
    }

    const payload: Record<string, unknown> = {
      from_address: tx.from,
      to_address: tx.to,
      amount_rtc: tx.amount,
      nonce: tx.nonce,
      memo: tx.memo ?? '',
      public_key: tx.public_key,
      signature: tx.signature,
    };

    if (tx.chain_id) {
      if (!isValidChainId(tx.chain_id)) {
        throw new RustChainApiError('Transaction has invalid chain_id');
      }
      payload.chain_id = tx.chain_id;
    }

    const result = await this.request<any>('POST', '/wallet/transfer/signed', payload);
    return this.normalizeTransactionResponse(result);
  }

  /**
   * Perform a transfer (build, sign, submit)
   */
  async transfer(
    fromKeyPair: KeyPair,
    toAddress: string,
    amount: number,
    options?: { memo?: string }
  ): Promise<TransactionResponse> {
    const fromAddress = await publicKeyToRtcAddress(fromKeyPair.publicKey);

    // Validate recipient address
    if (!isValidAddress(toAddress)) {
      throw new RustChainApiError('Invalid recipient address');
    }

    if (!Number.isSafeInteger(amount) || amount <= 0) {
      throw new RustChainApiError('Amount must be a positive safe integer in micro-RTC');
    }

    // Reserve a unique local nonce immediately so rapid sends cannot reuse it.
    const nonce = await NonceStore.reserveNextNonce(fromAddress);

    // Build transaction
    const tx = this.buildTransaction({
      from: fromAddress,
      to: toAddress,
      amount: amount / MICRO_RTC_PER_RTC,
      nonce,
      memo: options?.memo,
    });

    // Sign transaction (includes chain_id)
    const signedTx = await this.signTransaction(tx, fromKeyPair);

    // Submit transaction
    return this.submitTransaction(signedTx);
  }

  /**
   * Health check - verify API is reachable
   */
  async healthCheck(): Promise<boolean> {
    try {
      await this.getNetworkInfo();
      return true;
    } catch {
      return false;
    }
  }
}

/**
 * Dry-run a transaction without submitting
 * Returns validation result and estimated costs
 */
export interface DryRunResult {
  valid: boolean;
  errors: string[];
  estimatedFee: number;
  totalCost: number;
  senderBalance?: number;
  sufficientBalance: boolean;
}

export async function dryRunTransfer(
  client: RustChainClient,
  fromKeyPairOrAddress: KeyPair | string,
  toAddress: string,
  amount: number,
  options?: { memo?: string }
): Promise<DryRunResult> {
  const errors: string[] = [];
  const fromAddress = typeof fromKeyPairOrAddress === 'string'
    ? fromKeyPairOrAddress
    : await publicKeyToRtcAddress(fromKeyPairOrAddress.publicKey);

  // Validate recipient address format (strict)
  if (!toAddress || !isValidAddress(toAddress)) {
    errors.push('Invalid recipient address format');
  }

  if (!Number.isSafeInteger(amount) || amount <= 0) {
    errors.push('Amount must be a positive safe integer in micro-RTC');
  }

  // Get sender balance
  let senderBalance = 0;
  let sufficientBalance = false;
  try {
    const balanceResp = await client.getBalance(fromAddress);
    senderBalance = balanceResp.balance;

    const fee = 0;
    const totalCost = amount + fee;
    sufficientBalance = senderBalance >= totalCost;

    if (!sufficientBalance) {
      errors.push(`Insufficient balance. Required: ${totalCost}, Available: ${senderBalance}`);
    }
  } catch (e) {
    errors.push('Failed to fetch sender balance');
  }

  // Get estimated fee
  let estimatedFee = 0;

  return {
    valid: errors.length === 0,
    errors,
    estimatedFee,
    totalCost: amount + estimatedFee,
    senderBalance,
    sufficientBalance,
  };
}

/**
 * Validate transaction input strings
 * Issue #785: Numeric validation hardening
 */
export interface TransactionInputValidation {
  valid: boolean;
  errors: string[];
  parsedAmount?: number;
  parsedFee?: number;
}

export function validateTransactionInput(
  amountStr: string,
  feeStr?: string
): TransactionInputValidation {
  const errors: string[] = [];
  let parsedAmount: number | undefined;
  let parsedFee: number | undefined;

  // Validate amount
  const amountResult = validateTransactionAmount(amountStr);
  if (!amountResult.valid) {
    errors.push(`Amount: ${amountResult.error}`);
  } else if (amountResult.value !== undefined) {
    parsedAmount = amountResult.value;
  }

  // Validate fee if provided
  if (feeStr && feeStr.trim()) {
    const feeResult = validateTransactionFee(feeStr);
    if (!feeResult.valid) {
      errors.push(`Fee: ${feeResult.error}`);
    } else if (feeResult.value !== undefined) {
      parsedFee = feeResult.value;
    }
  }

  return {
    valid: errors.length === 0,
    errors,
    parsedAmount,
    parsedFee,
  };
}
