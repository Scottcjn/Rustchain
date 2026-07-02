#!/usr/bin/env python3
"""
RustChain Testnet Faucet Service

A production-ready Flask-based faucet service for dispensing test RTC tokens.
Features:
- Configurable rate limiting (IP, wallet, or hybrid)
- Request validation with blocklist/allowlist support
- SQLite/Redis backend for distributed deployments
- REST API with HTML UI
- Comprehensive logging and monitoring

Usage:
    python faucet_service.py [--config faucet_config.yaml]

API Endpoints:
    GET  /faucet          - Web UI
    POST /faucet/drip     - Request tokens
    GET  /faucet/status   - Faucet status
    GET  /health          - Health check
    GET  /metrics         - Prometheus metrics (if enabled)
"""

import os
import re
import sys
import json
import math
import hashlib
import secrets
import requests
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from contextlib import contextmanager

import yaml
from Crypto.Hash import keccak
from flask import Flask, request, jsonify, render_template_string, g
from flask_cors import CORS
from functools import wraps
import time

# Try to import redis, make it optional
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# =============================================================================
# Configuration
# =============================================================================

DEFAULT_CONFIG = {
    'server': {
        'host': '0.0.0.0',
        'port': 8090,
        'debug': False,
        'base_path': '/faucet'
    },
    'rate_limit': {
        'enabled': True,
        'method': 'ip',
        'window_seconds': 86400,
        'max_amount': 0.5,
        'max_requests': 1,
        'redis': {
            'enabled': False,
            'host': 'localhost',
            'port': 6379,
            'db': 0,
            'password': None,
            'key_prefix': 'rustchain_faucet:'
        }
    },
    'validation': {
        'required_prefix': ['0x', 'RTC'],
        'min_length': 10,
        'max_length': 66,
        'require_checksum': False,
        'blocklist': [],
        'allowlist': []
    },
    'database': {
        'path': 'faucet.db',
        'pool_size': 5,
        'echo': False
    },
    'distribution': {
        'amount': 0.5,
        'min_balance': 10.0,
        'mock_mode': True,
        'node_rpc': None,
        'wallet_key': None
    },
    'event_codes': {
        'enabled': False,
        'admin_token': None,
        'default_amount': 0.5,
        'max_amount': 1.0,
        'max_batch_size': 500,
        'code_prefix': 'EVENT',
        'pending_claim_ttl_seconds': 300
    },
    'logging': {
        'level': 'INFO',
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        'file': 'faucet.log',
        'max_size_mb': 10,
        'backup_count': 5
    },
    'security': {
        'cors_origins': ['*'],
        'csrf_enabled': False,
        'request_timeout': 30,
        'max_body_size': 1048576
    },
    'monitoring': {
        'metrics_enabled': False,
        'metrics_path': '/metrics',
        'health_enabled': True,
        'health_path': '/health',
        'statsd': {
            'enabled': False,
            'host': 'localhost',
            'port': 8125,
            'prefix': 'rustchain.faucet'
        }
    }
}


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration from YAML file, merging with defaults."""
    config = _deep_copy(DEFAULT_CONFIG)
    
    if config_path and os.path.exists(config_path):
        with open(config_path, 'r') as f:
            file_config = yaml.safe_load(f)
            if file_config:
                _merge_config(config, file_config)
    
    return config


def _deep_copy(obj: Dict) -> Dict:
    """Create a deep copy of a dictionary."""
    import copy
    return copy.deepcopy(obj)


def _merge_config(base: Dict, override: Dict) -> None:
    """Recursively merge override config into base config."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _merge_config(base[key], value)
        else:
            base[key] = value


# =============================================================================
# Logging Setup
# =============================================================================

def setup_logging(config: Dict[str, Any]) -> logging.Logger:
    """Configure logging based on configuration."""
    log_config = config.get('logging', {})
    
    # Create logger
    logger = logging.getLogger('rustchain_faucet')
    logger.setLevel(getattr(logging, log_config.get('level', 'INFO')))
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_config.get('format')))
    logger.addHandler(console_handler)
    
    # File handler (optional)
    log_file = log_config.get('file')
    if log_file:
        from logging.handlers import RotatingFileHandler
        max_bytes = log_config.get('max_size_mb', 10) * 1024 * 1024
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=log_config.get('backup_count', 5)
        )
        file_handler.setFormatter(logging.Formatter(log_config.get('format')))
        logger.addHandler(file_handler)
    
    return logger


# =============================================================================
# Rate Limiter
# =============================================================================

