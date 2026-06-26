/**
 * @elyan/staking — TypeScript staking SDK for RustChain
 *
 * Implements the staking gate protocol: stake RTC, submit results,
 * poll for verdicts, and verify Ed25519-signed attestations.
 *
 * Reference: https://github.com/Scottcjn/rustchain-bounties/issues/14381
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface StakingConfig {
  /** Gate endpoint URL (e.g. https://gate.rustchain.org) */
  baseUrl?: string;
  /** Bearer API key for the gate */
  apiKey?: string;
  /** Gate public key for Ed25519 verdict verification */
  gatePubkey?: string;
  /** Request timeout in ms (default: 30000) */
  timeoutMs?: number;
  /** Custom fetch implementation (Node 18+ default) */
  fetch?: typeof globalThis.fetch;
}

export interface StakeRequest {
  /** Skill/domain identifier */
  skill: string;
  /** Amount of RTC to bond */
  bondRtc: number;
  /** Optional agent/wallet identifier */
  agentId?: string;
}

export interface StakeResponse {
  taskId: string;
  status: "pending" | "accepted" | "rejected";
  bondedRtc: number;
  createdAt: string;
  /** ISO timestamp when the stake expires */
  expiresAt?: string;
}

export interface SubmitRequest {
  taskId: string;
  /** Result payload (freeform — depends on skill) */
  result: Record<string, unknown>;
}

export interface SubmitResponse {
  taskId: string;
  status: "submitted" | "verified" | "rejected";
  /** Raw signed verdict from the gate */
  verdict?: string;
}

export interface PollResponse {
  taskId: string;
  status: "pending" | "processing" | "verified" | "rejected" | "expired";
  /** Ed25519-signed verdict (present when status === "verified") */
  verdict?: string;
  /** On-chain attestation hash */
  attestation?: string;
  /** Error message if rejected */
  error?: string;
}

export interface VerifyResult {
  valid: boolean;
  /** Recovered signer address */
  signer?: string;
  /** Error detail if invalid */
  error?: string;
}

// ---------------------------------------------------------------------------
// Error types
// ---------------------------------------------------------------------------

export class StakingError extends Error {
  constructor(message: string, public readonly code?: string) {
    super(message);
    this.name = "StakingError";
  }
}

export class StakingAuthError extends StakingError {
  constructor(message = "Authentication failed — check apiKey") {
    super(message, "AUTH_ERROR");
    this.name = "StakingAuthError";
  }
}

export class StakingValidationError extends StakingError {
  constructor(message: string) {
    super(message, "VALIDATION_ERROR");
    this.name = "StakingValidationError";
  }
}

// ---------------------------------------------------------------------------
// Ed25519 helpers (pure JS, no native deps)
// ---------------------------------------------------------------------------

/**
 * Minimal Ed25519 verification using the Web Crypto API.
 * Falls back gracefully if SubtleCrypto is unavailable (logs warning, returns false).
 */
function toArrayBuffer(bytes: Uint8Array): ArrayBuffer {
  const buf = new ArrayBuffer(bytes.byteLength);
  new Uint8Array(buf).set(bytes);
  return buf;
}

