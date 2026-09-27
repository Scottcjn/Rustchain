const DEFAULT_BASE_URL = "https://rustchain.org";
const DEFAULT_TIMEOUT_MS = 30000;

export const AGENT_JOB_CATEGORIES = Object.freeze([
  "research",
  "code",
  "video",
  "audio",
  "writing",
  "translation",
  "data",
  "design",
  "testing",
  "other"
]);

export class RustChainError extends Error {
  constructor(message, options = {}) {
    super(message);
    this.name = "RustChainError";
    this.cause = options.cause;
  }
}

export class RustChainApiError extends RustChainError {
  constructor(message, options = {}) {
    super(message, options);
    this.name = "RustChainApiError";
    this.status = options.status;
    this.endpoint = options.endpoint;
    this.body = options.body;
  }
}

export class RustChainValidationError extends RustChainError {
  constructor(message) {
    super(message);
    this.name = "RustChainValidationError";
  }
}

export class RustChainClient {
  constructor(options = {}) {
    const baseUrl = typeof options === "string" ? options : options.baseUrl;

    this.baseUrl = normalizeBaseUrl(baseUrl || DEFAULT_BASE_URL);
    this.timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    this.fetchImpl = options.fetch ?? globalThis.fetch;

    if (typeof this.fetchImpl !== "function") {
      throw new RustChainValidationError("A fetch implementation is required. Use Node 18+ or pass { fetch }.");
    }
  }

  async health() {
    return this.request("GET", "/health");
  }

  async epoch() {
    return this.request("GET", "/epoch");
  }

  async miners(options = {}) {
    const params = new URLSearchParams();
    if (options.limit !== undefined) params.set("limit", String(validatePositiveInteger(options.limit, "limit")));
    if (options.offset !== undefined) params.set("offset", String(validateNonNegativeInteger(options.offset, "offset")));
    if (options.hardwareType) params.set("hardware_type", String(options.hardwareType));

    const result = await this.request("GET", withQuery("/api/miners", params));
    if (Array.isArray(result)) return result;
    if (Array.isArray(result?.miners)) return result.miners;
    if (Array.isArray(result?.data)) return result.data;
    if (Array.isArray(result?.items)) return result.items;
    return [];
  }

  async balance(minerId) {
    assertNonEmptyString(minerId, "minerId");
    const params = new URLSearchParams({ miner_id: minerId });
    return this.request("GET", withQuery("/wallet/balance", params));
  }

  async transfer(options = {}) {
    if (!options || typeof options !== "object" || Array.isArray(options)) {
      throw new RustChainValidationError("transfer options must be an object");
    }

    const from = options.from ?? options.from_address;
    const to = options.to ?? options.to_address;
    const amount = options.amount ?? options.amount_rtc;
    const fee = options.fee ?? options.fee_rtc ?? 0;
    const publicKey = options.publicKey ?? options.public_key;
    const chainId = options.chainId ?? options.chain_id;
    const nonce = validatePositiveInteger(options.nonce, "nonce");

    assertNonEmptyString(from, "from");
    assertNonEmptyString(to, "to");
    assertNonEmptyString(options.signature, "signature");
    if (isRtcAddress(from) || publicKey !== undefined) {
      assertNonEmptyString(publicKey, "publicKey");
    }
    validatePositiveNumber(amount, "amount");
    validateNonNegativeNumber(fee, "fee");

    const payload = {
      from_address: from,
      to_address: to,
      amount_rtc: Number(amount),
      fee_rtc: Number(fee),
      nonce,
      signature: options.signature,
      ...(publicKey ? { public_key: publicKey } : {}),
      ...(options.memo !== undefined ? { memo: String(options.memo) } : {}),
      ...(chainId !== undefined ? { chain_id: String(chainId) } : {})
    };

    return this.request("POST", "/wallet/transfer/signed", payload);
  }

  async attestChallenge(payload = {}) {
    return this.request("POST", "/attest/challenge", payload);
  }

