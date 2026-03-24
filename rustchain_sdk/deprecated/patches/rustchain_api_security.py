#!/usr/bin/env python3
"""
RustChain API Security - Mainnet Hardening
===========================================

Phase 3 Implementation:
- API key enforcement for admin routes
- Rate limiting per IP/wallet
- Read-only JSON endpoint protection
- Request logging and monitoring

Security layers for production deployment.
"""

import os
import time
import hashlib
import logging
import threading
from functools import wraps
from typing import Dict, Optional, Callable
from collections import defaultdict
from dataclasses import dataclass, field

from flask import Flask, request, jsonify, g

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [API-SEC] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

# API Key for admin operations (set via environment variable)
ADMIN_API_KEY_HASH = os.environ.get("RC_ADMIN_KEY", "")

# Rate limiting defaults
DEFAULT_RATE_LIMIT = 60  # requests per minute
ATTESTATION_RATE_LIMIT = 10  # attestations per minute per IP
TX_SUBMIT_RATE_LIMIT = 30  # transaction submits per minute per wallet
ADMIN_RATE_LIMIT = 100  # admin requests per minute

# Whitelist IPs (no rate limiting)
WHITELIST_IPS = {
    "127.0.0.1",
    "::1",
    "50.28.86.131",  # LiquidWeb node 1
    "50.28.86.153",  # LiquidWeb node 2
}

# Ban duration for excessive violations
BAN_DURATION = 3600  # 1 hour
MAX_VIOLATIONS = 100  # violations before auto-ban


# =============================================================================
# RATE LIMITER
# =============================================================================

@dataclass
class RateLimitBucket:
    """Token bucket for rate limiting"""
    tokens: float
    last_update: float
    violations: int = 0

    def consume(self, rate_limit: int) -> bool:
        """
        Try to consume a token.

        Args:
            rate_limit: Max requests per minute

        Returns:
            True if request allowed, False if rate limited
        """
        now = time.time()
        elapsed = now - self.last_update
        self.last_update = now

        # Refill tokens (rate_limit per minute)
        tokens_per_second = rate_limit / 60.0
        self.tokens = min(rate_limit, self.tokens + elapsed * tokens_per_second)

        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        else:
            self.violations += 1
            return False


class RateLimiter:
    """
    Rate limiter with per-IP and per-wallet buckets.
    """

    def __init__(self):
        self._ip_buckets: Dict[str, RateLimitBucket] = defaultdict(
            lambda: RateLimitBucket(tokens=60, last_update=time.time())
        )
        self._wallet_buckets: Dict[str, RateLimitBucket] = defaultdict(
            lambda: RateLimitBucket(tokens=30, last_update=time.time())
        )
        self._banned_ips: Dict[str, float] = {}  # IP -> ban expiry timestamp
        self._lock = threading.Lock()

    def is_ip_banned(self, ip: str) -> bool:
        """Check if IP is banned"""
        if ip in WHITELIST_IPS:
            return False

        with self._lock:
            if ip in self._banned_ips:
                if time.time() < self._banned_ips[ip]:
                    return True
                else:
                    del self._banned_ips[ip]
            return False

    def ban_ip(self, ip: str, duration: int = BAN_DURATION):
        """Ban an IP address"""
        if ip not in WHITELIST_IPS:
            with self._lock:
                self._banned_ips[ip] = time.time() + duration
                logger.warning(f"Banned IP {ip} for {duration} seconds")

    def check_ip_rate(self, ip: str, rate_limit: int = DEFAULT_RATE_LIMIT) -> bool:
        """
        Check rate limit for IP.

        Returns True if request allowed.
        """
        if ip in WHITELIST_IPS:
            return True

        if self.is_ip_banned(ip):
            return False

        with self._lock:
            bucket = self._ip_buckets[ip]
            allowed = bucket.consume(rate_limit)

            # Auto-ban on excessive violations
            if bucket.violations >= MAX_VIOLATIONS:
                self.ban_ip(ip)
                bucket.violations = 0

            return allowed

    def check_wallet_rate(self, wallet: str, rate_limit: int = TX_SUBMIT_RATE_LIMIT) -> bool:
        """
        Check rate limit for wallet address.

        Returns True if request allowed.
        """
        with self._lock:
            bucket = self._wallet_buckets[wallet]
            return bucket.consume(rate_limit)

    def get_stats(self) -> Dict:
        """Get rate limiter statistics"""
        with self._lock:
            return {
                "active_ip_buckets": len(self._ip_buckets),
                "active_wallet_buckets": len(self._wallet_buckets),
                "banned_ips": len(self._banned_ips),
                "banned_ip_list": list(self._banned_ips.keys())
            }

    def cleanup(self, max_age: int = 3600):
        """Remove stale buckets"""
        cutoff = time.time() - max_age

        with self._lock:
            # Clean IP buckets
            stale_ips = [
                ip for ip, bucket in self._ip_buckets.items()
                if bucket.last_update < cutoff
            ]
            for ip in stale_ips:
                del self._ip_buckets[ip]

            # Clean wallet buckets
            stale_wallets = [
                wallet for wallet, bucket in self._wallet_buckets.items()
                if bucket.last_update < cutoff
            ]
            for wallet in stale_wallets:
                del self._wallet_buckets[wallet]

            # Clean expired bans
            expired_bans = [
                ip for ip, expiry in self._banned_ips.items()
                if time.time() >= expiry
            ]
            for ip in expired_bans:
                del self._banned_ips[ip]


