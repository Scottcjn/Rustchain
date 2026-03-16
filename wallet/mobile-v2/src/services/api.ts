/**
 * RustChain API Client
 *
 * Communicates with the RustChain node for balance queries,
 * transaction submission, transfer history, and network info.
 */

import type {
  KeyPair,
  BalanceResponse,
  TransactionResponse,
  TransferHistoryItem,
  NetworkInfo,
  Transaction,
  TransactionOptions,
  DryRunResult,
  NetworkId,
  NetworkConfig,
} from '../types';
import { MICRO_RTC_PER_RTC } from '../types';
import {
  isValidAddress,
  isValidChainId,
  publicKeyToHex,
  publicKeyToRtcAddress,
  signTransactionPayload,
  validateTransactionAmount,
  validateTransactionFee,
} from './wallet';
import { NonceStore } from './storage';

// ── Network Configuration ───────────────────────────────────────────────────

const DEFAULT_CONFIGS: Record<NetworkId, NetworkConfig> = {
  mainnet: {
    rpcUrl: 'https://rustchain.org',
    explorerUrl: 'https://rustchain.org/explorer',
  },
  testnet: {
    rpcUrl: 'https://testnet-rpc.rustchain.org',
    explorerUrl: 'https://testnet-explorer.rustchain.org',
  },
  devnet: {
    rpcUrl: 'https://devnet-rpc.rustchain.org',
    explorerUrl: 'https://devnet-explorer.rustchain.org',
  },
};

export function getNetworkConfig(network: NetworkId): NetworkConfig {
  const customUrl = process.env.EXPO_PUBLIC_RUSTCHAIN_NODE_URL;
  if (customUrl && network === 'mainnet') {
    return { rpcUrl: customUrl, explorerUrl: DEFAULT_CONFIGS.mainnet.explorerUrl };
  }
  return DEFAULT_CONFIGS[network];
}

export function getDefaultNetwork(): NetworkId {
  const env = process.env.EXPO_PUBLIC_NETWORK;
  if (env === 'testnet' || env === 'devnet') return env;
  return 'mainnet';
}

// ── Error Type ──────────────────────────────────────────────────────────────

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

// ── Client ──────────────────────────────────────────────────────────────────

export class RustChainClient {
  private baseUrl: string;
  private timeout: number;
  private chainId: string | null = null;

  constructor(network: NetworkId = getDefaultNetwork(), timeout: number = 30000) {
    this.baseUrl = getNetworkConfig(network).rpcUrl;
    this.timeout = timeout;
  }

  static withUrl(url: string, timeout = 30000): RustChainClient {
    const c = new RustChainClient('mainnet', timeout);
    c.baseUrl = url;
    return c;
  }

  // ── HTTP Layer ──────────────────────────────────────────────────────────

  private async request<T>(method: string, endpoint: string, data?: unknown): Promise<T> {
    const url = `${this.baseUrl}/${endpoint.replace(/^\//, '')}`;
    const ctrl = new AbortController();
    const tid = setTimeout(() => ctrl.abort(), this.timeout);

    try {
      const opts: RequestInit = {
        method,
        headers: { 'Content-Type': 'application/json' },
        signal: ctrl.signal,
      };
      if (data && (method === 'POST' || method === 'PUT')) {
        opts.body = JSON.stringify(data);
      }

      const res = await fetch(url, opts);
      clearTimeout(tid);

      if (!res.ok) {
        throw new RustChainApiError(`HTTP ${res.status}: ${res.statusText}`, res.status);
      }
      return (await res.json()) as T;
    } catch (err) {
      clearTimeout(tid);
      if (err instanceof RustChainApiError) throw err;
      if (err instanceof Error && err.name === 'AbortError') {
        throw new RustChainApiError('Request timeout', 408);
      }
      throw new RustChainApiError(
        `Request failed: ${err instanceof Error ? err.message : String(err)}`,
        undefined,
        err instanceof Error ? err : undefined
      );
    }
  }

  // ── Normalization ───────────────────────────────────────────────────────