  async submitAttestation(payload) {
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
      throw new RustChainValidationError("payload must be an object");
    }
    return this.request("POST", "/attest/submit", payload);
  }

  async transferHistory(wallet, options = {}) {
    assertNonEmptyString(wallet, "wallet");
    const params = new URLSearchParams({ miner_id: wallet });
    if (options.limit !== undefined) params.set("limit", String(validatePositiveInteger(options.limit, "limit")));
    const result = await this.request("GET", withQuery("/wallet/history", params));
    if (Array.isArray(result)) return result;
    if (Array.isArray(result?.transactions)) return result.transactions;
    if (Array.isArray(result?.history)) return result.history;
    if (Array.isArray(result?.items)) return result.items;
    return [];
  }

  async listJobs(options = {}) {
    const params = new URLSearchParams();
    if (options.category !== undefined) {
      assertAgentJobCategory(options.category);
      params.set("category", options.category);
    }
    if (options.status !== undefined) {
      assertNonEmptyString(options.status, "status");
      params.set("status", options.status);
    }
    if (options.limit !== undefined) {
      const limit = validateNonNegativeInteger(options.limit, "limit");
      if (limit > 100) throw new RustChainValidationError("limit must be at most 100");
      params.set("limit", String(limit));
    }
    if (options.offset !== undefined) {
      params.set("offset", String(validateNonNegativeInteger(options.offset, "offset")));
    }
    if (options.minReward !== undefined) {
      params.set("min_reward", String(validateNonNegativeNumber(options.minReward, "minReward")));
    }
    return this.request("GET", withQuery("/agent/jobs", params));
  }

  async getJob(jobId) {
    assertNonEmptyString(jobId, "jobId");
    return this.request("GET", `/agent/jobs/${encodeURIComponent(jobId)}`);
  }

  async postJob(options = {}) {
    assertObject(options, "postJob options");
    assertNonEmptyString(options.posterWallet, "posterWallet");
    assertMinLength(options.title, 5, "title");
    assertMinLength(options.description, 20, "description");
    assertAgentJobCategory(options.category ?? "other");
    const rewardRtc = validateRangeNumber(options.rewardRtc, "rewardRtc", 0.01, 10000);
    const ttlSeconds = validatePositiveInteger(options.ttlSeconds, "ttlSeconds");

    return this.request("POST", "/agent/jobs", {
      poster_wallet: options.posterWallet,
      title: options.title,
      description: options.description,
      category: options.category ?? "other",
      reward_rtc: rewardRtc,
      ttl_seconds: ttlSeconds,
      ...(options.tags !== undefined ? { tags: normalizeTags(options.tags) } : {})
    });
  }

  async claimJob(jobId, workerWallet) {
    assertNonEmptyString(jobId, "jobId");
    assertNonEmptyString(workerWallet, "workerWallet");
    return this.request("POST", `/agent/jobs/${encodeURIComponent(jobId)}/claim`, {
      worker_wallet: workerWallet
    });
  }

  async deliverJob(jobId, options = {}) {
    assertNonEmptyString(jobId, "jobId");
    assertObject(options, "deliverJob options");
    assertNonEmptyString(options.workerWallet, "workerWallet");
    if (options.deliverableUrl === undefined && options.resultSummary === undefined) {
      throw new RustChainValidationError("deliverableUrl or resultSummary is required");
    }
    const body = {
      worker_wallet: options.workerWallet,
      ...(options.deliverableUrl !== undefined ? { deliverable_url: String(options.deliverableUrl) } : {}),
      ...(options.deliverableHash !== undefined ? { deliverable_hash: String(options.deliverableHash) } : {}),
      ...(options.resultSummary !== undefined ? { result_summary: String(options.resultSummary) } : {})
    };
    return this.request("POST", `/agent/jobs/${encodeURIComponent(jobId)}/deliver`, body);
  }

  async acceptJob(jobId, options = {}) {
    assertNonEmptyString(jobId, "jobId");
    assertObject(options, "acceptJob options");
    assertNonEmptyString(options.posterWallet, "posterWallet");
    const body = { poster_wallet: options.posterWallet };
    if (options.rating !== undefined) {
      const rating = validateRangeNumber(options.rating, "rating", 1, 5);
      if (!Number.isInteger(rating)) throw new RustChainValidationError("rating must be an integer from 1 to 5");
      body.rating = rating;
    }
    return this.request("POST", `/agent/jobs/${encodeURIComponent(jobId)}/accept`, body);
  }

  async disputeJob(jobId, posterWallet, reason) {
    assertNonEmptyString(jobId, "jobId");
    assertNonEmptyString(posterWallet, "posterWallet");
    assertNonEmptyString(reason, "reason");
    return this.request("POST", `/agent/jobs/${encodeURIComponent(jobId)}/dispute`, {
      poster_wallet: posterWallet,
      reason
    });
  }

  async cancelJob(jobId, posterWallet) {
    assertNonEmptyString(jobId, "jobId");
    assertNonEmptyString(posterWallet, "posterWallet");
    return this.request("POST", `/agent/jobs/${encodeURIComponent(jobId)}/cancel`, {
      poster_wallet: posterWallet
    });
  }

  async reputation(walletId) {
    assertNonEmptyString(walletId, "walletId");
    return this.request("GET", `/agent/reputation/${encodeURIComponent(walletId)}`);
  }

  async agentStats() {
    return this.request("GET", "/agent/stats");
  }

  async request(method, endpoint, body) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    const headers = {
      Accept: "application/json",
      "User-Agent": "rustchain-js-sdk/0.1.0"
    };

    let fetchBody;
    if (body !== undefined) {
      headers["Content-Type"] = "application/json";
      fetchBody = JSON.stringify(body);
    }

    try {
      const response = await this.fetchImpl(`${this.baseUrl}${endpoint}`, {
        method,
        headers,
        body: fetchBody,
        redirect: "manual",
        signal: controller.signal
      });

      const responseText = await response.text();
      const parsed = parseResponseBody(responseText);

      if (response.status >= 300 && response.status < 400) {
        throw new RustChainApiError(`API redirected with HTTP ${response.status}`, {
          status: response.status,
          endpoint,
          body: parsed
        });
      }

      if (!response.ok) {
        throw new RustChainApiError(`API request failed with HTTP ${response.status}`, {
          status: response.status,
          endpoint,
          body: parsed
        });
      }

      return parsed;
    } catch (error) {
      if (error instanceof RustChainApiError) throw error;
      if (error?.name === "AbortError") {
        throw new RustChainError(`Request timed out after ${this.timeoutMs} ms`, { cause: error });
      }
      throw new RustChainError(`Request failed: ${error?.message || String(error)}`, { cause: error });
    } finally {
      clearTimeout(timer);
    }
  }
}