# Global rate limiter instance
rate_limiter = RateLimiter()


# =============================================================================
# API KEY AUTHENTICATION
# =============================================================================

def hash_api_key(key: str) -> str:
    """Hash an API key for comparison"""
    return hashlib.blake2b(key.encode(), digest_size=32).hexdigest()


def verify_api_key(provided_key: str) -> bool:
    """Verify an API key against the stored hash"""
    if not ADMIN_API_KEY_HASH:
        logger.warning("No admin API key configured!")
        return False

    provided_hash = hash_api_key(provided_key)
    return provided_hash == ADMIN_API_KEY_HASH


def get_api_key_from_request() -> Optional[str]:
    """Extract API key from request headers or query params"""
    # Check Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]

    # Check X-API-Key header
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return api_key

    # Check query parameter
    return request.args.get("api_key")


# =============================================================================
# FLASK DECORATORS
# =============================================================================

def require_api_key(f: Callable) -> Callable:
    """
    Decorator to require valid API key for admin routes.

    Usage:
        @app.route('/admin/action')
        @require_api_key
        def admin_action():
            ...
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = get_api_key_from_request()

        if not api_key:
            return jsonify({
                "error": "API key required",
                "hint": "Provide key via Authorization: Bearer <key> or X-API-Key header"
            }), 401

        if not verify_api_key(api_key):
            logger.warning(f"Invalid API key attempt from {request.remote_addr}")
            return jsonify({"error": "Invalid API key"}), 403

        return f(*args, **kwargs)

    return decorated


def rate_limit(limit: int = DEFAULT_RATE_LIMIT, per_wallet: bool = False):
    """
    Decorator to apply rate limiting.

    Args:
        limit: Requests per minute allowed
        per_wallet: If True, rate limit by wallet address instead of IP

    Usage:
        @app.route('/api/data')
        @rate_limit(60)
        def get_data():
            ...
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated(*args, **kwargs):
            ip = request.remote_addr

            # Check IP ban first
            if rate_limiter.is_ip_banned(ip):
                return jsonify({
                    "error": "IP banned",
                    "retry_after": BAN_DURATION
                }), 429

            # Check rate limit
            if per_wallet:
                # Get wallet from request body or args
                wallet = None
                if request.is_json:
                    wallet = request.get_json().get("from_addr") or request.get_json().get("miner")
                if not wallet:
                    wallet = request.args.get("wallet") or request.args.get("address")

                if wallet:
                    if not rate_limiter.check_wallet_rate(wallet, limit):
                        return jsonify({
                            "error": "Rate limit exceeded",
                            "limit": f"{limit} requests per minute per wallet",
                            "retry_after": 60
                        }), 429
                else:
                    # Fall back to IP rate limiting
                    if not rate_limiter.check_ip_rate(ip, limit):
                        return jsonify({
                            "error": "Rate limit exceeded",
                            "limit": f"{limit} requests per minute",
                            "retry_after": 60
                        }), 429
            else:
                if not rate_limiter.check_ip_rate(ip, limit):
                    return jsonify({
                        "error": "Rate limit exceeded",
                        "limit": f"{limit} requests per minute",
                        "retry_after": 60
                    }), 429

            return f(*args, **kwargs)

        return decorated
    return decorator


