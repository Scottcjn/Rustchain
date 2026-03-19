// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import hashlib
import hmac
import time
import sqlite3
import secrets
from functools import wraps
from flask import request, jsonify

DB_PATH = 'faucet_security.db'
TOKEN_EXPIRY = 3600  # 1 hour
SECRET_KEY = secrets.token_hex(32)

def init_security_db():
    """Initialize security database for client verification"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS client_tokens (
                ip_hash TEXT PRIMARY KEY,
                token TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                verified INTEGER DEFAULT 0
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS ip_verification (
                ip_hash TEXT PRIMARY KEY,
                challenge TEXT NOT NULL,
                response TEXT,
                verified_at INTEGER,
                trust_score INTEGER DEFAULT 0
            )
        ''')

def hash_ip(ip_addr):
    """Create secure hash of IP address"""
    salt = SECRET_KEY[:16].encode()
    return hashlib.pbkdf2_hmac('sha256', ip_addr.encode(), salt, 100000).hex()

def generate_verification_token(ip_addr):
    """Generate cryptographic verification token for client"""
    timestamp = int(time.time())
    ip_hash = hash_ip(ip_addr)
    
    payload = f"{ip_hash}:{timestamp}"
    signature = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    
    token = f"{payload}:{signature}"
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            'INSERT OR REPLACE INTO client_tokens (ip_hash, token, created_at) VALUES (?, ?, ?)',
            (ip_hash, token, timestamp)
        )
    
    return token

def verify_client_token(token, ip_addr):
    """Verify client token matches actual IP"""
    try:
        payload, signature = token.rsplit(':', 1)
        expected_sig = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
        
        if not hmac.compare_digest(signature, expected_sig):
            return False
            
        ip_hash, timestamp = payload.split(':', 1)
        current_time = int(time.time())
        
        if current_time - int(timestamp) > TOKEN_EXPIRY:
            return False
            
        if ip_hash != hash_ip(ip_addr):
            return False
            
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                'UPDATE client_tokens SET verified = 1 WHERE ip_hash = ? AND token = ?',
                (ip_hash, token)
            )
        
        return True
    except:
        return False

def get_secure_client_ip():
    """Get verified client IP with anti-spoofing protection"""
    # Never trust forwarded headers without verification
    real_ip = request.environ.get('REMOTE_ADDR', '127.0.0.1')
    
    # Check for verification token in headers
    token = request.headers.get('X-Client-Token')
    if token and verify_client_token(token, real_ip):
        return real_ip
    
    # For proxy scenarios, require additional verification
    forwarded = request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
    if forwarded and forwarded != real_ip:
        # Create challenge for forwarded IP verification
        challenge = create_ip_challenge(forwarded, real_ip)
        return None, challenge
    
    return real_ip

def create_ip_challenge(claimed_ip, proxy_ip):
    """Create cryptographic challenge for IP verification"""
    challenge_data = secrets.token_urlsafe(32)
    ip_hash = hash_ip(claimed_ip)
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            'INSERT OR REPLACE INTO ip_verification (ip_hash, challenge) VALUES (?, ?)',
            (ip_hash, challenge_data)
        )
    
    return {
        'challenge': challenge_data,
        'instructions': 'Verify IP ownership by solving challenge',
        'proxy_detected': proxy_ip
    }

def require_verified_ip(f):
    """Decorator to enforce IP verification"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        result = get_secure_client_ip()
        
        if isinstance(result, tuple):
            return jsonify({
                'error': 'IP verification required',
                'challenge': result[1]
            }), 403
        
        if not result:
            return jsonify({'error': 'Invalid client verification'}), 403
            
        request.verified_ip = result
        return f(*args, **kwargs)
    
    return decorated_function

def update_trust_score(ip_addr, action):
    """Update trust score for verified IP"""
    ip_hash = hash_ip(ip_addr)
    score_delta = 1 if action == 'valid_request' else -5
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            'SELECT trust_score FROM ip_verification WHERE ip_hash = ?',
            (ip_hash,)
        )
        row = cursor.fetchone()
        current_score = row[0] if row else 0
        
        new_score = max(0, min(100, current_score + score_delta))
        conn.execute(
            'INSERT OR REPLACE INTO ip_verification (ip_hash, trust_score, verified_at) VALUES (?, ?, ?)',
            (ip_hash, new_score, int(time.time()))
        )

def cleanup_expired_tokens():
    """Remove expired verification tokens"""
    cutoff = int(time.time()) - TOKEN_EXPIRY
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('DELETE FROM client_tokens WHERE created_at < ?', (cutoff,))
        conn.execute('DELETE FROM ip_verification WHERE verified_at < ?', (cutoff,))

# Initialize on import
init_security_db()