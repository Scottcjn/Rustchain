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

import { KeyPair, isValidAddress } from '../utils/crypto';
import {
  signString,
  publicKeyToBase58,
  createSigningPayload,
  signTransactionPayload,
  validateNumericString,
  validateTransactionAmount,
  validateTransactionFee,
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
  block_height?: number;
  confirmations?: number;
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
  fee: number;
  nonce: number;
  timestamp: string;
  memo?: string;
  signature?: string;
  chain_id?: string;
}

/**
 * Transaction builder options
 */
export interface TransactionOptions {
  from: string;
  to: string;
  amount: number;
  fee?: number;
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
    
    return this.request<BalanceResponse>('GET', `/wallet/balance?miner_id=${encodeURIComponent(address)}`);
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
    const balance = await this.getBalance(address);
    return balance.nonce ?? 0;
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
    const minFee = await this.getMinFee();
    const multipliers = {
      low: 1,
      normal: 2,
      high: 5,
      instant: 10,
    };
    return minFee * multipliers[priority];
  }

  /**
   * Build a transaction (unsigned)
   */
  buildTransaction(options: TransactionOptions): Transaction {
    return {
      from: options.from,
      to: options.to,
      amount: options.amount,
      fee: options.fee ?? 0,
      nonce: options.nonce,
      timestamp: new Date().toISOString(),
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
    
    // Create signing payload with chain_id
    const signature = signTransactionPayload(
      {
        from: tx.from,
        to: tx.to,
        amount: tx.amount,
        fee: tx.fee,
        nonce: tx.nonce,
        timestamp: tx.timestamp,
        memo: tx.memo,
      },
      chainId,
      keyPair.secretKey
    );

    return {
      ...tx,
      signature,
      chain_id: chainId,
    };
  }

  /**
   * Submit a signed transaction
   */
  async submitTransaction(tx: Transaction): Promise<TransactionResponse> {
    if (!tx.signature) {
      throw new RustChainApiError('Transaction not signed');
    }
    
    // Validate transaction structure
    if (!tx.chain_id) {
      throw new RustChainApiError('Transaction missing chain_id');
    }
    
    return this.request<TransactionResponse>('POST', '/api/transaction', tx);
  }

  /**
   * Perform a transfer (build, sign, submit)
   */
  async transfer(
    fromKeyPair: KeyPair,
    toAddress: string,
    amount: number,
    options?: { fee?: number; memo?: string }
  ): Promise<TransactionResponse> {
    const fromAddress = publicKeyToBase58(fromKeyPair.publicKey);

    // Validate recipient address
    if (!isValidAddress(toAddress)) {
      throw new RustChainApiError('Invalid recipient address');
    }

    // Get current nonce
    const nonce = await this.getNonce(fromAddress);

    // Get fee if not provided
    const fee = options?.fee ?? await this.estimateFee(amount);

    // Build transaction
    const tx = this.buildTransaction({
      from: fromAddress,
      to: toAddress,
      amount,
      fee,
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
  fromKeyPair: KeyPair,
  toAddress: string,
  amount: number,
  options?: { fee?: number; memo?: string }
): Promise<DryRunResult> {
  const errors: string[] = [];
  const fromAddress = publicKeyToBase58(fromKeyPair.publicKey);

  // Validate recipient address format (strict)
  if (!toAddress || !isValidAddress(toAddress)) {
    errors.push('Invalid recipient address format');
  }

  // Validate amount (must be positive)
  if (amount <= 0) {
    errors.push('Amount must be greater than 0');
  }

  // Get sender balance
  let senderBalance = 0;
  let sufficientBalance = false;
  try {
    const balanceResp = await client.getBalance(fromAddress);
    senderBalance = balanceResp.balance;

    const fee = options?.fee ?? await client.estimateFee(amount);
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
  try {
    estimatedFee = options?.fee ?? await client.estimateFee(amount);
  } catch {
    estimatedFee = 0;
    errors.push('Failed to estimate fee');
  }

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
