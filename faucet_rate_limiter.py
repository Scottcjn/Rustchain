// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import hashlib
import time
import json
import hmac
from flask import request
from datetime import datetime, timedelta

DB_PATH = 'rustchain.db'

class FaucetRateLimiter:
    def __init__(self, request_limit=5, window_hours=24):
        self.request_limit = request_limit
        self.window_hours = window_hours
        self.init_db()

    def init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS faucet_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_hash TEXT NOT NULL,
                fingerprint_hash TEXT NOT NULL,
                request_signature TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                user_agent TEXT,
                request_size INTEGER,
                timing_delta REAL
            )''')
            
            conn.execute('''CREATE INDEX IF NOT EXISTS idx_faucet_ip_time 
                           ON faucet_requests(ip_hash, timestamp)''')
            conn.execute('''CREATE INDEX IF NOT EXISTS idx_faucet_fingerprint 
                           ON faucet_requests(fingerprint_hash, timestamp)''')

    def get_client_fingerprint(self):
        """Generate client fingerprint from multiple request attributes"""
        user_agent = request.headers.get('User-Agent', '')
        accept_lang = request.headers.get('Accept-Language', '')
        accept_enc = request.headers.get('Accept-Encoding', '')
        connection = request.headers.get('Connection', '')
        
        fingerprint_data = f"{user_agent}|{accept_lang}|{accept_enc}|{connection}"
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()

    def get_request_signature(self):
        """Generate request signature for replay attack detection"""
        timestamp = str(int(time.time()))
        remote_addr = request.remote_addr or '127.0.0.1'
        path = request.path
        method = request.method
        
        signature_data = f"{timestamp}|{remote_addr}|{path}|{method}"
        signature = hmac.new(
            b'rustchain_faucet_key',
            signature_data.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return f"{timestamp}:{signature}"

    def calculate_timing_delta(self):
        """Calculate request timing patterns for behavioral analysis"""
        current_time = time.time()
        last_request_time = getattr(self, '_last_request_time', None)
        
        if last_request_time:
            delta = current_time - last_request_time
        else:
            delta = 0.0
            
        self._last_request_time = current_time
        return delta

    def get_trusted_ip(self):
        """Get real client IP with proxy validation"""
        remote_addr = request.remote_addr or '127.0.0.1'
        
        # Trusted proxy networks (RFC1918 + common cloud providers)
        trusted_proxies = [
            '10.0.0.0/8',
            '172.16.0.0/12', 
            '192.168.0.0/16',
            '127.0.0.0/8'
        ]
        
        forwarded_for = request.headers.get('X-Forwarded-For')
        real_ip = request.headers.get('X-Real-IP')
        
        # Only trust forwarded headers from known proxy IPs
        if self.is_trusted_proxy(remote_addr, trusted_proxies):
            if real_ip:
                return real_ip.split(',')[0].strip()
            elif forwarded_for:
                return forwarded_for.split(',')[0].strip()
        
        return remote_addr

    def is_trusted_proxy(self, ip, proxy_networks):
        """Check if IP is in trusted proxy network ranges"""
        import ipaddress
        try:
            ip_addr = ipaddress.ip_address(ip)
            for network in proxy_networks:
                if ip_addr in ipaddress.ip_network(network):
                    return True
        except:
            pass
        return False

    def hash_ip(self, ip):
        """Hash IP address for privacy"""
        salt = "rustchain_ip_salt_2026"
        return hashlib.sha256(f"{salt}{ip}".encode()).hexdigest()

    def check_rate_limit(self, wallet_address):
        """Enhanced rate limit check with multiple validation layers"""
        current_time = int(time.time())
        window_start = current_time - (self.window_hours * 3600)
        
        # Get client identifiers
        client_ip = self.get_trusted_ip()
        ip_hash = self.hash_ip(client_ip)
        fingerprint_hash = self.get_client_fingerprint()
        request_signature = self.get_request_signature()
        timing_delta = self.calculate_timing_delta()
        
        with sqlite3.connect(DB_PATH) as conn:
            # Check IP-based rate limit
            ip_count = conn.execute(
                'SELECT COUNT(*) FROM faucet_requests WHERE ip_hash = ? AND timestamp > ?',
                (ip_hash, window_start)
            ).fetchone()[0]
            
            if ip_count >= self.request_limit:
                return False, "IP rate limit exceeded"
            
            # Check fingerprint-based rate limit (stricter)
            fp_count = conn.execute(
                'SELECT COUNT(*) FROM faucet_requests WHERE fingerprint_hash = ? AND timestamp > ?',
                (fingerprint_hash, window_start)
            ).fetchone()[0]
            
            if fp_count >= (self.request_limit - 1):
                return False, "Device fingerprint rate limit exceeded"
            
            # Check for rapid-fire requests (timing analysis)
            if timing_delta > 0 and timing_delta < 2.0:
                recent_rapid = conn.execute(
                    'SELECT COUNT(*) FROM faucet_requests WHERE ip_hash = ? AND timestamp > ? AND timing_delta < 5.0',
                    (ip_hash, current_time - 300)
                ).fetchone()[0]
                
                if recent_rapid >= 3:
                    return False, "Rapid request pattern detected"
            
            # Check for signature replay attacks
            signature_exists = conn.execute(
                'SELECT COUNT(*) FROM faucet_requests WHERE request_signature = ?',
                (request_signature,)
            ).fetchone()[0]
            
            if signature_exists > 0:
                return False, "Request signature replay detected"
            
            # Record this request
            user_agent = request.headers.get('User-Agent', '')[:255]
            request_size = len(str(request.get_data()))
            
            conn.execute('''INSERT INTO faucet_requests 
                           (ip_hash, fingerprint_hash, request_signature, timestamp, 
                            user_agent, request_size, timing_delta)
                           VALUES (?, ?, ?, ?, ?, ?, ?)''',
                        (ip_hash, fingerprint_hash, request_signature, current_time,
                         user_agent, request_size, timing_delta))
            
            # Clean old records
            conn.execute('DELETE FROM faucet_requests WHERE timestamp < ?', (window_start,))
            
            return True, "Rate limit check passed"

    def get_rate_limit_status(self):
        """Get current rate limit status for client"""
        current_time = int(time.time())
        window_start = current_time - (self.window_hours * 3600)
        
        client_ip = self.get_trusted_ip()
        ip_hash = self.hash_ip(client_ip)
        fingerprint_hash = self.get_client_fingerprint()
        
        with sqlite3.connect(DB_PATH) as conn:
            ip_count = conn.execute(
                'SELECT COUNT(*) FROM faucet_requests WHERE ip_hash = ? AND timestamp > ?',
                (ip_hash, window_start)
            ).fetchone()[0]
            
            fp_count = conn.execute(
                'SELECT COUNT(*) FROM faucet_requests WHERE fingerprint_hash = ? AND timestamp > ?',
                (fingerprint_hash, window_start)
            ).fetchone()[0]
            
            remaining_ip = max(0, self.request_limit - ip_count)
            remaining_fp = max(0, (self.request_limit - 1) - fp_count)
            
            return {
                'ip_requests': ip_count,
                'fingerprint_requests': fp_count,
                'remaining_requests': min(remaining_ip, remaining_fp),
                'window_hours': self.window_hours,
                'reset_time': window_start + (self.window_hours * 3600)
            }

    def get_security_metrics(self):
        """Get security metrics for monitoring"""
        current_time = int(time.time())
        last_hour = current_time - 3600
        
        with sqlite3.connect(DB_PATH) as conn:
            total_requests = conn.execute(
                'SELECT COUNT(*) FROM faucet_requests WHERE timestamp > ?',
                (last_hour,)
            ).fetchone()[0]
            
            unique_ips = conn.execute(
                'SELECT COUNT(DISTINCT ip_hash) FROM faucet_requests WHERE timestamp > ?',
                (last_hour,)
            ).fetchone()[0]
            
            rapid_requests = conn.execute(
                'SELECT COUNT(*) FROM faucet_requests WHERE timestamp > ? AND timing_delta < 2.0',
                (last_hour,)
            ).fetchone()[0]
            
            return {
                'requests_last_hour': total_requests,
                'unique_ips_last_hour': unique_ips,
                'rapid_requests_last_hour': rapid_requests,
                'average_requests_per_ip': round(total_requests / max(1, unique_ips), 2)
            }