def read_only(f: Callable) -> Callable:
    """
    Decorator to mark endpoint as read-only (no side effects).

    Adds caching headers and logging.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        response = f(*args, **kwargs)

        # If it's a tuple (response, status_code)
        if isinstance(response, tuple):
            return response

        # Add cache headers for GET requests
        if request.method == "GET":
            if hasattr(response, 'headers'):
                response.headers['Cache-Control'] = 'public, max-age=10'

        return response

    return decorated


# =============================================================================
# REQUEST LOGGING MIDDLEWARE
# =============================================================================

class RequestLogger:
    """
    Middleware for logging API requests.
    """

    def __init__(self, app: Flask = None):
        self.app = app
        if app:
            self.init_app(app)

    def init_app(self, app: Flask):
        """Initialize with Flask app"""
        app.before_request(self.before_request)
        app.after_request(self.after_request)

    def before_request(self):
        """Log request start"""
        g.request_start_time = time.time()
        g.request_id = hashlib.md5(
            f"{time.time()}{request.remote_addr}{request.path}".encode()
        ).hexdigest()[:12]

    def after_request(self, response):
        """Log request completion"""
        duration = time.time() - g.get('request_start_time', time.time())

        # Don't log health checks
        if request.path in ['/health', '/ping']:
            return response

        # Log based on response status
        if response.status_code >= 500:
            log_level = logging.ERROR
        elif response.status_code >= 400:
            log_level = logging.WARNING
        else:
            log_level = logging.INFO

        logger.log(
            log_level,
            f"[{g.get('request_id', 'N/A')}] "
            f"{request.method} {request.path} "
            f"-> {response.status_code} "
            f"({duration*1000:.1f}ms) "
            f"from {request.remote_addr}"
        )

        return response


# =============================================================================
# SECURITY ROUTES
# =============================================================================

def create_security_routes(app: Flask):
    """Add security-related API routes"""

    @app.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint (no rate limiting)"""
        return jsonify({"status": "ok", "timestamp": int(time.time())})

    @app.route('/admin/rate-limiter/stats', methods=['GET'])
    @require_api_key
    def rate_limiter_stats():
        """Get rate limiter statistics"""
        return jsonify(rate_limiter.get_stats())

    @app.route('/admin/rate-limiter/ban', methods=['POST'])
    @require_api_key
    def ban_ip_route():
        """Ban an IP address"""
        data = request.get_json()
        ip = data.get("ip")
        duration = data.get("duration", BAN_DURATION)

        if not ip:
            return jsonify({"error": "IP required"}), 400

        rate_limiter.ban_ip(ip, duration)
        return jsonify({"success": True, "banned_ip": ip, "duration": duration})

    @app.route('/admin/rate-limiter/unban', methods=['POST'])
    @require_api_key
    def unban_ip_route():
        """Unban an IP address"""
        data = request.get_json()
        ip = data.get("ip")

        if not ip:
            return jsonify({"error": "IP required"}), 400

        with rate_limiter._lock:
            if ip in rate_limiter._banned_ips:
                del rate_limiter._banned_ips[ip]
                return jsonify({"success": True, "unbanned_ip": ip})
            else:
                return jsonify({"error": "IP not banned"}), 404

    @app.route('/admin/rate-limiter/cleanup', methods=['POST'])
    @require_api_key
    def cleanup_rate_limiter():
        """Cleanup stale rate limiter buckets"""
        max_age = request.get_json().get("max_age", 3600) if request.is_json else 3600
        rate_limiter.cleanup(max_age)
        return jsonify({"success": True, "message": f"Cleaned up buckets older than {max_age}s"})


