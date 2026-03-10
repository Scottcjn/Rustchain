/**
 * RustChain API Client
 * 
 * Provides methods for interacting with RustChain node API:
 * - Balance queries
 * - Transaction submission
 * - Network info
 */

import { KeyPair } from '../utils/crypto';
import { signString, publicKeyToBase58 } from '../utils/crypto';

/**
 * Network configuration
 */
export enum Network {
  Mainnet = 'mainnet',
  Testnet = 'testnet',
  Devnet = 'devnet',
}

export const NETWORK_CONFIG: Record<Network, { rpcUrl: string; explorerUrl: string }> = {
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
 * Transfer history item returned by the node.
 */
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
  confirmations: number;
  direction: 'sent' | 'received';
  counterparty: string;
  reason?: string | null;
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
  fee: number;
  nonce: number;
  timestamp: string;
  memo?: string;
  signature?: string;
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

  constructor(network: Network = Network.Mainnet, timeout: number = 30000) {
    this.baseUrl = NETWORK_CONFIG[network].rpcUrl;
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
    return this.request<BalanceResponse>('GET', `/wallet/balance?miner_id=${encodeURIComponent(address)}`);
  }

  /**
   * Get public transfer history for a wallet address.
   */
  async getTransferHistory(address: string, limit: number = 50): Promise<TransferHistoryItem[]> {
    return this.request<TransferHistoryItem[]>(
      'GET',
      `/wallet/history?miner_id=${encodeURIComponent(address)}&limit=${Math.max(1, Math.min(limit, 200))}`
    );
  }

  /**
   * Get network information
   */
  async getNetworkInfo(): Promise<NetworkInfo> {
    return this.request<NetworkInfo>('GET', '/api/stats');
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
   * Sign a transaction
   */
  signTransaction(tx: Transaction, keyPair: KeyPair): Transaction {
    // Create signing payload (excludes signature field)
    const signingData = {
      from: tx.from,
      to: tx.to,
      amount: tx.amount,
      fee: tx.fee,
      nonce: tx.nonce,
      timestamp: tx.timestamp,
      memo: tx.memo,
    };

    const payload = JSON.stringify(signingData);
    const signature = signString(payload, keyPair.secretKey);

    return {
      ...tx,
      signature,
    };
  }

  /**
   * Submit a signed transaction
   */
  async submitTransaction(tx: Transaction): Promise<TransactionResponse> {
    if (!tx.signature) {
      throw new RustChainApiError('Transaction not signed');
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

    // Sign transaction
    const signedTx = this.signTransaction(tx, fromKeyPair);

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

  // Validate recipient address format
  if (!toAddress || toAddress.length < 40) {
    errors.push('Invalid recipient address format');
  }

  // Validate amount
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