class RateLimiter:
    """Rate limiting implementation with IP, wallet, or hybrid methods."""
    
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.use_redis = config.get('rate_limit', {}).get('redis', {}).get('enabled', False)
        
        if self.use_redis and REDIS_AVAILABLE:
            redis_config = config['rate_limit']['redis']
            self.redis_client = redis.Redis(
                host=redis_config['host'],
                port=redis_config['port'],
                db=redis_config['db'],
                password=redis_config['password'],
                decode_responses=True
            )
            self.logger.info("Redis rate limiting enabled")
        else:
            self.redis_client = None
            self.logger.info("Using in-memory/SQLite rate limiting")
    
    def _get_key(self, identifier: str, id_type: str) -> str:
        """Generate rate limit key."""
        prefix = self.config['rate_limit']['redis'].get('key_prefix', 'rustchain_faucet:')
        window = self.config['rate_limit']['window_seconds']
        # Create time-based window key
        current_window = int(time.time()) // window
        return f"{prefix}{id_type}:{identifier}:{current_window}"
    
    def check_rate_limit(self, ip_address: str, wallet: str) -> Tuple[bool, Optional[str]]:
        """
        Check if request is within rate limits.
        
        Returns:
            Tuple of (allowed: bool, next_available: Optional[str])
        """
        if not self.config.get('rate_limit', {}).get('enabled', True):
            return True, None
        
        method = self.config['rate_limit'].get('method', 'ip')
        
        # Determine identifier based on method
        if method == 'ip':
            identifier = ip_address
        elif method == 'wallet':
            identifier = wallet
        elif method == 'hybrid':
            # Use both IP and wallet
            identifier = f"{ip_address}:{wallet}"
        else:
            identifier = ip_address
        
        if self.redis_client and REDIS_AVAILABLE:
            return self._check_redis(identifier)
        else:
            return self._check_sqlite(identifier, ip_address, wallet)
    
    def _check_redis(self, identifier: str) -> Tuple[bool, Optional[str]]:
        """Check rate limit using Redis."""
        key = self._get_key(identifier, 'rl')
        count_key = self._get_key(identifier, 'count')
        
        current_count = self.redis_client.get(count_key)
        current_count = int(current_count) if current_count else 0
        
        max_requests = self.config['rate_limit'].get('max_requests', 1)
        window_seconds = self.config['rate_limit']['window_seconds']
        
        if current_count >= max_requests:
            ttl = self.redis_client.ttl(key)
            next_available = datetime.now() + timedelta(seconds=max(0, ttl))
            return False, next_available.isoformat()
        
        return True, None
    
    def _check_sqlite(self, identifier: str, ip_address: str, wallet: str) -> Tuple[bool, Optional[str]]:
        """Check rate limit using SQLite."""
        conn = sqlite3.connect(self.config['database']['path'])
        c = conn.cursor()
        
        window_seconds = self.config['rate_limit']['window_seconds']
        cutoff = datetime.now() - timedelta(seconds=window_seconds)
        
        c.execute('''
            SELECT COUNT(*) FROM drip_requests
            WHERE (ip_address = ? OR wallet = ?)
            AND timestamp > ?
        ''', (ip_address, wallet, cutoff.isoformat()))
        
        count = c.fetchone()[0]
        max_requests = self.config['rate_limit'].get('max_requests', 1)
        
        conn.close()
        
        if count >= max_requests:
            # Calculate next available time.
            conn = sqlite3.connect(self.config['database']['path'])
            try:
                c = conn.cursor()
                c.execute('''
                    SELECT MAX(timestamp) FROM drip_requests
                    WHERE (ip_address = ? OR wallet = ?)
                    AND timestamp > ?
                ''', (ip_address, wallet, cutoff.isoformat()))
                last_request = c.fetchone()[0]
            finally:
                conn.close()

            if last_request:
                last_time = datetime.fromisoformat(last_request)
                next_available = last_time + timedelta(seconds=window_seconds)
                return False, next_available.isoformat()
        
        return True, None
    
    def record_request(self, identifier: str, ip_address: str, wallet: str, amount: float) -> None:
        """Record a rate-limited request."""
        if self.redis_client and REDIS_AVAILABLE:
            self._record_redis(identifier)
        else:
            self._record_sqlite(ip_address, wallet, amount)

    def record_request_if_allowed(
        self,
        identifier: str,
        ip_address: str,
        wallet: str,
        amount: float,
    ) -> Tuple[bool, Optional[str]]:
        """Atomically check the active rate limit and record the drip."""
        if not self.config.get('rate_limit', {}).get('enabled', True):
            self.record_request(identifier, ip_address, wallet, amount)
            return True, None

        if self.redis_client and REDIS_AVAILABLE:
            return self._record_redis_if_allowed(identifier)

        return self._record_sqlite_if_allowed(ip_address, wallet, amount)

    def _record_redis_if_allowed(self, identifier: str) -> Tuple[bool, Optional[str]]:
        """Check and record the Redis rate limit in one atomic script."""
        key = self._get_key(identifier, 'rl')
        count_key = self._get_key(identifier, 'count')
        max_requests = self.config['rate_limit'].get('max_requests', 1)
        window_seconds = self.config['rate_limit']['window_seconds']
        now_iso = datetime.now().isoformat()

        result = self.redis_client.eval(
            """
            local count_key = KEYS[1]
            local marker_key = KEYS[2]
            local max_requests = tonumber(ARGV[1])
            local window_seconds = tonumber(ARGV[2])
            local now_iso = ARGV[3]

            local current = tonumber(redis.call('GET', count_key) or '0')
            if current >= max_requests then
                local ttl = redis.call('TTL', marker_key)
                if ttl < 0 then
                    ttl = redis.call('TTL', count_key)
                end
                return {0, ttl}
            end

            local new_count = redis.call('INCR', count_key)
            if new_count == 1 or redis.call('TTL', count_key) < 0 then
                redis.call('EXPIRE', count_key, window_seconds)
            end
            redis.call('SET', marker_key, now_iso, 'EX', window_seconds)
            return {1, redis.call('TTL', marker_key)}
            """,
            2,
            count_key,
            key,
            max_requests,
            window_seconds,
            now_iso,
        )

        allowed = int(result[0]) == 1
        if allowed:
            return True, None

        ttl = int(result[1]) if len(result) > 1 and result[1] is not None else 0
        next_available = datetime.now() + timedelta(seconds=max(0, ttl))
        return False, next_available.isoformat()
    
    def _record_redis(self, identifier: str) -> None:
        """Record request in Redis."""
        key = self._get_key(identifier, 'rl')
        count_key = self._get_key(identifier, 'count')
        window_seconds = self.config['rate_limit']['window_seconds']
        
        pipe = self.redis_client.pipeline()
        pipe.incr(count_key)
        pipe.expire(count_key, window_seconds)
        pipe.set(key, datetime.now().isoformat(), ex=window_seconds)
        pipe.execute()
    
    def _record_sqlite(self, ip_address: str, wallet: str, amount: float) -> None:
        """Record request in SQLite."""
        conn = sqlite3.connect(self.config['database']['path'])
        c = conn.cursor()
        c.execute('''
            INSERT INTO drip_requests (wallet, ip_address, amount, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (wallet, ip_address, amount, datetime.now().isoformat()))
        conn.commit()
        conn.close()

    def _record_sqlite_if_allowed(
        self,
        ip_address: str,
        wallet: str,
        amount: float,
    ) -> Tuple[bool, Optional[str]]:
        """Check and insert under one SQLite write transaction."""
        conn = sqlite3.connect(self.config['database']['path'], timeout=30)
        try:
            conn.isolation_level = None
            c = conn.cursor()
            c.execute('PRAGMA busy_timeout = 30000')
            c.execute('BEGIN IMMEDIATE')

            window_seconds = self.config['rate_limit']['window_seconds']
            cutoff = datetime.now() - timedelta(seconds=window_seconds)
            c.execute('''
                SELECT COUNT(*), MAX(timestamp) FROM drip_requests
                WHERE (ip_address = ? OR wallet = ?)
                AND timestamp > ?
            ''', (ip_address, wallet, cutoff.isoformat()))

            count, last_request = c.fetchone()
            max_requests = self.config['rate_limit'].get('max_requests', 1)
            if count >= max_requests:
                c.execute('ROLLBACK')
                if last_request:
                    last_time = datetime.fromisoformat(last_request)
                    next_available = last_time + timedelta(seconds=window_seconds)
                    return False, next_available.isoformat()
                return False, None

            c.execute('''
                INSERT INTO drip_requests (wallet, ip_address, amount, timestamp)
                VALUES (?, ?, ?, ?)
            ''', (wallet, ip_address, amount, datetime.now().isoformat()))
            c.execute('COMMIT')
            return True, None
        except Exception:
            try:
                conn.execute('ROLLBACK')
            except sqlite3.OperationalError:
                pass
            raise
        finally:
            conn.close()


# =============================================================================
# Validator
# =============================================================================

RTC_WALLET_RE = re.compile(r'^RTC[0-9a-fA-F]{40}$')


class FaucetValidator:
    """Request validation with blocklist/allowlist support."""

    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.validation_config = config.get('validation', {})
        self.blocklist = set(self.validation_config.get('blocklist', []))
        self.allowlist = set(self.validation_config.get('allowlist', []))
    
    def validate_wallet(self, wallet: str) -> Tuple[bool, Optional[str]]:
        """
        Validate wallet address.
        
        Returns:
            Tuple of (valid: bool, error_message: Optional[str])
        """
        if not wallet:
            return False, "Wallet address is required"
        
        wallet = wallet.strip()
        
        # Check prefix
        required_prefix = self.validation_config.get('required_prefix', ['0x', 'RTC'])
        if isinstance(required_prefix, str):
            accepted_prefixes = [required_prefix]
        else:
            accepted_prefixes = list(required_prefix or [])

        if accepted_prefixes and not any(wallet.startswith(prefix) for prefix in accepted_prefixes):
            joined_prefixes = "', '".join(accepted_prefixes)
            return False, f"Wallet must start with one of '{joined_prefixes}'"
        
        # Check length
        min_len = self.validation_config.get('min_length', 10)
        max_len = self.validation_config.get('max_length', 66)
        
        if len(wallet) < min_len:
            return False, f"Wallet address too short (min {min_len} characters)"
        
        if len(wallet) > max_len:
            return False, f"Wallet address too long (max {max_len} characters)"

        # Tightened format validation for native RTC wallets: RTC + 40 hex chars.
        # Mirrors the legacy faucet fix in commit 541c784 so malformed values like
        # "RTCzzzzzzzzzz" or "RTC1234567890" cannot pass as distinct wallet identities.
        if wallet.startswith('RTC') and not RTC_WALLET_RE.fullmatch(wallet):
            return False, "Invalid RTC wallet format (expected 'RTC' + 40 hex chars)"

        # Check blocklist
        if wallet.lower() in self.blocklist:
            return False, "Wallet address is blocklisted"
        
        # Check allowlist (if configured, only allowlisted addresses can request)
        if self.allowlist and wallet.lower() not in self.allowlist:
            return False, "Wallet address is not in allowlist"
        
        # Check checksum (if enabled)
        if self.validation_config.get('require_checksum', False):
            if not self._validate_checksum(wallet):
                return False, "Invalid wallet checksum"
        
        return True, None
    
    def _validate_checksum(self, wallet: str) -> bool:
        """Validate Ethereum-style checksum (EIP-55)."""
        if not wallet.startswith('0x'):
            return False
        
        address = wallet[2:]
        if not all(c in '0123456789abcdefABCDEF' for c in address):
            return False
        
        # EIP-55 uses the original Keccak-256, not FIPS SHA3-256.
        hasher = keccak.new(digest_bits=256)
        hasher.update(address.lower().encode())
        hash_lower = hasher.hexdigest()
        for i, c in enumerate(address):
            if c in '0123456789':
                continue
            hash_char = hash_lower[i]
            if int(hash_char, 16) >= 8 and c.lower() == c:
                return False
            if int(hash_char, 16) < 8 and c.upper() == c:
                return False
        
        return True


# =============================================================================
# Database
# =============================================================================

def init_database(db_path: str) -> None:
    """Initialize SQLite database with required tables."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS drip_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet TEXT NOT NULL,
            ip_address TEXT NOT NULL,
            amount REAL NOT NULL,
            timestamp TEXT NOT NULL,
            status TEXT DEFAULT 'completed',
            tx_hash TEXT
        )
    ''')

    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_drip_requests_wallet_ts
        ON drip_requests(wallet, timestamp)
    ''')

    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_drip_requests_ip_ts
        ON drip_requests(ip_address, timestamp)
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS event_claim_codes (
            code TEXT PRIMARY KEY,
            amount REAL NOT NULL,
            batch_id TEXT,
            metadata_json TEXT,
            expires_at TEXT,
            created_at TEXT NOT NULL,
            created_by TEXT,
            claimed_at TEXT,
            claimed_wallet TEXT,
            claimed_ip TEXT,
            tx_hash TEXT
        )
    ''')

    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_event_claim_codes_expires_at
        ON event_claim_codes(expires_at)
    ''')

    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_event_claim_codes_claimed_wallet
        ON event_claim_codes(claimed_wallet)
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS event_claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            wallet TEXT NOT NULL,
            ip_address TEXT NOT NULL,
            amount REAL NOT NULL,
            batch_id TEXT,
            claimed_at TEXT NOT NULL,
            tx_hash TEXT,
            status TEXT DEFAULT 'reserved',
            updated_at TEXT NOT NULL,
            FOREIGN KEY(code) REFERENCES event_claim_codes(code)
        )
    ''')

    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_event_claims_code
        ON event_claims(code)
    ''')

    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_event_claims_wallet_ts
        ON event_claims(wallet, claimed_at)
    ''')

    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_event_claims_ip_ts
        ON event_claims(ip_address, claimed_at)
    ''')
    
    conn.commit()
    conn.close()


# =============================================================================
# Faucet Service
# =============================================================================

def create_app(config: Dict[str, Any]) -> Flask:
    """Create and configure Flask application."""
    app = Flask(__name__)
    CORS(app, origins=config.get('security', {}).get('cors_origins', ['*']))
    
    # Setup logging
    logger = setup_logging(config)
    
    # Initialize components
    validator = FaucetValidator(config, logger)
    rate_limiter = RateLimiter(config, logger)
    
    # Initialize database
    db_path = config.get('database', {}).get('path', 'faucet.db')
    init_database(db_path)
    
    @app.before_request
    def before_request():
        """Check request size and prepare context."""
        max_size = config.get('security', {}).get('max_body_size', 1048576)
        if request.content_length and request.content_length > max_size:
            return jsonify({'ok': False, 'error': 'Request too large'}), 413
    
    @app.route(config['server'].get('base_path', '/faucet'))
    def index():
        """Serve the faucet web UI."""
        template_vars = get_template_vars(config)
        return render_template_string(HTML_TEMPLATE, **template_vars)
    
    @app.route(f"{config['server'].get('base_path', '/faucet')}/drip", methods=['POST'])
    def drip():
        """Handle faucet drip request."""
        try:
            data = request.get_json() or {}
            wallet = data.get('wallet', '').strip()
            amount = config.get('distribution', {}).get('amount', 0.5)
            
            # Validate wallet
            valid, error = validator.validate_wallet(wallet)
            if not valid:
                logger.warning(f"Invalid wallet request: {wallet} - {error}")
                return jsonify({'ok': False, 'error': error}), 400
            
            # Get client IP
            trust_proxy_headers = config.get('security', {}).get('trust_proxy_headers', False)
            ip_address = get_client_ip(request, trust_proxy_headers)
            
            # Check rate limit
            allowed, next_available = rate_limiter.check_rate_limit(ip_address, wallet)
            if not allowed:
                logger.info(f"Rate limit exceeded for {wallet} from {ip_address}")
                return jsonify({
                    'ok': False,
                    'error': 'Rate limit exceeded',
                    'next_available': next_available
                }), 429
            
            # Check faucet balance/minimum if not in mock mode
            dist_config = config.get('distribution', {})
            if not dist_config.get('mock_mode', True):
                # In real mode, we'd check actual node balance here
                # For now, simulate the check
                faucet_balance = dist_config.get('faucet_balance', 100.0)
                min_balance = dist_config.get('min_balance', 10.0)
                
                if faucet_balance < amount or faucet_balance < min_balance:
                    logger.error(f"Insufficient faucet balance: {faucet_balance}")
                    return jsonify({
                        'ok': False,
                        'error': 'Faucet temporarily unavailable'
                    }), 503
            
            # Record request atomically with rate limit enforcement.
            method = config['rate_limit'].get('method', 'ip')
            if method == 'ip':
                identifier = ip_address
            elif method == 'wallet':
                identifier = wallet
            elif method == 'hybrid':
                identifier = f"{ip_address}:{wallet}"
            else:
                identifier = ip_address

            recorded, next_available = rate_limiter.record_request_if_allowed(
                identifier,
                ip_address,
                wallet,
                amount,
            )
            if not recorded:
                logger.info(f"Rate limit exceeded for {wallet} from {ip_address} during commit")
                return jsonify({
                    'ok': False,
                    'error': 'Rate limit exceeded',
                    'next_available': next_available
                }), 429
            
            # Log successful request
            logger.info(f"Faucet drip: {amount} RTC to {wallet} from {ip_address}")
            
            # Return success
            return jsonify({
                'ok': True,
                'amount': amount,
                'wallet': wallet,
                'next_available': (datetime.now() + timedelta(
                    seconds=config['rate_limit']['window_seconds']
                )).isoformat()
            })
            
        except Exception as e:
            logger.exception(f"Faucet error: {e}")
            return jsonify({'ok': False, 'error': 'Internal server error'}), 500

    base_path = config['server'].get('base_path', '/faucet')

    @app.route(f'{base_path}/admin/event-codes', methods=['POST'])
    def create_event_codes():
        """Mint a batch of one-time faucet claim codes for an event organizer."""
        auth_error = _require_event_admin(config)
        if auth_error:
            return auth_error

        payload = request.get_json(silent=True) or {}
        event_config = config.get('event_codes', {})

        try:
            requested_count = int(payload.get('count', 0))
        except (TypeError, ValueError):
            return jsonify({'ok': False, 'error': 'count must be an integer'}), 400

        if requested_count <= 0:
            return jsonify({'ok': False, 'error': 'count must be greater than 0'}), 400

        max_batch_size = int(event_config.get('max_batch_size', 500))
        if requested_count > max_batch_size:
            return jsonify({
                'ok': False,
                'error': f'count exceeds max_batch_size ({max_batch_size})'
            }), 400

        amount = payload.get('amount', event_config.get('default_amount', 0.5))
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            return jsonify({'ok': False, 'error': 'amount must be numeric'}), 400

        if amount <= 0:
            return jsonify({'ok': False, 'error': 'amount must be greater than 0'}), 400

        max_amount = float(event_config.get('max_amount', amount))
        if amount > max_amount:
            return jsonify({
                'ok': False,
                'error': f'amount exceeds configured max_amount ({max_amount})'
            }), 400

        batch_id = str(payload.get('batch_id', '') or '').strip() or None
        code_prefix = str(payload.get('code_prefix', event_config.get('code_prefix', 'EVENT')) or 'EVENT').strip()
        created_by = request.headers.get('X-Event-Creator', 'admin').strip() or 'admin'

        expires_at = _parse_future_datetime(payload.get('expires_at'))
        expires_at_iso = expires_at.isoformat() if expires_at else None

        metadata = payload.get('metadata', {})
        if metadata is None:
            metadata = {}
        if not isinstance(metadata, dict):
            return jsonify({'ok': False, 'error': 'metadata must be a JSON object'}), 400

        db_path = config.get('database', {}).get('path', 'faucet.db')
        created_at = datetime.now().isoformat()
        generated = []

        conn = sqlite3.connect(db_path, timeout=30)
        try:
            c = conn.cursor()
            for _ in range(requested_count):
                code = _generate_event_code(code_prefix)
                metadata_json = json.dumps(metadata, sort_keys=True)
                c.execute('''
                    INSERT INTO event_claim_codes (
                        code, amount, batch_id, metadata_json, expires_at,
                        created_at, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    code,
                    amount,
                    batch_id,
                    metadata_json,
                    expires_at_iso,
                    created_at,
                    created_by,
                ))
                generated.append({
                    'code': code,
                    'amount': amount,
                    'batch_id': batch_id,
                    'expires_at': expires_at_iso,
                    'metadata': metadata,
                })
            conn.commit()
        finally:
            conn.close()

        logger.info(
            "Created %s event faucet codes batch_id=%s amount=%s creator=%s",
            requested_count,
            batch_id,
            amount,
            created_by,
        )

        return jsonify({
            'ok': True,
            'count': requested_count,
            'amount': amount,
            'batch_id': batch_id,
            'expires_at': expires_at_iso,
            'codes': generated,
        })

    @app.route(f'{base_path}/event-claim', methods=['POST'])
    def claim_event_code():
        """Redeem a one-time faucet claim code into an RTC faucet drip."""
        payload = request.get_json(silent=True) or {}
        code = str(payload.get('code', '') or '').strip()
        wallet = str(payload.get('wallet', '') or '').strip()

        if not code:
            return jsonify({'ok': False, 'error': 'Event claim code is required'}), 400

        valid_wallet, wallet_error = validator.validate_wallet(wallet)
        if not valid_wallet:
            return jsonify({'ok': False, 'error': wallet_error}), 400

        db_path = config.get('database', {}).get('path', 'faucet.db')
        trust_proxy_headers = config.get('security', {}).get('trust_proxy_headers', False)
        ip_address = get_client_ip(request, trust_proxy_headers)
        now = datetime.now()

        conn = sqlite3.connect(db_path, timeout=30)
        try:
            conn.isolation_level = None
            c = conn.cursor()
            c.execute('PRAGMA busy_timeout = 30000')
            c.execute('BEGIN IMMEDIATE')

            _release_stale_event_claim_reservation(c, code, now, config.get('event_codes', {}))

            c.execute('''
                SELECT code, amount, batch_id, metadata_json, expires_at,
                       created_at, claimed_at, claimed_wallet, tx_hash
                FROM event_claim_codes
                WHERE code = ?
            ''', (code,))
            row = c.fetchone()
            if not row:
                c.execute('ROLLBACK')
                return jsonify({'ok': False, 'error': 'Invalid event claim code'}), 404

            (
                stored_code,
                amount,
                batch_id,
                metadata_json,
                expires_at_raw,
                created_at,
                claimed_at,
                claimed_wallet,
                existing_tx_hash,
            ) = row

            if expires_at_raw:
                expires_at = datetime.fromisoformat(expires_at_raw)
                if expires_at <= now:
                    c.execute('ROLLBACK')
                    return jsonify({'ok': False, 'error': 'Event claim code has expired'}), 410

            if claimed_at is not None:
                c.execute('ROLLBACK')
                if claimed_wallet and claimed_wallet.lower() == wallet.lower():
                    return jsonify({
                        'ok': True,
                        'amount': float(amount),
                        'wallet': wallet,
                        'code': stored_code,
                        'tx_hash': existing_tx_hash,
                        'already_claimed': True,
                    })
                return jsonify({'ok': False, 'error': 'Event claim code already used'}), 409

            now_iso = now.isoformat()
            c.execute('''
                UPDATE event_claim_codes
                SET claimed_wallet = ?, claimed_ip = ?, claimed_at = ?
                WHERE code = ?
            ''', (wallet, ip_address, now_iso, stored_code))
            c.execute('''
                INSERT INTO event_claims (
                    code, wallet, ip_address, amount, batch_id,
                    claimed_at, tx_hash, status, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                stored_code,
                wallet,
                ip_address,
                amount,
                batch_id,
                now_iso,
                None,
                'reserved',
                now_iso,
            ))
            claim_id = c.lastrowid
            c.execute('COMMIT')
        except Exception:
            try:
                conn.execute('ROLLBACK')
            except sqlite3.OperationalError:
                pass
            raise
        finally:
            conn.close()

        tx_hash = None
        try:
            _mark_event_claim_transfer_started(db_path, claim_id)
            tx_hash = _perform_faucet_transfer(
                config,
                logger,
                wallet,
                float(amount),
                idempotency_key=_event_claim_idempotency_key(code),
                reason=f"event_claim:{code}",
            )
        except Exception as exc:
            try:
                _release_event_claim(db_path, code, claim_id, 'transfer_failed')
            except Exception as finalize_exc:
                logger.error(f"Event claim failure finalization failed for code={code}: {finalize_exc}")
            logger.error(f"Event claim transfer failed for code={code}: {exc}")
            return jsonify({'ok': False, 'error': 'Internal transfer error'}), 500

        try:
            _finalize_event_claim(db_path, code, claim_id, tx_hash, 'completed')
        except Exception as exc:
            logger.error(f"Event claim finalization failed for code={code}: {exc}")
            return jsonify({'ok': False, 'error': 'Internal transfer error'}), 500

        return jsonify({
            'ok': True,
            'amount': float(amount),
            'wallet': wallet,
            'code': code,
            'tx_hash': tx_hash
        })
    
    @app.route(f'{base_path}/status')
    def status():
        """Get faucet status and statistics."""
        db_path = config.get('database', {}).get('path', 'faucet.db')
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # Get total drips
        c.execute('SELECT COUNT(*) FROM drip_requests')
        total_drips = c.fetchone()[0]
        
        # Get total amount
        c.execute('SELECT COALESCE(SUM(amount), 0) FROM drip_requests')
        total_amount = c.fetchone()[0]
        
        # Get unique wallets
        c.execute('SELECT COUNT(DISTINCT wallet) FROM drip_requests')
        unique_wallets = c.fetchone()[0]
        
        # Get unique IPs
        c.execute('SELECT COUNT(DISTINCT ip_address) FROM drip_requests')
        unique_ips = c.fetchone()[0]
        
        # Get last 24h stats
        cutoff = datetime.now() - timedelta(hours=24)
        c.execute('''
            SELECT COUNT(*), COALESCE(SUM(amount), 0)
            FROM drip_requests WHERE timestamp > ?
        ''', (cutoff.isoformat(),))
        result = c.fetchone()
        drips_24h, amount_24h = result
        
        conn.close()
        
        return jsonify({
            'status': 'operational',
            'network': 'testnet',
            'mock_mode': config.get('distribution', {}).get('mock_mode', True),
            'statistics': {
                'total_drips': total_drips,
                'total_amount': total_amount,
                'unique_wallets': unique_wallets,
                'unique_ips': unique_ips,
                'drips_24h': drips_24h,
                'amount_24h': amount_24h
            },
            'rate_limit': {
                'max_amount': config.get('rate_limit', {}).get('max_amount', 0.5),
                'window_hours': config.get('rate_limit', {}).get('window_seconds', 86400) / 3600
            }
        })
    
    # Health check endpoint
    if config.get('monitoring', {}).get('health_enabled', True):
        health_path = config.get('monitoring', {}).get('health_path', '/health')
        
        @app.route(health_path)
        def health():
            """Health check endpoint."""
            return jsonify({
                'status': 'healthy',
                'timestamp': datetime.now().isoformat(),
                'version': '1.0.0'
            })
    
    # Metrics endpoint (Prometheus format)
    if config.get('monitoring', {}).get('metrics_enabled', False):
        metrics_path = config.get('monitoring', {}).get('metrics_path', '/metrics')
        
        @app.route(metrics_path)
        def metrics():
            """Prometheus metrics endpoint."""
            db_path = config.get('database', {}).get('path', 'faucet.db')
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            
            c.execute('SELECT COUNT(*) FROM drip_requests')
            total_drips = c.fetchone()[0]
            
            c.execute('SELECT COALESCE(SUM(amount), 0) FROM drip_requests')
            total_amount = c.fetchone()[0]
            
            conn.close()
            
            metrics_text = f'''# HELP faucet_drips_total Total number of drips
# TYPE faucet_drips_total counter
faucet_drips_total {total_drips}

# HELP faucet_amount_total Total amount distributed
# TYPE faucet_amount_total counter
faucet_amount_total {total_amount}

# HELP faucet_up Faucet service status
# TYPE faucet_up gauge
faucet_up 1
'''
            return metrics_text, 200, {'Content-Type': 'text/plain'}


def get_client_ip(request, trust_proxy_headers: bool = False) -> str:
    """Get client IP address, trusting proxy headers only when configured."""
    if trust_proxy_headers and request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    if trust_proxy_headers and request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    return request.remote_addr or '127.0.0.1'


def _require_event_admin(config: Dict) -> Optional[Tuple[Any, int]]:
    """Require an event faucet admin token before minting claim codes."""
    event_config = config.get('event_codes', {})
    if not event_config.get('enabled', False):
        return jsonify({'ok': False, 'error': 'Event codes disabled'}), 404

    expected = os.environ.get('FAUCET_EVENT_ADMIN_TOKEN') or event_config.get('admin_token')
    if not expected:
        return jsonify({'ok': False, 'error': 'Event code admin token not configured'}), 503

    supplied = request.headers.get('X-Faucet-Admin-Token', '')
    if not secrets.compare_digest(str(supplied), str(expected)):
        return jsonify({'ok': False, 'error': 'Unauthorized'}), 401

    return None


def _parse_future_datetime(value: Any) -> Optional[datetime]:
    """Parse an ISO timestamp and ensure it is in the future."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    if parsed <= datetime.now():
        return None
    return parsed


def _generate_event_code(prefix: str) -> str:
    """Generate a short URL-safe event code with an organizer-readable prefix."""
    safe_prefix = re.sub(r'[^A-Za-z0-9_-]+', '-', prefix).strip('-') or 'EVENT'
    return f"{safe_prefix}-{secrets.token_urlsafe(12)}"


def _event_claim_idempotency_key(code: str) -> str:
    """Build a stable node idempotency key for a one-time event claim code."""
    digest = hashlib.sha256(code.encode()).hexdigest()[:32]
    return f"event_claim:{digest}"


def _release_stale_event_claim_reservation(
    c: sqlite3.Cursor,
    code: str,
    now: datetime,
    event_config: Dict[str, Any],
) -> bool:
    """Release stale pre-transfer event claim reservations for retry."""
    ttl_seconds = int(event_config.get('pending_claim_ttl_seconds', 300))
    if ttl_seconds < 0:
        return False

    c.execute('''
        SELECT id, status, updated_at FROM event_claims
        WHERE code = ?
        ORDER BY id DESC
        LIMIT 1
    ''', (code,))
    row = c.fetchone()
    if not row:
        return False

    claim_id, status, updated_at_raw = row
    if status != 'reserved':
        return False

    try:
        updated_at = datetime.fromisoformat(updated_at_raw)
    except (TypeError, ValueError):
        return False

    if (now - updated_at).total_seconds() < ttl_seconds:
        return False

    c.execute('''
        UPDATE event_claim_codes
        SET claimed_wallet = NULL, claimed_ip = NULL, claimed_at = NULL, tx_hash = NULL
        WHERE code = ?
    ''', (code,))
    c.execute('''
        UPDATE event_claims
        SET status = ?, updated_at = ?
        WHERE id = ?
    ''', ('released_stale_reservation', now.isoformat(), claim_id))
    return True


def _mark_event_claim_transfer_started(db_path: str, claim_id: Optional[int]) -> None:
    """Mark an event claim past the locally retryable reservation point."""
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        conn.execute('''
            UPDATE event_claims
            SET status = ?, updated_at = ?
            WHERE id = ?
        ''', ('transfer_started', datetime.now().isoformat(), claim_id))
        conn.commit()
    finally:
        conn.close()


def _perform_faucet_transfer(
    config: Dict,
    logger: logging.Logger,
    wallet: str,
    amount: float,
    idempotency_key: Optional[str] = None,
    reason: Optional[str] = None,
) -> Optional[str]:
    """Perform a faucet transfer or return None in mock mode."""
    if config.get('distribution', {}).get('mock_mode', True):
        logger.info(f"Mock event faucet claim: {amount} RTC to {wallet}")
        return None

    dist = config.get('distribution', {})
    node_url = dist.get('node_url', 'http://127.0.0.1:8198')
    faucet_wallet = dist.get('faucet_wallet', 'testnet_faucet')
    admin_key = os.environ.get('RC_ADMIN_KEY') or dist.get('admin_key', '')

    if not admin_key:
        raise RuntimeError('RC_ADMIN_KEY not set, cannot perform real drip')

    payload = {
        "from_miner": faucet_wallet,
        "to_miner": wallet,
        "amount_rtc": amount,
    }
    if idempotency_key:
        payload["idempotency_key"] = idempotency_key
    if reason:
        payload["reason"] = reason

    response = requests.post(
        f"{node_url}/wallet/transfer",
        json=payload,
        headers={"X-Admin-Key": admin_key},
        timeout=10
    )

    if response.status_code != 200:
        raise RuntimeError(f"Transfer failed on node: {response.status_code}")

    result = response.json()
    if not result.get('ok'):
        raise RuntimeError('Transfer failed on node')
    return result.get('tx_hash')


def _finalize_event_claim(
    db_path: str,
    code: str,
    claim_id: Optional[int],
    tx_hash: Optional[str],
    status: str,
) -> None:
    """Finalize the durable event claim record after the transfer attempt."""
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        c = conn.cursor()
        c.execute('''
            UPDATE event_claim_codes
            SET tx_hash = ?
            WHERE code = ?
        ''', (tx_hash, code))
        c.execute('''
            UPDATE event_claims
            SET status = ?, tx_hash = ?, updated_at = ?
            WHERE id = ?
        ''', (status, tx_hash, datetime.now().isoformat(), claim_id))
        conn.commit()
    finally:
        conn.close()


def _release_event_claim(
    db_path: str,
    code: str,
    claim_id: Optional[int],
    status: str,
) -> None:
    """Release a code when no transfer was completed, allowing a later retry."""
    now = datetime.now().isoformat()
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        c = conn.cursor()
        c.execute('''
            UPDATE event_claim_codes
            SET claimed_wallet = NULL, claimed_ip = NULL, claimed_at = NULL, tx_hash = NULL
            WHERE code = ?
        ''', (code,))
        c.execute('''
            UPDATE event_claims
            SET status = ?, updated_at = ?
            WHERE id = ?
        ''', (status, now, claim_id))
        conn.commit()
    finally:
        conn.close()


def get_template_vars(config: Dict) -> Dict:
    """Get template variables from config."""
    return {
        'rate_limit': config.get('rate_limit', {}).get('max_amount', 0.5),
        'hours': config.get('rate_limit', {}).get('window_seconds', 86400) / 3600,
        'network': 'Testnet',
        'mock_mode': config.get('distribution', {}).get('mock_mode', True)
    }


# =============================================================================
# HTML Template
# =============================================================================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RustChain Testnet Faucet</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Courier New', monospace;
            background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%);
            color: #00ff00;
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 700px;
            margin: 0 auto;
        }
        header {
            text-align: center;
            padding: 40px 0;
            border-bottom: 2px solid #00ff00;
            margin-bottom: 30px;
        }
        h1 {
            font-size: 2.5em;
            text-shadow: 0 0 10px #00ff00;
            margin-bottom: 10px;
        }
        .subtitle {
            color: #888;
            font-size: 0.9em;
        }
        .card {
            background: rgba(0, 20, 0, 0.8);
            border: 1px solid #00ff00;
            border-radius: 8px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 0 20px rgba(0, 255, 0, 0.1);
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: bold;
        }
        input[type="text"] {
            width: 100%;
            padding: 15px;
            background: #001100;
            color: #00ff00;
            border: 1px solid #00ff00;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            font-size: 16px;
        }
        input[type="text"]:focus {
            outline: none;
            box-shadow: 0 0 10px rgba(0, 255, 0, 0.5);
        }
        input[type="text"]::placeholder {
            color: #444;
        }
        button {
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #00aa00, #00ff00);
            color: #000;
            border: none;
            border-radius: 4px;
            font-size: 18px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s;
            text-transform: uppercase;
        }
        button:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(0, 255, 0, 0.4);
        }
        button:disabled {
            background: #333;
            color: #666;
            cursor: not-allowed;
        }
        .result {
            padding: 15px;
            margin-top: 20px;
            border-radius: 4px;
            display: none;
        }
        .result.show {
            display: block;
        }
        .result.success {
            background: rgba(0, 50, 0, 0.8);
            border: 1px solid #00ff00;
        }
        .result.error {
            background: rgba(50, 0, 0, 0.8);
            border: 1px solid #ff0000;
            color: #ff6666;
        }
        .info-box {
            background: rgba(0, 20, 40, 0.8);
            border: 1px solid #0066ff;
            padding: 15px;
            border-radius: 4px;
            margin-top: 20px;
        }
        .info-box h3 {
            color: #00aaff;
            margin-bottom: 10px;
        }
        .info-box ul {
            list-style: none;
            padding-left: 0;
        }
        .info-box li {
            padding: 5px 0;
            color: #aaa;
        }
        .info-box li:before {
            content: "→ ";
            color: #00aaff;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            margin-top: 20px;
        }
        .stat-item {
            background: rgba(0, 30, 0, 0.6);
            padding: 15px;
            border-radius: 4px;
            text-align: center;
        }
        .stat-value {
            font-size: 1.5em;
            font-weight: bold;
            color: #00ff00;
        }
        .stat-label {
            font-size: 0.8em;
            color: #888;
            margin-top: 5px;
        }
        footer {
            text-align: center;
            padding: 30px 0;
            color: #666;
            font-size: 0.8em;
        }
        .badge {
            display: inline-block;
            padding: 3px 8px;
            background: #003300;
            border: 1px solid #00ff00;
            border-radius: 3px;
            font-size: 0.7em;
            margin-left: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>💧 RustChain Faucet</h1>
            <p class="subtitle">Get free test RTC tokens for development</p>
        </header>

        <div class="card">
            <form id="faucetForm">
                <div class="form-group">
                    <label for="wallet">Your RTC Wallet Address</label>
                    <input type="text" id="wallet" name="wallet" 
                           placeholder="RTCe4fbe4c9085b8b2ed3f1228504de66799025f6ce" required>
                </div>
                <button type="submit" id="submitBtn">Request Test RTC</button>
            </form>

            <div id="result" class="result"></div>

            <div class="info-box">
                <h3>ℹ️ Faucet Information</h3>
                <ul>
                    <li>Rate Limit: {{ rate_limit }} RTC per {{ hours|int }} hours</li>
                    <li>Network: RustChain {{ network }}</li>
                    {% if mock_mode %}
                    <li>Mode: Mock (no actual transfers)</li>
                    {% endif %}
                </ul>
            </div>

            <div class="stats" id="stats">
                <div class="stat-item">
                    <div class="stat-value" id="totalDrips">-</div>
                    <div class="stat-label">Total Drips</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" id="totalAmount">-</div>
                    <div class="stat-label">Total Distributed (RTC)</div>
                </div>
            </div>
        </div>

        <footer>
            <p>RustChain Testnet Faucet v1.0.0</p>
            <p>For development and testing purposes only</p>
        </footer>
    </div>

    <script>
        const form = document.getElementById('faucetForm');
        const result = document.getElementById('result');
        const submitBtn = document.getElementById('submitBtn');
        const walletInput = document.getElementById('wallet');

        function clearResult() {
            result.replaceChildren();
        }

        // Load stats
        async function loadStats() {
            try {
                const response = await fetch('/faucet/status');
                const data = await response.json();
                if (data.statistics) {
                    document.getElementById('totalDrips').textContent = data.statistics.total_drips;
                    document.getElementById('totalAmount').textContent = data.statistics.total_amount.toFixed(2);
                }
            } catch (err) {
                console.error('Failed to load stats:', err);
            }
        }

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            submitBtn.disabled = true;
            submitBtn.textContent = 'Processing...';
            result.className = 'result';
            clearResult();

            const wallet = walletInput.value.trim();

            try {
                const response = await fetch('/faucet/drip', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({wallet})
                });

                const data = await response.json();

                result.className = 'result show ' + (data.ok ? 'success' : 'error');
                
                if (data.ok) {
                    clearResult();
                    const strong = document.createElement('strong');
                    strong.textContent = '✅ Success!';
                    result.appendChild(strong);
                    result.appendChild(document.createElement('br'));
                    const msg = document.createTextNode(`Sent ${data.amount} RTC to ${wallet.substring(0, 10)}...${wallet.substring(wallet.length - 8)}`);
                    result.appendChild(msg);
                    if (data.next_available) {
                        result.appendChild(document.createElement('br'));
                        const small = document.createElement('small');
                        small.textContent = `Next available: ${new Date(data.next_available).toLocaleString()}`;
                        result.appendChild(small);
                    }
                    walletInput.value = '';
                    loadStats();
                } else {
                    clearResult();
                    const strong = document.createElement('strong');
                    strong.textContent = `❌ ${data.error}`;
                    result.appendChild(strong);
                    if (data.next_available) {
                        result.appendChild(document.createElement('br'));
                        const small = document.createElement('small');
                        small.textContent = `Next available: ${new Date(data.next_available).toLocaleString()}`;
                        result.appendChild(small);
                    }
                }
            } catch (err) {
                result.className = 'result show error';
                clearResult();
                const strong = document.createElement('strong');
                strong.textContent = '❌ Error: ';
                result.appendChild(strong);
                const msg = document.createTextNode(err.message);
                result.appendChild(msg);
            }

            submitBtn.disabled = false;
            submitBtn.textContent = 'Request Test RTC';
        });

        // Load stats on page load
        loadStats();
    </script>
</body>
</html>
"""


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='RustChain Testnet Faucet')
    parser.add_argument('--config', '-c', default='faucet_config.yaml',
                        help='Path to configuration file')
    parser.add_argument('--host', help='Override host from config')
    parser.add_argument('--port', '-p', type=int, help='Override port from config')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config if os.path.exists(args.config) else None)
    
    # Override with command line args
    if args.host:
        config['server']['host'] = args.host
    if args.port:
        config['server']['port'] = args.port
    if args.debug:
        config['server']['debug'] = True
    
    # Create and run app
    app = create_app(config)
    
    host = config['server']['host']
    port = config['server']['port']
    debug = config['server']['debug']
    
    logger = logging.getLogger('rustchain_faucet')
    logger.info(f"Starting RustChain Faucet on http://{host}:{port}")
    logger.info(f"Configuration: {args.config if os.path.exists(args.config) else 'default'}")
    
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    main()
