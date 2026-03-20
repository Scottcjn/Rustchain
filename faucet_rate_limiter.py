// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import time
import hashlib
import hmac
import sqlite3
from flask import request
from datetime import datetime, timedelta

DB_PATH = 'rustchain.db'

class FaucetRateLimiter:
    def __init__(self):
        self.secret_key = "rustchain_faucet_limiter_v1"
        self.init_database()

    def init_database(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS faucet_rate_limits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ip_address TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    user_agent TEXT,
                    timestamp INTEGER NOT NULL,
                    success BOOLEAN DEFAULT FALSE
                )
            ''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_faucet_ip ON faucet_rate_limits(ip_address)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_faucet_timestamp ON faucet_rate_limits(timestamp)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_faucet_hash ON faucet_rate_limits(request_hash)')

    def get_real_client_ip(self):
        """Extract real client IP with anti-spoofing protection"""
        remote_ip = request.remote_addr or '127.0.0.1'

        forwarded_for = request.headers.get('X-Forwarded-For', '').strip()
        if forwarded_for and self._is_trusted_proxy(remote_ip):
            return forwarded_for.split(',')[0].strip()

        real_ip = request.headers.get('X-Real-IP', '').strip()
        if real_ip and self._is_trusted_proxy(remote_ip):
            return real_ip

        return remote_ip

    def _is_trusted_proxy(self, ip):
        """Check if IP is from trusted reverse proxy"""
        trusted_proxies = ['127.0.0.1', '::1']
        return ip in trusted_proxies

    def generate_request_fingerprint(self):
        """Create cryptographic fingerprint of request"""
        client_ip = self.get_real_client_ip()
        user_agent = request.headers.get('User-Agent', '')
        accept_language = request.headers.get('Accept-Language', '')
        accept_encoding = request.headers.get('Accept-Encoding', '')

        fingerprint_data = f"{client_ip}:{user_agent}:{accept_language}:{accept_encoding}"
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:32]

    def create_request_signature(self, fingerprint, timestamp):
        """Generate HMAC signature to prevent tampering"""
        message = f"{fingerprint}:{timestamp}"
        return hmac.new(
            self.secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()[:16]

    def check_rate_limit(self, address, limit_hours=24, max_requests=3):
        """Check if request should be allowed based on rate limits"""
        client_ip = self.get_real_client_ip()
        fingerprint = self.generate_request_fingerprint()
        current_time = int(time.time())
        cutoff_time = current_time - (limit_hours * 3600)

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Clean old entries first
            cursor.execute('DELETE FROM faucet_rate_limits WHERE timestamp < ?', (cutoff_time,))

            # Check IP-based rate limit
            cursor.execute('''
                SELECT COUNT(*) FROM faucet_rate_limits
                WHERE ip_address = ? AND timestamp >= ? AND success = TRUE
            ''', (client_ip, cutoff_time))

            ip_count = cursor.fetchone()[0]
            if ip_count >= max_requests:
                return False, "IP rate limit exceeded"

            # Check fingerprint-based rate limit
            cursor.execute('''
                SELECT COUNT(*) FROM faucet_rate_limits
                WHERE request_hash = ? AND timestamp >= ? AND success = TRUE
            ''', (fingerprint, cutoff_time))

            fingerprint_count = cursor.fetchone()[0]
            if fingerprint_count >= max_requests:
                return False, "Request fingerprint rate limit exceeded"

            # Check for suspicious rapid requests from same fingerprint
            cursor.execute('''
                SELECT COUNT(*) FROM faucet_rate_limits
                WHERE request_hash = ? AND timestamp >= ?
            ''', (fingerprint, current_time - 300))  # 5 minutes

            rapid_count = cursor.fetchone()[0]
            if rapid_count >= 5:
                return False, "Too many rapid requests detected"

            return True, "Request allowed"

    def record_request(self, success=False):
        """Record the current request attempt"""
        client_ip = self.get_real_client_ip()
        fingerprint = self.generate_request_fingerprint()
        user_agent = request.headers.get('User-Agent', '')[:255]
        current_time = int(time.time())

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                INSERT INTO faucet_rate_limits
                (ip_address, request_hash, user_agent, timestamp, success)
                VALUES (?, ?, ?, ?, ?)
            ''', (client_ip, fingerprint, user_agent, current_time, success))

    def get_time_until_next_request(self, limit_hours=24):
        """Get seconds until next request is allowed"""
        client_ip = self.get_real_client_ip()
        fingerprint = self.generate_request_fingerprint()
        cutoff_time = int(time.time()) - (limit_hours * 3600)

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Get most recent successful request time
            cursor.execute('''
                SELECT MAX(timestamp) FROM faucet_rate_limits
                WHERE (ip_address = ? OR request_hash = ?)
                AND timestamp >= ? AND success = TRUE
            ''', (client_ip, fingerprint, cutoff_time))

            result = cursor.fetchone()[0]
            if not result:
                return 0

            next_allowed = result + (limit_hours * 3600)
            current_time = int(time.time())

            return max(0, next_allowed - current_time)

    def detect_anomalous_patterns(self):
        """Detect potentially malicious request patterns"""
        current_time = int(time.time())
        last_hour = current_time - 3600

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Check for excessive requests from single IP
            cursor.execute('''
                SELECT ip_address, COUNT(*) as count FROM faucet_rate_limits
                WHERE timestamp >= ?
                GROUP BY ip_address
                HAVING count > 20
            ''', (last_hour,))

            suspicious_ips = cursor.fetchall()

            # Check for identical user agents across different IPs
            cursor.execute('''
                SELECT user_agent, COUNT(DISTINCT ip_address) as ip_count
                FROM faucet_rate_limits
                WHERE timestamp >= ? AND user_agent != ''
                GROUP BY user_agent
                HAVING ip_count > 5
            ''', (last_hour,))

            suspicious_agents = cursor.fetchall()

            return {
                'suspicious_ips': suspicious_ips,
                'suspicious_user_agents': suspicious_agents
            }

    def cleanup_old_records(self, days_to_keep=30):
        """Clean up old rate limit records"""
        cutoff_time = int(time.time()) - (days_to_keep * 24 * 3600)

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM faucet_rate_limits WHERE timestamp < ?', (cutoff_time,))
            deleted_count = cursor.rowcount

        return deleted_count

rate_limiter = FaucetRateLimiter()