async function verifyEd25519(
  message: Uint8Array,
  signature: Uint8Array,
  publicKey: Uint8Array,
): Promise<boolean> {
  // Normalise key to 32 bytes
  const rawKey = publicKey.length === 32
    ? publicKey
    : publicKey.slice(0, 32);

  try {
    const key = await crypto.subtle.importKey(
      "raw",
      toArrayBuffer(rawKey),
      { name: "Ed25519" },
      false,
      ["verify"],
    );
    return await crypto.subtle.verify(
      "Ed25519",
      key,
      toArrayBuffer(signature),
      toArrayBuffer(message),
    );
  } catch (err) {
    // Some runtimes (e.g. older Node, Bun, Deno compat modes)
    // don't expose Ed25519 via SubtleCrypto yet.
    console.warn(
      "[@elyan/staking] Ed25519 verification unavailable in this runtime:",
      (err as Error).message,
    );
    return false;
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function assertString(value: unknown, name: string): asserts value is string {
  if (typeof value !== "string" || value.length === 0) {
    throw new StakingValidationError(`${name} must be a non-empty string`);
  }
}

function assertPositiveNumber(value: unknown, name: string): asserts value is number {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) {
    throw new StakingValidationError(`${name} must be a positive number`);
  }
}

function base64ToBytes(b64: string): Uint8Array {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes;
}

// ---------------------------------------------------------------------------
// Client
// ---------------------------------------------------------------------------

const DEFAULT_BASE_URL = "https://gate.rustchain.org";
const DEFAULT_TIMEOUT_MS = 30_000;

export class StakingClient {
  private readonly baseUrl: string;
  private readonly apiKey: string | undefined;
  private readonly gatePubkey: string | undefined;
  private readonly timeoutMs: number;
  private readonly fetchImpl: typeof globalThis.fetch;

  constructor(config: StakingConfig = {}) {
    this.baseUrl = (config.baseUrl ?? DEFAULT_BASE_URL).replace(/\/+$/, "");
    this.apiKey = config.apiKey;
    this.gatePubkey = config.gatePubkey;
    this.timeoutMs = config.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    this.fetchImpl = config.fetch ?? globalThis.fetch;

    if (typeof this.fetchImpl !== "function") {
      throw new StakingValidationError(
        "A fetch implementation is required. Use Node 18+ or pass { fetch }.",
      );
    }
  }

  // -----------------------------------------------------------------------
  // Stake
  // -----------------------------------------------------------------------

  async stake(request: StakeRequest): Promise<StakeResponse> {
    assertString(request.skill, "skill");
    assertPositiveNumber(request.bondRtc, "bondRtc");

    return this._post<StakeResponse>("/v1/stake", {
      skill: request.skill,
      bond_rtc: request.bondRtc,
      agent_id: request.agentId,
    });
  }

  // -----------------------------------------------------------------------
  // Submit
  // -----------------------------------------------------------------------

  async submit(request: SubmitRequest): Promise<SubmitResponse> {
    assertString(request.taskId, "taskId");
    if (!request.result || typeof request.result !== "object") {
      throw new StakingValidationError("result must be a non-empty object");
    }

    return this._post<SubmitResponse>(`/v1/tasks/${request.taskId}/submit`, {
      result: request.result,
    });
  }

  // -----------------------------------------------------------------------
  // Poll
  // -----------------------------------------------------------------------

  async poll(taskId: string): Promise<PollResponse> {
    assertString(taskId, "taskId");
    return this._get<PollResponse>(`/v1/tasks/${taskId}`);
  }

  // -----------------------------------------------------------------------
  // Verify
  // -----------------------------------------------------------------------

  /**
   * Verify an Ed25519-signed verdict from the gate.
   *
   * If `gatePubkey` was provided in the constructor it is used;
   * otherwise pass `pubkey` explicitly.
   */
  async verify(
    verdict: string,
    pubkey?: string,
  ): Promise<VerifyResult> {
    assertString(verdict, "verdict");

    const key = pubkey ?? this.gatePubkey;
    if (!key) {
      return {
        valid: false,
        error:
          "No public key provided — pass a pubkey or set gatePubkey in the constructor",
      };
    }

    try {
      // Expected format: base64(message) "." base64(signature)
      const dot = verdict.lastIndexOf(".");
      if (dot === -1) {
        return { valid: false, error: "Invalid verdict format: expected 'msg.sig'" };
      }

      const msgB64 = verdict.slice(0, dot);
      const sigB64 = verdict.slice(dot + 1);

      const message = base64ToBytes(msgB64);
      const signature = base64ToBytes(sigB64);
      const pubkeyBytes = base64ToBytes(key);

      const valid = await verifyEd25519(message, signature, pubkeyBytes);

      return {
        valid,
        signer: valid ? key : undefined,
        error: valid ? undefined : "Signature does not match the provided public key",
      };
    } catch (err) {
      return {
        valid: false,
        error: `Verification error: ${(err as Error).message}`,
      };
    }
  }

  // -----------------------------------------------------------------------
  // Internal HTTP helpers
  // -----------------------------------------------------------------------

  private async _request<T>(
    method: string,
    path: string,
    body?: Record<string, unknown>,
  ): Promise<T> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);

    const headers: Record<string, string> = {
      Accept: "application/json",
      "Content-Type": "application/json",
      "User-Agent": "@elyan/staking/0.1.0",
    };

    if (this.apiKey) {
      headers["Authorization"] = `Bearer ${this.apiKey}`;
    }

    try {
      const url = `${this.baseUrl}${path}`;
      const resp = await this.fetchImpl(url, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });

      // 402 = x402 payment required => not an error per se, but a signal
      if (resp.status === 402) {
        const paymentRequired = await resp.json().catch(() => ({}));
        throw new StakingError(
          `x402 payment required: ${JSON.stringify(paymentRequired)}`,
          "PAYMENT_REQUIRED",
        );
      }

      if (!resp.ok) {
        const errBody = await resp.text().catch(() => "unknown");
        if (resp.status === 401 || resp.status === 403) {
          throw new StakingAuthError();
        }
        throw new StakingError(
          `HTTP ${resp.status}: ${errBody}`,
          `HTTP_${resp.status}`,
        );
      }

      return (await resp.json()) as T;
    } catch (err) {
      if (err instanceof StakingError) throw err;
      if ((err as Error)?.name === "AbortError") {
        throw new StakingError(
          `Request timed out after ${this.timeoutMs}ms`,
          "TIMEOUT",
        );
      }
      throw new StakingError(
        `Request failed: ${(err as Error).message}`,
        "NETWORK_ERROR",
      );
    } finally {
      clearTimeout(timer);
    }
  }

  private _get<T>(path: string): Promise<T> {
    return this._request<T>("GET", path);
  }

  private _post<T>(path: string, body: Record<string, unknown>): Promise<T> {
    return this._request<T>("POST", path, body);
  }
}

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

export function createStakingClient(config?: StakingConfig): StakingClient {
  return new StakingClient(config);
}