export function createClient(options) {
  return new RustChainClient(options);
}

function normalizeBaseUrl(baseUrl) {
  assertNonEmptyString(baseUrl, "baseUrl");
  return baseUrl.replace(/\/+$/, "");
}

function withQuery(path, params) {
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}

function parseResponseBody(text) {
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    return { rawResponse: text };
  }
}

function assertNonEmptyString(value, name) {
  if (typeof value !== "string" || value.trim() === "") {
    throw new RustChainValidationError(`${name} must be a non-empty string`);
  }
}

function assertObject(value, name) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new RustChainValidationError(`${name} must be an object`);
  }
}

function assertMinLength(value, minLength, name) {
  assertNonEmptyString(value, name);
  if (value.trim().length < minLength) {
    throw new RustChainValidationError(`${name} must be at least ${minLength} characters`);
  }
}

function assertAgentJobCategory(value) {
  assertNonEmptyString(value, "category");
  if (!AGENT_JOB_CATEGORIES.includes(value)) {
    throw new RustChainValidationError(`category must be one of: ${AGENT_JOB_CATEGORIES.join(", ")}`);
  }
}

function normalizeTags(value) {
  if (Array.isArray(value)) return value.map((tag) => String(tag));
  return String(value);
}

function isRtcAddress(value) {
  return typeof value === "string" && /^RTC[0-9a-fA-F]{40}$/.test(value);
}

function validatePositiveInteger(value, name) {
  const number = Number(value);
  if (!Number.isInteger(number) || number <= 0) {
    throw new RustChainValidationError(`${name} must be a positive integer`);
  }
  return number;
}

function validateNonNegativeInteger(value, name) {
  const number = Number(value);
  if (!Number.isInteger(number) || number < 0) {
    throw new RustChainValidationError(`${name} must be a non-negative integer`);
  }
  return number;
}

function validatePositiveNumber(value, name) {
  const number = Number(value);
  if (!Number.isFinite(number) || number <= 0) {
    throw new RustChainValidationError(`${name} must be a positive number`);
  }
  return number;
}

function validateNonNegativeNumber(value, name) {
  const number = Number(value);
  if (!Number.isFinite(number) || number < 0) {
    throw new RustChainValidationError(`${name} must be a non-negative number`);
  }
  return number;
}

function validateRangeNumber(value, name, minimum, maximum) {
  const number = Number(value);
  if (!Number.isFinite(number) || number < minimum || number > maximum) {
    throw new RustChainValidationError(`${name} must be between ${minimum} and ${maximum}`);
  }
  return number;
}
