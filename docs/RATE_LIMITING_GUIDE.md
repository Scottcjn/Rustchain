# RustChain Rate Limiting Guide

## Overview

This guide provides comprehensive instructions for implementing and configuring rate limiting in RustChain to prevent API abuse and DoS attacks.

## Table of Contents

1. [Why Rate Limiting](#why-rate-limiting)
2. [Rate Limiting Architecture](#rate-limiting-architecture)
3. [API Rate Limit Configuration](#api-rate-limit-configuration)
4. [Anti-Abuse Strategies](#anti-abuse-strategies)
5. [Implementation Examples](#implementation-examples)
6. [Monitoring and Maintenance](#monitoring-and-maintenance)
7. [Best Practices](#best-practices)

---

## Why Rate Limiting

Rate limiting is essential for:

- **Preventing DoS Attacks**: Stops attackers from flooding the system with requests
- **Resource Protection**: Prevents unbounded memory growth from rate limit tracking dictionaries
- **Fair Usage**: Ensures all users get equitable access to API resources
- **Cost Control**: Reduces infrastructure costs from processing malicious traffic
- **Security Layer**: Adds defense-in-depth alongside authentication and authorization

---

## Rate Limiting Architecture

### Core Components

1. **Per-IP Tracking**: Track requests by client IP address
2. **Bounded Storage**: Use LRU cache or TTL-based dictionaries (NOT unbounded plain dicts)
3. **Endpoint Classification**: Different limits for read vs write operations
4. **Automatic Cleanup**: Periodic removal of stale rate limit entries

### Data Flow

```
Client Request → IP Extraction → Rate Limit Check → Allow/Deny → Log → Response
                                           ↓
                                    Update Counter
                                           ↓
                                    Periodic Cleanup
```

---

## API Rate Limit Configuration

### Recommended Default Limits

| Endpoint Type | Method | Limit | Window |
|--------------|--------|-------|--------|
| Read endpoints | GET | 30 req/min | 60s |
| Write endpoints | POST/PATCH/DELETE | 10 req/min | 60s |
| Authentication | POST /auth/* | 5 req/min | 60s |
| Miner attestation | POST /attest/submit | 20 req/min | 60s |
| Admin operations | POST /wallet/transfer | 3 req/min | 60s |

### Configuration File Structure

```yaml
# config/rate_limits.yaml
rate_limiting:
  enabled: true
  
  # Storage backend
  storage:
    type: "memory"  # or "redis" for distributed setups
    max_entries: 10000
    cleanup_interval: 300  # seconds
    
  # Default limits
  defaults:
    read:
      requests: 30
      window_seconds: 60
    write:
      requests: 10
      window_seconds: 60
      
  # Endpoint-specific overrides
  endpoints:
    "/attest/submit":
      requests: 20
      window_seconds: 60
    "/wallet/transfer":
      requests: 3
      window_seconds: 60
    "/api/miners":
      requests: 60
      window_seconds: 60
      
  # IP extraction settings
  ip_extraction:
    trust_proxy_headers: false  # Set true only behind trusted reverse proxy
    header_priority:
      - "X-Real-IP"
      - "X-Forwarded-For"
      - "CF-Connecting-IP"
```

---

## Anti-Abuse Strategies

### 1. IP-Based Rate Limiting

**Implementation:**
```python
# Example: Bounded rate limiter with LRU cache
from collections import OrderedDict
import time
from typing import Dict, Tuple

class BoundedRateLimiter:
    def __init__(self, max_entries: int = 10000):
        self.limits: OrderedDict = OrderedDict()
        self.max_entries = max_entries
        
    def is_allowed(self, ip: str, limit: int, window: int) -> Tuple[bool, int]:
        now = time.time()
        window_start = now - window
        
        # Clean old entries for this IP
        if ip in self.limits:
            self.limits[ip] = [t for t in self.limits[ip] if t > window_start]
        else:
            self.limits[ip] = []
            
        # Check if under limit
        if len(self.limits[ip]) < limit:
            self.limits[ip].append(now)
            self.limits.move_to_end(ip)
            
            # Enforce max entries (LRU eviction)
            if len(self.limits) > self.max_entries:
                self.limits.popitem(last=False)
                
            return True, limit - len(self.limits[ip])
            
        return False, 0
        
    def cleanup_stale(self, max_age: int):
        """Remove entries older than max_age seconds"""
        cutoff = time.time() - max_age
        stale_ips = [ip for ip, timestamps in self.limits.items() 
                    if not timestamps or max(timestamps) < cutoff]
        for ip in stale_ips:
            del self.limits[ip]
```

### 2. Rate Limit Bypass Prevention

**X-Forwarded-For Spoofing Protection:**

```python
def extract_client_ip(request, trusted_proxy=False):
    """
    Extract real client IP while preventing spoofing
    
    Args:
        request: HTTP request object
        trusted_proxy: Only check proxy headers if behind trusted reverse proxy
    
    Returns:
        str: Client IP address
    """
    if trusted_proxy:
        # Check headers in priority order
        for header in ['X-Real-IP', 'X-Forwarded-For', 'CF-Connecting-IP']:
            if header in request.headers:
                # X-Forwarded-For can contain multiple IPs, take the first
                ip = request.headers[header].split(',')[0].strip()
                if ip:
                    return ip
    
    # Fallback to direct connection IP
    return request.remote_addr
```

**Key Security Measures:**

1. **Never trust proxy headers** unless behind a known, trusted reverse proxy
2. **Validate IP format** to prevent injection attacks
3. **Use connection IP** as fallback when headers are suspicious
4. **Log header anomalies** for security monitoring

### 3. Adaptive Rate Limiting

Implement progressive penalties for repeated violations:

```python
class AdaptiveRateLimiter:
    def __init__(self):
        self.violation_count: Dict[str, int] = {}
        self.ban_until: Dict[str, float] = {}
        
    def record_violation(self, ip: str):
        """Record a rate limit violation and escalate response"""
        self.violation_count[ip] = self.violation_count.get(ip, 0) + 1
        violations = self.violation_count[ip]
        
        # Progressive penalties
        if violations >= 10:
            # Permanent ban after 10 violations
            self.ban_until[ip] = float('inf')
        elif violations >= 5:
            # 24-hour ban after 5 violations
            self.ban_until[ip] = time.time() + 86400
        elif violations >= 3:
            # 1-hour ban after 3 violations
            self.ban_until[ip] = time.time() + 3600
            
    def is_banned(self, ip: str) -> Tuple[bool, str]:
        """Check if IP is currently banned"""
        if ip in self.ban_until:
            if self.ban_until[ip] == float('inf'):
                return True, "Permanent ban due to repeated violations"
            elif time.time() < self.ban_until[ip]:
                remaining = int(self.ban_until[ip] - time.time())
                return True, f"Temporary ban, {remaining}s remaining"
            else:
                # Ban expired, reset
                del self.ban_until[ip]
                self.violation_count[ip] = 0
                
        return False, ""
```

### 4. Request Fingerprinting

Beyond IP-based limiting, use multiple signals:

```python
def create_request_fingerprint(request):
    """
    Create a fingerprint for rate limiting based on multiple signals
    """
    import hashlib
    
    signals = [
        request.remote_addr,  # IP address
        request.headers.get('User-Agent', ''),  # User agent
        request.headers.get('Authorization', '')[:10],  # Auth token prefix
    ]
    
    fingerprint_data = '|'.join(signals)
    return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:16]
```

---

## Implementation Examples

### Example 1: Flask Middleware

```python
from flask import Flask, request, jsonify, g
from functools import wraps
import time

app = Flask(__name__)
rate_limiter = BoundedRateLimiter(max_entries=10000)

def rate_limit(limit_type: str = 'read'):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            client_ip = extract_client_ip(request, trusted_proxy=False)
            
            # Check if banned
            adaptive_limiter = getattr(app, 'adaptive_limiter', None)
            if adaptive_limiter:
                banned, reason = adaptive_limiter.is_banned(client_ip)
                if banned:
                    return jsonify({'error': reason}), 429
            
            # Get limits based on type
            limits = {
                'read': (30, 60),
                'write': (10, 60),
                'auth': (5, 60)
            }
            req_limit, window = limits.get(limit_type, (30, 60))
            
            # Check rate limit
            allowed, remaining = rate_limiter.is_allowed(client_ip, req_limit, window)
            
            # Add rate limit headers
            g.rate_limit_remaining = remaining
            g.rate_limit_reset = int(time.time()) + window
            
            if not allowed:
                # Record violation for adaptive limiting
                if adaptive_limiter:
                    adaptive_limiter.record_violation(client_ip)
                
                response = jsonify({
                    'error': 'Rate limit exceeded',
                    'retry_after': window
                })
                response.status_code = 429
                response.headers['X-RateLimit-Limit'] = str(req_limit)
                response.headers['X-RateLimit-Remaining'] = '0'
                response.headers['X-RateLimit-Reset'] = str(g.rate_limit_reset)
                response.headers['Retry-After'] = str(window)
                return response
            
            return f(*args, **kwargs)
        return wrapped
    return decorator

# Usage
@app.route('/api/miners', methods=['GET'])
@rate_limit('read')
def get_miners():
    return jsonify({'miners': [...]})

@app.route('/attest/submit', methods=['POST'])
@rate_limit('write')
def submit_attestation():
    # Process attestation
    return jsonify({'status': 'success'})

@app.after_request
def add_rate_limit_headers(response):
    if hasattr(g, 'rate_limit_remaining'):
        response.headers['X-RateLimit-Limit'] = str(30)
        response.headers['X-RateLimit-Remaining'] = str(g.rate_limit_remaining)
        response.headers['X-RateLimit-Reset'] = str(g.rate_limit_reset)
    return response
```

### Example 2: FastAPI Middleware

```python
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import time

app = FastAPI()
rate_limiter = BoundedRateLimiter(max_entries=10000)

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host
    
    # Extract IP from headers if behind proxy
    if 'X-Real-IP' in request.headers:
        client_ip = request.headers['X-Real-IP'].split(',')[0].strip()
    
    # Determine limit based on method
    if request.method in ['POST', 'PATCH', 'DELETE']:
        limit, window = 10, 60
    else:
        limit, window = 30, 60
    
    allowed, remaining = rate_limiter.is_allowed(client_ip, limit, window)
    
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "retry_after": window
            },
            headers={
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time()) + window),
                "Retry-After": str(window)
            }
        )
    
    response = await call_next(request)
    
    # Add rate limit headers to response
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(int(time.time()) + window)
    
    return response
```

### Example 3: Redis-Backed Distributed Rate Limiting

For production deployments across multiple nodes:

```python
import redis
import time

class RedisRateLimiter:
    def __init__(self, redis_client: redis.Redis, max_entries: int = 100000):
        self.redis = redis_client
        self.max_entries = max_entries
        
    def is_allowed(self, key: str, limit: int, window: int) -> tuple:
        """
        Use Redis sorted sets for distributed rate limiting
        """
        pipe = self.redis.pipeline()
        now = time.time()
        window_start = now - window
        
        # Remove old entries
        pipe.zremrangebyscore(key, 0, window_start)
        
        # Count current requests
        pipe.zcard(key)
        
        # Add current request
        pipe.zadd(key, {str(now): now})
        
        # Set expiry on the key
        pipe.expire(key, window * 2)
        
        results = pipe.execute()
        current_count = results[1]
        
        if current_count < limit:
            return True, limit - current_count - 1
        
        return False, 0
    
    def cleanup_stale(self, pattern: str = "ratelimit:*"):
        """Cleanup stale entries across all rate limit keys"""
        keys = self.redis.keys(pattern)
        for key in keys:
            ttl = self.redis.ttl(key)
            if ttl == -1:  # No expiry set
                self.redis.expire(key, 3600)
```

---

## Monitoring and Maintenance

### Key Metrics to Track

1. **Rate Limit Hits**: Number of requests blocked by rate limiting
2. **Top Offenders**: IPs with most rate limit violations
3. **Endpoint Distribution**: Which endpoints hit rate limits most
4. **False Positives**: Legitimate users hitting rate limits
5. **Memory Usage**: Rate limit storage size

### Monitoring Dashboard Example

```python
# Prometheus metrics for rate limiting
from prometheus_client import Counter, Histogram, Gauge

rate_limit_hits = Counter(
    'rate_limit_hits_total',
    'Total number of rate limit hits',
    ['endpoint', 'client_ip_subnet']
)

rate_limit_storage_size = Gauge(
    'rate_limit_storage_entries',
    'Current number of entries in rate limit storage'
)

def record_rate_limit_hit(endpoint: str, client_ip: str):
    # Anonymize IP for privacy (use /24 subnet)
    ip_subnet = '.'.join(client_ip.split('.')[:3]) + '.0/24'
    rate_limit_hits.labels(endpoint=endpoint, client_ip_subnet=ip_subnet).inc()
```

### Regular Maintenance Tasks

**Daily:**
- Review rate limit hit logs for anomalies
- Check for false positives from legitimate users

**Weekly:**
- Analyze rate limit effectiveness
- Adjust limits based on traffic patterns
- Review banned IP list

**Monthly:**
- Audit rate limit configuration
- Test rate limit bypass attempts
- Update documentation

### Log Format

```json
{
  "timestamp": "2026-03-12T11:55:00Z",
  "event": "rate_limit_exceeded",
  "client_ip": "192.168.1.100",
  "endpoint": "/attest/submit",
  "method": "POST",
  "limit": 10,
  "window_seconds": 60,
  "request_count": 15,
  "user_agent": "Mozilla/5.0...",
  "action_taken": "request_blocked"
}
```

---

## Best Practices

### DO ✅

1. **Use bounded storage** - Always use LRU cache or TTL-based dictionaries
2. **Implement periodic cleanup** - Remove stale entries automatically
3. **Set reasonable defaults** - 30 req/min for reads, 10 req/min for writes
4. **Log rate limit events** - For security monitoring and debugging
5. **Return proper HTTP headers** - X-RateLimit-*, Retry-After
6. **Use adaptive limiting** - Escalate penalties for repeat offenders
7. **Test bypass attempts** - Regularly test for X-Forwarded-For spoofing
8. **Document limits publicly** - Help developers stay within limits

### DON'T ❌

1. **Don't use unbounded dictionaries** - They grow forever and cause memory issues
2. **Don't trust proxy headers blindly** - Only when behind trusted reverse proxy
3. **Don't set limits too low** - Will block legitimate users
4. **Don't hide rate limit info** - Provide clear feedback to clients
5. **Don't forget cleanup** - Stale entries waste memory
6. **Don't rate limit health checks** - Exclude monitoring endpoints
7. **Don't use IP alone for auth endpoints** - Combine with other signals

### Response Headers

Always include these headers in responses:

```
X-RateLimit-Limit: 30
X-RateLimit-Remaining: 25
X-RateLimit-Reset: 1710244500
Retry-After: 60  # Only on 429 responses
```

### Error Response Format

```json
{
  "error": "Rate limit exceeded",
  "message": "You have made too many requests. Please retry after 60 seconds.",
  "retry_after": 60,
  "limit": 30,
  "window_seconds": 60
}
```

---

## Testing Rate Limiting

### Unit Test Example

```python
import unittest
import time

class TestRateLimiter(unittest.TestCase):
    def setUp(self):
        self.limiter = BoundedRateLimiter(max_entries=100)
        
    def test_basic_rate_limiting(self):
        ip = "192.168.1.1"
        limit = 5
        window = 60
        
        # Should allow first 5 requests
        for i in range(5):
            allowed, remaining = self.limiter.is_allowed(ip, limit, window)
            self.assertTrue(allowed)
            self.assertEqual(remaining, 5 - i - 1)
        
        # 6th request should be denied
        allowed, remaining = self.limiter.is_allowed(ip, limit, window)
        self.assertFalse(allowed)
        self.assertEqual(remaining, 0)
        
    def test_window_reset(self):
        ip = "192.168.1.2"
        limit = 2
        window = 1  # 1 second window for testing
        
        # Hit the limit
        self.limiter.is_allowed(ip, limit, window)
        self.limiter.is_allowed(ip, limit, window)
        allowed, _ = self.limiter.is_allowed(ip, limit, window)
        self.assertFalse(allowed)
        
        # Wait for window to expire
        time.sleep(1.1)
        
        # Should be allowed again
        allowed, _ = self.limiter.is_allowed(ip, limit, window)
        self.assertTrue(allowed)
        
    def test_max_entries_enforcement(self):
        limiter = BoundedRateLimiter(max_entries=10)
        
        # Add 15 different IPs
        for i in range(15):
            ip = f"192.168.1.{i}"
            limiter.is_allowed(ip, 100, 60)
        
        # Should only keep 10 entries
        self.assertLessEqual(len(limiter.limits), 10)
```

### Integration Testing

```bash
# Test rate limiting with curl
for i in {1..15}; do
  curl -s -o /dev/null -w "Request $i: %{http_code}\n" \
    -H "X-Forwarded-For: 192.168.1.100" \
    http://localhost:8080/api/miners
done

# Expected: First 30 return 200, then 429
```

---

## Troubleshooting

### Common Issues

**Issue: Rate limits too aggressive**
- **Symptom**: Legitimate users getting blocked
- **Solution**: Increase limits, implement user authentication for higher limits

**Issue: Memory growth**
- **Symptom**: Server memory increasing over time
- **Solution**: Ensure bounded storage and periodic cleanup are implemented

**Issue: Rate limit bypass**
- **Symptom**: Same user making unlimited requests
- **Solution**: Check proxy header handling, implement request fingerprinting

**Issue: Distributed inconsistency**
- **Symptom**: Rate limits not enforced across multiple nodes
- **Solution**: Use Redis-backed rate limiting for shared state

---

## Security Considerations

### Attack Vectors

1. **IP Rotation**: Attackers using multiple IPs
   - **Mitigation**: Combine with user authentication, device fingerprinting

2. **Distributed Attacks**: Botnets with many IPs
   - **Mitigation**: Use WAF, behavioral analysis, CAPTCHA for suspicious traffic

3. **Header Spoofing**: Fake X-Forwarded-For headers
   - **Mitigation**: Only trust headers from known reverse proxies

4. **Slowloris Attacks**: Many slow connections
   - **Mitigation**: Connection timeouts, request body size limits

### Defense in Depth

Rate limiting is one layer. Combine with:

- Authentication and authorization
- Input validation
- WAF (Web Application Firewall)
- DDoS protection services (Cloudflare, etc.)
- Request signing for critical operations

---

## Conclusion

Proper rate limiting is essential for protecting RustChain APIs from abuse and ensuring fair access for all users. This guide provides the foundation for implementing robust rate limiting with:

- Bounded storage to prevent memory issues
- Configurable limits per endpoint type
- Anti-bypass measures for production security
- Monitoring and maintenance procedures
- Testing strategies to verify effectiveness

For questions or issues, please open a GitHub issue in the rustchain-bounties repository.

---

## References

- [OWASP Rate Limiting Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Rate_Limiting_Cheat_Sheet.html)
- [RFC 6585 - Additional HTTP Status Codes](https://tools.ietf.org/html/rfc6585)
- [RustChain Issue #389 - Add rate limiting to Atlas API endpoints](https://github.com/Scottcjn/rustchain-bounties/issues/389)
- [RustChain Issue #57 - Red Team: API Authentication & Rate Limiting](https://github.com/Scottcjn/rustchain-bounties/issues/57)
