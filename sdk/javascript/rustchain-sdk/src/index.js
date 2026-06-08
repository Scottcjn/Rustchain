const DEFAULT_BASE_URL = "https://rustchain.org";
const DEFAULT_TIMEOUT_MS = 30000;

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

  async transfer({ from, to, amount, signature, fee = 0.01 }) {
    assertNonEmptyString(from, "from");
    assertNonEmptyString(to, "to");
    validatePositiveNumber(amount, "amount");
    validateNonNegativeNumber(fee, "fee");

    return this.request("POST", "/transfer", {
      from,
      to,
      amount,
      fee,
      ...(signature ? { signature } : {})
    });
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
