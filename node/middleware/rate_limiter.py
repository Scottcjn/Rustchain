"""
RustChain API Rate Limiter
==========================
Token-bucket rate limiting middleware for the RustChain Flask node.

Features:
- Per-IP token bucket algorithm with configurable burst and refill rates
- Endpoint-specific limits (e.g. stricter limits on /api/mine, /attest/submit)
- Redis-backed storage for distributed multi-node deployments
- Automatic fallback to thread-safe in-memory storage when Redis is unavailable
- Proper 429 responses with Retry-After header (RFC 6585 / RFC 7231)
- Admin and health endpoints exempt by default

Usage:
    from middleware import init_rate_limiter
    init_rate_limiter(app)
"""

import time
import threading
import logging
from functools import wraps
from typing import Dict, Optional, Tuple

from flask import Flask, request, jsonify, g

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default configuration
# ---------------------------------------------------------------------------

# Global default: 60 requests per minute, burst of 20
DEFAULT_RATE = 60          # tokens added per window
DEFAULT_WINDOW = 60        # window length in seconds
DEFAULT_BURST = 20         # max tokens (bucket capacity)

# Per-endpoint overrides  (endpoint_prefix -> (rate, window, burst))
# Lower limits on write-heavy / compute-heavy paths
DEFAULT_ENDPOINT_LIMITS: Dict[str, Tuple[int, int, int]] = {
    "/api/mine":            (10,  60, 5),    # mining submissions
    "/attest/submit":       (15,  60, 5),    # attestation submissions
    "/attest/challenge":    (20,  60, 10),   # challenge requests
    "/epoch/enroll":        (10,  60, 5),    # epoch enrollment
    "/withdraw/request":    (5,   60, 3),    # withdrawal requests
    "/headers/ingest_signed": (20, 60, 10),  # signed header ingestion
    "/withdraw/register":   (10,  60, 5),    # withdrawal registration
}

# Paths that are never rate-limited
DEFAULT_EXEMPT_PREFIXES = (
    "/admin/",
    "/metrics",
    "/health",
    "/openapi.json",
)


# ---------------------------------------------------------------------------
# Token bucket implementation
# ---------------------------------------------------------------------------

class TokenBucket:
    """Single token bucket with atomic refill-and-consume."""

    __slots__ = ("capacity", "refill_rate", "tokens", "last_refill")

    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate       # tokens per second
        self.tokens = float(capacity)
        self.last_refill = time.monotonic()

    def consume(self) -> Tuple[bool, float]:
        """Try to consume one token.

        Returns:
            (allowed, retry_after)  -- retry_after is 0.0 when allowed.
        """
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True, 0.0

        deficit = 1.0 - self.tokens
        retry_after = deficit / self.refill_rate
        return False, retry_after


# ---------------------------------------------------------------------------
# Storage backends
# ---------------------------------------------------------------------------

class InMemoryStore:
    """Thread-safe in-memory bucket store with periodic eviction."""

    def __init__(self, max_entries: int = 50_000, evict_after: float = 600.0):
        self._buckets: Dict[str, TokenBucket] = {}
        self._lock = threading.Lock()
        self._max_entries = max_entries
        self._evict_after = evict_after
        self._last_eviction = time.monotonic()

    def consume(self, key: str, capacity: int, refill_rate: float) -> Tuple[bool, float]:
        with self._lock:
            self._maybe_evict()
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = TokenBucket(capacity, refill_rate)
                self._buckets[key] = bucket
            return bucket.consume()

    def _maybe_evict(self):
        now = time.monotonic()
        if now - self._last_eviction < 60.0:
            return
        self._last_eviction = now
        if len(self._buckets) <= self._max_entries:
            return
        # Evict buckets that have been idle longer than evict_after
        cutoff = now - self._evict_after
        stale = [k for k, b in self._buckets.items() if b.last_refill < cutoff]
        for k in stale:
            del self._buckets[k]
        logger.debug("Rate-limiter evicted %d stale buckets", len(stale))


