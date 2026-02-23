from functools import wraps
import time
from flask import request, jsonify

def require_auth(admin_key):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            key = request.headers.get("X-Admin-Key") or request.headers.get("X-API-Key")
            if not key or key != admin_key:
                return jsonify({"error": "Unauthorized"}), 401
            return f(*args, **kwargs)
        return decorated
    return decorator

class RateLimiter:
    def __init__(self, requests_per_minute=10):
        self.requests_per_minute = requests_per_minute
        self.requests = {} # (ip, endpoint) -> [timestamps]

    def is_rate_limited(self, ip, endpoint):
        now = time.time()
        key = (ip, endpoint)
        if key not in self.requests:
            self.requests[key] = []
        
        # Filter timestamps older than 60 seconds
        self.requests[key] = [ts for ts in self.requests[key] if now - ts < 60]
        
        if len(self.requests[key]) >= self.requests_per_minute:
            return True
        
        self.requests[key].append(now)
        return False

def rate_limit(limiter):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            ip = request.remote_addr 
            endpoint = request.path
            if limiter.is_rate_limited(ip, endpoint):
                return jsonify({"error": "Rate limit exceeded"}), 429
            return f(*args, **kwargs)
        return decorated
    return decorator