  private normalizeBalance(raw: any, address: string): BalanceResponse {
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

  private normalizeTxResponse(raw: any): TransactionResponse {
    return {
      tx_hash: String(raw?.tx_hash ?? ''),
      status: String(raw?.status ?? raw?.phase ?? (raw?.ok ? 'pending' : 'unknown')),
      verified: raw?.verified === true,
      confirms_at: Number.isSafeInteger(raw?.confirms_at) ? raw.confirms_at : undefined,
      message: typeof raw?.message === 'string' ? raw.message : undefined,
    };
  }

  // ── Public API ──────────────────────────────────────────────────────────

  async getBalance(address: string): Promise<BalanceResponse> {
    if (!isValidAddress(address)) {
      throw new RustChainApiError('Invalid wallet address format');
    }
    const raw = await this.request<any>(
      'GET',
      `/wallet/balance?address=${encodeURIComponent(address)}`
    );
    return this.normalizeBalance(raw, address);
  }

  async getTransferHistory(address: string, limit = 50): Promise<TransferHistoryItem[]> {
    if (!isValidAddress(address)) {
      throw new RustChainApiError('Invalid wallet address format');
    }
    const safeLimit = Math.max(1, Math.min(Math.trunc(limit || 50), 200));
    return this.request<TransferHistoryItem[]>(
      'GET',
      `/wallet/history?address=${encodeURIComponent(address)}&limit=${safeLimit}`
    );
  }

  async getNetworkInfo(): Promise<NetworkInfo> {
    const info = await this.request<NetworkInfo>('GET', '/api/stats');
    if (info.chain_id) this.chainId = info.chain_id;
    return info;
  }

  async getChainId(): Promise<string> {
    if (!this.chainId) await this.getNetworkInfo();
    return this.chainId!;
  }

  async getNonce(address: string): Promise<number> {
    return NonceStore.getNextNonce(address);
  }

  async healthCheck(): Promise<boolean> {
    try {
      await this.getNetworkInfo();
      return true;
    } catch {
      return false;
    }
  }

  // ── Transaction Building ────────────────────────────────────────────────

  buildTransaction(opts: TransactionOptions): Transaction {
    return {
      from: opts.from,
      to: opts.to,
      amount: opts.amount,
      nonce: opts.nonce,
      memo: opts.memo,
    };
  }

  async signTransaction(tx: Transaction, keyPair: KeyPair): Promise<Transaction> {
    const chainId = await this.getChainId();
    if (!isValidChainId(chainId)) {
      throw new RustChainApiError('Invalid chain_id from network');
    }

    const signature = signTransactionPayload(
      { from: tx.from, to: tx.to, amount: tx.amount, nonce: tx.nonce, memo: tx.memo },
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

  async submitTransaction(tx: Transaction): Promise<TransactionResponse> {
    if (!tx.signature) throw new RustChainApiError('Transaction not signed');
    if (!tx.public_key || !/^[0-9a-fA-F]{64}$/.test(tx.public_key)) {
      throw new RustChainApiError('Missing public key');
    }
    if (!Number.isSafeInteger(tx.nonce) || tx.nonce <= 0) {
      throw new RustChainApiError('Nonce must be a safe positive integer');
    }
    if (typeof tx.amount !== 'number' || !Number.isFinite(tx.amount) || tx.amount <= 0) {
      throw new RustChainApiError('Amount must be a positive finite value');
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
      if (!isValidChainId(tx.chain_id)) throw new RustChainApiError('Invalid chain_id');
      payload.chain_id = tx.chain_id;
    }

    const raw = await this.request<any>('POST', '/wallet/transfer/signed', payload);
    return this.normalizeTxResponse(raw);
  }

  /** Build, sign, and submit a transfer in one call. */
  async transfer(
    fromKeyPair: KeyPair,
    toAddress: string,
    amountMicroRtc: number,
    options?: { memo?: string }
  ): Promise<TransactionResponse> {
    const fromAddress = await publicKeyToRtcAddress(fromKeyPair.publicKey);
    if (!isValidAddress(toAddress)) throw new RustChainApiError('Invalid recipient address');
    if (!Number.isSafeInteger(amountMicroRtc) || amountMicroRtc <= 0) {
      throw new RustChainApiError('Amount must be a positive safe integer in micro-RTC');
    }

    const nonce = await NonceStore.reserveNextNonce(fromAddress);
    const tx = this.buildTransaction({
      from: fromAddress,
      to: toAddress,
      amount: amountMicroRtc / MICRO_RTC_PER_RTC,
      nonce,
      memo: options?.memo,
    });
    const signed = await this.signTransaction(tx, fromKeyPair);
    return this.submitTransaction(signed);
  }
}

// ── Dry-Run ─────────────────────────────────────────────────────────────────

export async function dryRunTransfer(
  client: RustChainClient,
  fromKeyPairOrAddress: KeyPair | string,
  toAddress: string,
  amount: number,
  options?: { memo?: string }
): Promise<DryRunResult> {
  const errors: string[] = [];
  const fromAddress =
    typeof fromKeyPairOrAddress === 'string'
      ? fromKeyPairOrAddress
      : await publicKeyToRtcAddress(fromKeyPairOrAddress.publicKey);

  if (!toAddress || !isValidAddress(toAddress)) {
    errors.push('Invalid recipient address');
  }
  if (!Number.isSafeInteger(amount) || amount <= 0) {
    errors.push('Amount must be a positive safe integer in micro-RTC');
  }

  let senderBalance = 0;
  let sufficientBalance = false;
  try {
    const bal = await client.getBalance(fromAddress);
    senderBalance = bal.balance;
    const totalCost = amount;
    sufficientBalance = senderBalance >= totalCost;
    if (!sufficientBalance) {
      errors.push(`Insufficient balance. Need ${totalCost}, have ${senderBalance}`);
    }
  } catch {
    errors.push('Failed to fetch sender balance');
  }

  return {
    valid: errors.length === 0,
    errors,
    estimatedFee: 0,
    totalCost: amount,
    senderBalance,
    sufficientBalance,
  };
}

// ── Input Validation ────────────────────────────────────────────────────────

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

  const ar = validateTransactionAmount(amountStr);
  if (!ar.valid) errors.push(`Amount: ${ar.error}`);
  else parsedAmount = ar.value;

  if (feeStr?.trim()) {
    const fr = validateTransactionFee(feeStr);
    if (!fr.valid) errors.push(`Fee: ${fr.error}`);
    else parsedFee = fr.value;
  }

  return { valid: errors.length === 0, errors, parsedAmount, parsedFee };
}