class RedisStore:
    """Redis-backed token bucket using a Lua script for atomic operations.

    Falls back to InMemoryStore on connection errors so the node never
    hard-fails on a Redis outage.
    """

    # Atomic Lua script: refill tokens, try to consume, return result
    _LUA_SCRIPT = """
    local key       = KEYS[1]
    local capacity  = tonumber(ARGV[1])
    local refill    = tonumber(ARGV[2])
    local now       = tonumber(ARGV[3])
    local ttl       = tonumber(ARGV[4])

    local data = redis.call('HMGET', key, 'tokens', 'ts')
    local tokens = tonumber(data[1])
    local last   = tonumber(data[2])

    if tokens == nil then
        tokens = capacity
        last   = now
    end

    local elapsed = math.max(0, now - last)
    tokens = math.min(capacity, tokens + elapsed * refill)

    local allowed = 0
    local retry   = 0

    if tokens >= 1 then
        tokens  = tokens - 1
        allowed = 1
    else
        retry = (1 - tokens) / refill
    end

    redis.call('HMSET', key, 'tokens', tostring(tokens), 'ts', tostring(now))
    redis.call('EXPIRE', key, ttl)

    return {allowed, tostring(retry)}
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0",
                 key_prefix: str = "rc:rl:", ttl: int = 600):
        self._prefix = key_prefix
        self._ttl = ttl
        self._fallback = InMemoryStore()
        self._redis = None
        self._script_sha: Optional[str] = None
        self._available = False

        try:
            import redis as _redis
            self._redis = _redis.Redis.from_url(redis_url, decode_responses=True,
                                                  socket_connect_timeout=2,
                                                  socket_timeout=1)
            self._redis.ping()
            self._script_sha = self._redis.script_load(self._LUA_SCRIPT)
            self._available = True
            logger.info("Rate-limiter connected to Redis at %s", redis_url)
        except Exception as exc:
            logger.warning("Rate-limiter Redis unavailable (%s) -- using in-memory fallback", exc)
            self._available = False

    @property
    def is_redis_active(self) -> bool:
        return self._available

    def consume(self, key: str, capacity: int, refill_rate: float) -> Tuple[bool, float]:
        if not self._available:
            return self._fallback.consume(key, capacity, refill_rate)

        full_key = f"{self._prefix}{key}"
        try:
            result = self._redis.evalsha(
                self._script_sha, 1, full_key,
                str(capacity), str(refill_rate),
                str(time.time()), str(self._ttl),
            )
            allowed = int(result[0]) == 1
            retry_after = float(result[1])
            return allowed, retry_after
        except Exception as exc:
            logger.warning("Redis rate-limit call failed (%s) -- falling back to in-memory", exc)
            self._available = False
            return self._fallback.consume(key, capacity, refill_rate)


# ---------------------------------------------------------------------------
# Flask middleware
# ---------------------------------------------------------------------------

class RateLimiter:
    """Flask extension that applies per-IP token-bucket rate limiting."""

    def __init__(self, app: Optional[Flask] = None, **kwargs):
        self.store = None
        self.default_rate: int = DEFAULT_RATE
        self.default_window: int = DEFAULT_WINDOW
        self.default_burst: int = DEFAULT_BURST
        self.endpoint_limits: Dict[str, Tuple[int, int, int]] = dict(DEFAULT_ENDPOINT_LIMITS)
        self.exempt_prefixes: tuple = DEFAULT_EXEMPT_PREFIXES
        self.enabled: bool = True

        if app is not None:
            self.init_app(app, **kwargs)

    def init_app(self, app: Flask, **kwargs):
        """Attach the rate limiter to a Flask app.

        Config keys (also settable via kwargs):
            RATELIMIT_ENABLED          bool   (default True)
            RATELIMIT_DEFAULT_RATE     int    requests per window
            RATELIMIT_DEFAULT_WINDOW   int    window in seconds
            RATELIMIT_DEFAULT_BURST    int    max burst
            RATELIMIT_REDIS_URL        str    Redis connection URL
            RATELIMIT_ENDPOINT_LIMITS  dict   endpoint prefix -> (rate, window, burst)
            RATELIMIT_EXEMPT_PREFIXES  tuple  prefixes to skip
        """
        cfg = app.config

        self.enabled = kwargs.get("enabled",
                                  cfg.get("RATELIMIT_ENABLED", True))
        if not self.enabled:
            logger.info("Rate limiter disabled via configuration")
            return

        self.default_rate = kwargs.get("default_rate",
                                       cfg.get("RATELIMIT_DEFAULT_RATE", DEFAULT_RATE))
        self.default_window = kwargs.get("default_window",
                                         cfg.get("RATELIMIT_DEFAULT_WINDOW", DEFAULT_WINDOW))
        self.default_burst = kwargs.get("default_burst",
                                        cfg.get("RATELIMIT_DEFAULT_BURST", DEFAULT_BURST))

        extra_limits = kwargs.get("endpoint_limits",
                                  cfg.get("RATELIMIT_ENDPOINT_LIMITS"))
        if extra_limits:
            self.endpoint_limits.update(extra_limits)

        exempt = kwargs.get("exempt_prefixes",
                            cfg.get("RATELIMIT_EXEMPT_PREFIXES"))
        if exempt is not None:
            self.exempt_prefixes = tuple(exempt)

        # Initialise storage backend
        redis_url = kwargs.get("redis_url",
                               cfg.get("RATELIMIT_REDIS_URL"))
        if redis_url:
            self.store = RedisStore(redis_url=redis_url)
        else:
            # Try default localhost Redis, fall back to in-memory
            store = RedisStore()
            if store.is_redis_active:
                self.store = store
            else:
                self.store = InMemoryStore()
                logger.info("Rate limiter using in-memory storage")

        # Register before_request hook
        app.before_request(self._check_rate_limit)

        logger.info("Rate limiter initialised  (default %d req / %ds, burst %d)",
                     self.default_rate, self.default_window, self.default_burst)

    # ---- internal ---------------------------------------------------------

    def _resolve_client_ip(self) -> str:
        """Extract client IP, respecting X-Forwarded-For behind a reverse proxy."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # First entry is the original client
            return forwarded.split(",")[0].strip()
        return request.remote_addr or "127.0.0.1"

    def _match_endpoint(self, path: str) -> Tuple[int, int, int]:
        """Return (rate, window, burst) for the given request path."""
        for prefix, limits in self.endpoint_limits.items():
            if path.startswith(prefix):
                return limits
        return self.default_rate, self.default_window, self.default_burst

    def _check_rate_limit(self):
        """Flask before_request hook."""
        if not self.enabled:
            return None

        path = request.path

        # Skip exempt paths
        for prefix in self.exempt_prefixes:
            if path.startswith(prefix):
                return None

        client_ip = self._resolve_client_ip()
        rate, window, burst = self._match_endpoint(path)
        refill_rate = rate / window  # tokens per second

        # Build a bucket key scoped to IP + endpoint group
        endpoint_group = path
        for prefix in self.endpoint_limits:
            if path.startswith(prefix):
                endpoint_group = prefix
                break
        bucket_key = f"{client_ip}:{endpoint_group}"

        allowed, retry_after = self.store.consume(bucket_key, burst, refill_rate)

        if allowed:
            # Attach rate info to g for optional use by endpoints
            g.rate_limit_remaining = True
            return None

        # 429 Too Many Requests
        retry_after_int = max(1, int(retry_after + 0.5))
        response = jsonify({
            "ok": False,
            "error": "rate_limited",
            "message": f"Too many requests. Retry after {retry_after_int}s.",
            "retry_after": retry_after_int,
        })
        response.status_code = 429
        response.headers["Retry-After"] = str(retry_after_int)
        response.headers["X-RateLimit-Limit"] = str(rate)
        response.headers["X-RateLimit-Window"] = str(window)
        return response


# ---------------------------------------------------------------------------
# Convenience initialiser
# ---------------------------------------------------------------------------

def init_rate_limiter(app: Flask, **kwargs) -> RateLimiter:
    """One-liner to attach rate limiting to a Flask app.

    Example::

        from middleware import init_rate_limiter
        init_rate_limiter(app)

    Returns the RateLimiter instance for further customisation.
    """
    limiter = RateLimiter(app, **kwargs)
    return limiter