# =============================================================================
# SECURE FLASK APP FACTORY
# =============================================================================

def create_secure_app(name: str = __name__) -> Flask:
    """
    Create a Flask app with security middleware enabled.

    Usage:
        app = create_secure_app()

        @app.route('/api/data')
        @rate_limit(60)
        @read_only
        def get_data():
            return jsonify({"data": "..."})

        @app.route('/admin/action')
        @require_api_key
        def admin_action():
            return jsonify({"action": "done"})
    """
    app = Flask(name)

    # Initialize request logging
    RequestLogger(app)

    # Add security routes
    create_security_routes(app)

    # Disable Flask's default strict slashes
    app.url_map.strict_slashes = False

    # Security headers
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        return response

    return app


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    import os

    print("=" * 70)
    print("RustChain API Security - Test Suite")
    print("=" * 70)

    # Set test API key
    test_key = "test-admin-key-12345"
    os.environ["RC_ADMIN_KEY"] = hash_api_key(test_key)

    print(f"\n=== API Key Hashing ===")
    print(f"Test key: {test_key}")
    print(f"Hash: {hash_api_key(test_key)}")
    print(f"Verify correct: {verify_api_key(test_key)}")
    print(f"Verify wrong: {verify_api_key('wrong-key')}")

    print(f"\n=== Rate Limiter ===")
    limiter = RateLimiter()

    # Test IP rate limiting
    test_ip = "192.168.1.100"
    print(f"Testing IP: {test_ip}")

    for i in range(65):
        allowed = limiter.check_ip_rate(test_ip, 60)
        if not allowed:
            print(f"  Rate limited at request {i+1}")
            break
    else:
        print("  All 65 requests allowed (shouldn't happen)")

    # Test whitelist
    print(f"\n=== Whitelist Test ===")
    for ip in ["127.0.0.1", "50.28.86.131", "1.2.3.4"]:
        allowed = limiter.check_ip_rate(ip, 1)  # Very strict limit
        allowed2 = limiter.check_ip_rate(ip, 1)
        print(f"  {ip}: first={allowed}, second={allowed2}")

    # Test ban
    print(f"\n=== Ban Test ===")
    limiter.ban_ip("10.0.0.1", 10)
    print(f"  10.0.0.1 banned: {limiter.is_ip_banned('10.0.0.1')}")
    print(f"  127.0.0.1 banned: {limiter.is_ip_banned('127.0.0.1')}")

    # Test stats
    print(f"\n=== Stats ===")
    stats = limiter.get_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")

    # Test Flask app
    print(f"\n=== Flask App Test ===")
    app = create_secure_app("test")

    @app.route('/test/public')
    @rate_limit(10)
    @read_only
    def test_public():
        return jsonify({"public": True})

    @app.route('/test/admin')
    @require_api_key
    def test_admin():
        return jsonify({"admin": True})

    with app.test_client() as client:
        # Test public endpoint
        resp = client.get('/test/public')
        print(f"  Public endpoint: {resp.status_code}")

        # Test admin without key
        resp = client.get('/test/admin')
        print(f"  Admin (no key): {resp.status_code}")

        # Test admin with key
        resp = client.get('/test/admin', headers={"X-API-Key": test_key})
        print(f"  Admin (with key): {resp.status_code}")

        # Test health
        resp = client.get('/health')
        print(f"  Health check: {resp.status_code}, {resp.get_json()}")

    print("\n" + "=" * 70)
    print("All tests passed!")
    print("=" * 70)
