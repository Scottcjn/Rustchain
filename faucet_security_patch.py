// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import hmac
import hashlib
import time
import secrets
import sqlite3
from flask import request
import ipaddress

DB_PATH = 'blockchain.db'
SECRET_KEY = secrets.token_bytes(32)
TOKEN_VALIDITY = 300  # 5 minutes

def init_security_db():
    """Initialize security tables for IP validation and rate limiting"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS ip_security_tokens (
                ip_address TEXT PRIMARY KEY,
                token_hash TEXT NOT NULL,
                issued_at INTEGER NOT NULL,
                request_count INTEGER DEFAULT 0,
                last_request INTEGER NOT NULL
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS trusted_proxies (
                proxy_ip TEXT PRIMARY KEY,
                added_at INTEGER NOT NULL,
                active INTEGER DEFAULT 1
            )
        ''')
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_ip_tokens_issued 
            ON ip_security_tokens(issued_at)
        ''')

def generate_ip_token(ip_address):
    """Generate HMAC token for IP validation"""
    timestamp = int(time.time())
    message = f"{ip_address}:{timestamp}"
    token = hmac.new(SECRET_KEY, message.encode(), hashlib.sha256).hexdigest()
    return f"{timestamp}:{token}"

def validate_ip_token(ip_address, token_string):
    """Validate HMAC token against IP and timestamp"""
    try:
        timestamp_str, token = token_string.split(':', 1)
        timestamp = int(timestamp_str)
        
        if time.time() - timestamp > TOKEN_VALIDITY:
            return False
            
        expected_message = f"{ip_address}:{timestamp}"
        expected_token = hmac.new(SECRET_KEY, expected_message.encode(), hashlib.sha256).hexdigest()
        
        return hmac.compare_digest(token, expected_token)
    except (ValueError, TypeError):
        return False

def is_trusted_proxy(ip_address):
    """Check if IP is a trusted reverse proxy"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                "SELECT active FROM trusted_proxies WHERE proxy_ip = ? AND active = 1",
                (ip_address,)
            )
            return cursor.fetchone() is not None
    except:
        return False

def normalize_ip(ip_string):
    """Normalize IP address to prevent spoofing variations"""
    try:
        ip_obj = ipaddress.ip_address(ip_string.strip())
        if ip_obj.is_private or ip_obj.is_loopback:
            return str(ip_obj)
        return str(ip_obj)
    except ValueError:
        return None

def get_secure_client_ip():
    """Get client IP with enhanced security validation"""
    remote_addr = request.remote_addr or '127.0.0.1'
    
    # Check for X-Forwarded-For only from trusted proxies
    if is_trusted_proxy(remote_addr):
        forwarded_header = request.headers.get('X-Forwarded-For')
        if forwarded_header:
            # Take first IP from chain and validate
            client_ip = forwarded_header.split(',')[0].strip()
            normalized = normalize_ip(client_ip)
            if normalized:
                return normalized
    
    return normalize_ip(remote_addr) or '127.0.0.1'

def update_ip_security_record(ip_address):
    """Update security tracking for IP address"""
    current_time = int(time.time())
    token = generate_ip_token(ip_address)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "SELECT request_count FROM ip_security_tokens WHERE ip_address = ?",
            (ip_address,)
        )
        existing = cursor.fetchone()
        
        if existing:
            new_count = existing[0] + 1
            conn.execute('''
                UPDATE ip_security_tokens 
                SET token_hash = ?, issued_at = ?, request_count = ?, last_request = ?
                WHERE ip_address = ?
            ''', (token_hash, current_time, new_count, current_time, ip_address))
        else:
            conn.execute('''
                INSERT INTO ip_security_tokens 
                (ip_address, token_hash, issued_at, request_count, last_request)
                VALUES (?, ?, ?, 1, ?)
            ''', (ip_address, token_hash, current_time, current_time))
    
    return token

def check_rate_limit_security(ip_address, max_requests=5, window=3600):
    """Enhanced rate limiting with cryptographic validation"""
    current_time = int(time.time())
    window_start = current_time - window
    
    with sqlite3.connect(DB_PATH) as conn:
        # Clean expired tokens
        conn.execute(
            "DELETE FROM ip_security_tokens WHERE issued_at < ?",
            (current_time - TOKEN_VALIDITY,)
        )
        
        cursor = conn.execute('''
            SELECT request_count, last_request, token_hash 
            FROM ip_security_tokens 
            WHERE ip_address = ? AND last_request > ?
        ''', (ip_address, window_start))
        
        record = cursor.fetchone()
        
        if record and record[0] >= max_requests:
            return False, "Rate limit exceeded"
    
    return True, "OK"

def add_trusted_proxy(proxy_ip):
    """Add trusted proxy to whitelist"""
    normalized = normalize_ip(proxy_ip)
    if not normalized:
        return False
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            INSERT OR REPLACE INTO trusted_proxies (proxy_ip, added_at)
            VALUES (?, ?)
        ''', (normalized, int(time.time())))
    
    return True

def validate_request_integrity():
    """Comprehensive request validation for faucet security"""
    client_ip = get_secure_client_ip()
    if not client_ip:
        return False, "Invalid IP address", None
    
    allowed, message = check_rate_limit_security(client_ip)
    if not allowed:
        return False, message, client_ip
    
    security_token = update_ip_security_record(client_ip)
    return True, "Valid request", client_ip