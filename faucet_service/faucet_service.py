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
import sys
import json
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
        'required_prefix': '0x',
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


# =============================================================================
# Validator
# =============================================================================

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
        required_prefix = self.validation_config.get('required_prefix', '0x')
        if required_prefix and not wallet.startswith(required_prefix):
            return False, f"Wallet must start with '{required_prefix}'"
        
        # Check length
        min_len = self.validation_config.get('min_length', 10)
        max_len = self.validation_config.get('max_length', 66)
        
        if len(wallet) < min_len:
            return False, f"Wallet address too short (min {min_len} characters)"
        
        if len(wallet) > max_len:
            return False, f"Wallet address too long (max {max_len} characters)"
        
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
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'completed',
            tx_hash TEXT
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS faucet_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE UNIQUE,
            total_drips INTEGER DEFAULT 0,
            total_amount REAL DEFAULT 0,
            unique_wallets INTEGER DEFAULT 0,
            unique_ips INTEGER DEFAULT 0
        )
    ''')
    
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_drip_wallet ON drip_requests(wallet)
    ''')
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_drip_ip ON drip_requests(ip_address)
    ''')
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_drip_timestamp ON drip_requests(timestamp)
    ''')
    
    conn.commit()
    conn.close()


# =============================================================================
# Flask Application
# =============================================================================

def create_app(config: Optional[Dict[str, Any]] = None) -> Flask:
    """Create and configure the Flask application."""
    
    # Load configuration
    if config is None:
        config = load_config()
    
    # Initialize logging
    logger = setup_logging(config)
    
    # Initialize database
    db_path = config.get('database', {}).get('path', 'faucet.db')
    init_database(db_path)
    
    # Initialize components
    rate_limiter = RateLimiter(config, logger)
    validator = FaucetValidator(config, logger)
    
    # Create Flask app
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = config.get('security', {}).get('max_body_size', 1048576)
    
    # Enable CORS
    cors_origins = config.get('security', {}).get('cors_origins', ['*'])
    CORS(app, origins=cors_origins)
    
    # Store components in app config
    app.config['faucet_config'] = config
    app.config['faucet_logger'] = logger
    app.config['rate_limiter'] = rate_limiter
    app.config['validator'] = validator
    
    # Register routes
    register_routes(app, config, logger, rate_limiter, validator)
    
    return app


def register_routes(app: Flask, config: Dict, logger: logging.Logger,
                    rate_limiter: RateLimiter, validator: FaucetValidator) -> None:
    """Register all application routes."""
    
    base_path = config.get('server', {}).get('base_path', '/faucet')
    
    @app.route('/')
    def index():
        """Redirect to faucet page."""
        return jsonify({'redirect': f'{base_path}'})
    
    @app.route(base_path)
    def faucet_page():
        """Serve the faucet web interface."""
        return render_template_string(HTML_TEMPLATE, **get_template_vars(config))
    
    @app.route(f'{base_path}/drip', methods=['POST'])
    def drip():
        """
        Handle drip requests.
        
        Request body:
            {"wallet": "0x..."}
        
        Response:
            {"ok": true, "amount": 0.5, "wallet": "...", "next_available": "..."}
        """
        start_time = time.time()
        
        # Parse request
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or 'wallet' not in data:
            logger.warning(f"Invalid request from {request.remote_addr}: missing wallet")
            return jsonify({'ok': False, 'error': 'Wallet address required'}), 400
        
        wallet_value = data['wallet']
        if not isinstance(wallet_value, str) or not wallet_value.strip():
            logger.warning(f"Invalid request from {request.remote_addr}: invalid wallet type")
            return jsonify({'ok': False, 'error': 'Wallet address required'}), 400

        wallet = wallet_value.strip()
        ip = get_client_ip(request)
        
        logger.info(f"Drip request: wallet={wallet}, ip={ip}")
        
        # Validate wallet
        valid, error = validator.validate_wallet(wallet)
        if not valid:
            logger.warning(f"Invalid wallet {wallet}: {error}")
            return jsonify({'ok': False, 'error': error}), 400
        
        # Check rate limit
        allowed, next_available = rate_limiter.check_rate_limit(ip, wallet)
        if not allowed:
            logger.info(f"Rate limit exceeded for {ip}/{wallet}")
            return jsonify({
                'ok': False,
                'error': 'Rate limit exceeded',
                'next_available': next_available
            }), 429
        
        # Process drip
        amount = config.get('distribution', {}).get('amount', 0.5)
        
        # In mock mode, just record the request
        if config.get('distribution', {}).get('mock_mode', True):
            tx_hash = None
            logger.info(f"Mock drip: {amount} RTC to {wallet}")
        else:
            # TODO: Implement actual token transfer
            tx_hash = None
            logger.info(f"Real drip: {amount} RTC to {wallet}")
        
        # Record the request
        rate_limiter.record_request(f"{ip}:{wallet}", ip, wallet, amount)
        
        # Calculate next available time
        window_seconds = config.get('rate_limit', {}).get('window_seconds', 86400)
        next_avail = datetime.now() + timedelta(seconds=window_seconds)
        
        elapsed = time.time() - start_time
        logger.info(f"Drip completed in {elapsed:.3f}s: {amount} RTC to {wallet}")
        
        return jsonify({
            'ok': True,
            'amount': amount,
            'wallet': wallet,
            'tx_hash': tx_hash,
            'next_available': next_avail.isoformat()
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


def get_client_ip(request) -> str:
    """Get client IP address from request, handling proxies."""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    if request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    return request.remote_addr or '127.0.0.1'


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
                           placeholder="0xYourWalletAddress" required>
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
            result.innerHTML = '';

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
                    result.innerHTML = `
                        <strong>✅ Success!</strong><br>
                        Sent ${data.amount} RTC to ${wallet.substring(0, 10)}...${wallet.substring(wallet.length - 8)}<br>
                        ${data.next_available ? `<small>Next available: ${new Date(data.next_available).toLocaleString()}</small>` : ''}
                    `;
                    walletInput.value = '';
                    loadStats();
                } else {
                    result.innerHTML = `
                        <strong>❌ ${data.error}</strong><br>
                        ${data.next_available ? `<small>Next available: ${new Date(data.next_available).toLocaleString()}</small>` : ''}
                    `;
                }
            } catch (err) {
                result.className = 'result show error';
                result.innerHTML = `<strong>❌ Error:</strong> ${err.message}`;
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
