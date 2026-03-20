// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import hmac
import hashlib
import time
import sqlite3
import ipaddress
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Set, Tuple
from flask import request

class FaucetSecurityManager:
    def __init__(self, db_path: str = 'rustchain.db', secret_key: Optional[str] = None):
        self.db_path = db_path
        self.secret_key = secret_key or os.environ.get('FAUCET_SECRET', 'default_dev_key_change_in_prod')
        self.trusted_proxies = self._load_trusted_proxies()
        self.init_security_tables()

    def _load_trusted_proxies(self) -> Set[str]:
        """Load trusted reverse proxy IPs from config"""
        default_proxies = {'127.0.0.1', '::1'}
        try:
            proxy_config = os.environ.get('TRUSTED_PROXIES', '127.0.0.1,::1')
            return set(proxy_config.split(',')) | default_proxies
        except:
            return default_proxies

    def init_security_tables(self):
        """Initialize security tracking tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS faucet_security_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    real_ip TEXT NOT NULL,
                    claimed_ip TEXT,
                    fingerprint TEXT NOT NULL,
                    hmac_signature TEXT NOT NULL,
                    amount REAL,
                    blocked BOOLEAN DEFAULT 0,
                    reason TEXT
                )
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_security_ip_time
                ON faucet_security_log(real_ip, timestamp)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_security_fingerprint
                ON faucet_security_log(fingerprint, timestamp)
            ''')

    def generate_request_fingerprint(self, ip_addr: str) -> str:
        """Generate unique fingerprint for request"""
        user_agent = request.headers.get('User-Agent', '')
        accept_lang = request.headers.get('Accept-Language', '')
        accept_enc = request.headers.get('Accept-Encoding', '')

        # Include timing component to detect rapid requests
        time_window = int(time.time() / 300)  # 5-minute windows

        fingerprint_data = f"{ip_addr}:{user_agent}:{accept_lang}:{accept_enc}:{time_window}"
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:16]

    def create_security_signature(self, ip_addr: str, amount: float, timestamp: float) -> str:
        """Create HMAC signature for request validation"""
        message = f"{ip_addr}:{amount}:{timestamp}"
        return hmac.new(
            self.secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

    def get_real_client_ip(self) -> Tuple[str, str]:
        """Get real client IP, detecting proxy spoofing attempts"""
        direct_ip = request.remote_addr or '127.0.0.1'
        forwarded_ip = request.headers.get('X-Forwarded-For', '').split(',')[0].strip()

        # If no proxy headers or direct connection from untrusted source
        if not forwarded_ip or direct_ip not in self.trusted_proxies:
            return direct_ip, direct_ip

        # Validate forwarded IP format
        try:
            ipaddress.ip_address(forwarded_ip)
            return forwarded_ip, direct_ip
        except ValueError:
            # Invalid IP in X-Forwarded-For, use direct connection
            return direct_ip, direct_ip

    def check_rate_limits(self, ip_addr: str, amount: float) -> Dict:
        """Enhanced rate limiting with crypto verification"""
        current_time = time.time()
        fingerprint = self.generate_request_fingerprint(ip_addr)
        signature = self.create_security_signature(ip_addr, amount, current_time)

        with sqlite3.connect(self.db_path) as conn:
            # Check recent requests by IP (1 hour window)
            recent_by_ip = conn.execute('''
                SELECT COUNT(*), SUM(amount) FROM faucet_security_log
                WHERE real_ip = ? AND timestamp > ? AND blocked = 0
            ''', (ip_addr, current_time - 3600)).fetchone()

            # Check recent requests by fingerprint (stricter, 30 min window)
            recent_by_fingerprint = conn.execute('''
                SELECT COUNT(*), SUM(amount) FROM faucet_security_log
                WHERE fingerprint = ? AND timestamp > ? AND blocked = 0
            ''', (fingerprint, current_time - 1800)).fetchone()

            # Check for signature replay attacks
            signature_used = conn.execute('''
                SELECT COUNT(*) FROM faucet_security_log
                WHERE hmac_signature = ? AND timestamp > ?
            ''', (signature, current_time - 300)).fetchone()[0]

        ip_requests, ip_total = recent_by_ip or (0, 0)
        fp_requests, fp_total = recent_by_fingerprint or (0, 0)

        # Rate limit thresholds
        max_requests_per_hour = 3
        max_amount_per_hour = 15.0
        max_fp_requests = 2

        result = {
            'allowed': True,
            'reason': None,
            'signature': signature,
            'fingerprint': fingerprint,
            'wait_time': 0
        }

        if signature_used > 0:
            result.update({'allowed': False, 'reason': 'Signature replay detected'})
        elif ip_requests >= max_requests_per_hour:
            result.update({'allowed': False, 'reason': 'IP hourly request limit exceeded', 'wait_time': 3600})
        elif (ip_total or 0) + amount > max_amount_per_hour:
            result.update({'allowed': False, 'reason': 'IP hourly amount limit exceeded', 'wait_time': 3600})
        elif fp_requests >= max_fp_requests:
            result.update({'allowed': False, 'reason': 'Device request limit exceeded', 'wait_time': 1800})

        return result

    def log_faucet_request(self, real_ip: str, claimed_ip: str, fingerprint: str,
                          signature: str, amount: float, blocked: bool = False, reason: str = None):
        """Log security information for faucet request"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO faucet_security_log
                (timestamp, real_ip, claimed_ip, fingerprint, hmac_signature, amount, blocked, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (time.time(), real_ip, claimed_ip, fingerprint, signature, amount, blocked, reason))

    def validate_request_integrity(self, ip_addr: str, amount: float, provided_signature: str) -> bool:
        """Validate request hasn't been tampered with"""
        expected_sig = self.create_security_signature(ip_addr, amount, time.time())
        return hmac.compare_digest(expected_sig, provided_signature)

    def cleanup_old_logs(self, days_to_keep: int = 30):
        """Clean up old security logs"""
        cutoff_time = time.time() - (days_to_keep * 24 * 3600)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('DELETE FROM faucet_security_log WHERE timestamp < ?', (cutoff_time,))

    def get_security_stats(self) -> Dict:
        """Get security statistics for monitoring"""
        with sqlite3.connect(self.db_path) as conn:
            total_requests = conn.execute('SELECT COUNT(*) FROM faucet_security_log').fetchone()[0]
            blocked_requests = conn.execute('SELECT COUNT(*) FROM faucet_security_log WHERE blocked = 1').fetchone()[0]

            # Recent activity (last 24h)
            recent_cutoff = time.time() - 86400
            recent_requests = conn.execute('''
                SELECT COUNT(*) FROM faucet_security_log WHERE timestamp > ?
            ''', (recent_cutoff,)).fetchone()[0]

            # Top IPs by request count
            top_ips = conn.execute('''
                SELECT real_ip, COUNT(*) as req_count FROM faucet_security_log
                WHERE timestamp > ? GROUP BY real_ip ORDER BY req_count DESC LIMIT 10
            ''', (recent_cutoff,)).fetchall()

        return {
            'total_requests': total_requests,
            'blocked_requests': blocked_requests,
            'block_rate': (blocked_requests / max(total_requests, 1)) * 100,
            'recent_requests_24h': recent_requests,
            'top_requesting_ips': dict(top_ips)
        }
