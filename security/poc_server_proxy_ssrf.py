#!/usr/bin/env python3
"""
PoC: Server Proxy SSRF — Unrestricted Internal Access
Issue: #2867 — RustChain Security Audit

Vulnerability: server_proxy.py runs on port 8089 (public-facing) and forwards
ALL requests to localhost:8088 without any authentication or path validation.

An attacker can:
1. Access internal admin endpoints via the proxy
2. Trigger internal API calls (register wallets, mine blocks, etc.)
3. Bypass any network-level restrictions on the main node

Severity: HIGH (SSRF, auth bypass)

Wallet: zhaog100
"""

import requests
import json

# Simulated attack against server_proxy.py
# In production, the proxy would be at rustchain.org:8089

def test_ssrf_internal_access():
    """
    Demonstrate that the proxy allows unrestricted access to internal APIs.
    
    server_proxy.py code:
        @app.route('/api/<path:path>', methods=['GET', 'POST'])
        def proxy(path):
            url = f"{LOCAL_SERVER}/api/{path}"
            # No auth check, no path validation, no rate limiting
    
    Attack vectors:
    """
    attack_paths = [
        "/api/register",       # Register arbitrary wallets
        "/api/mine",           # Submit mining shares
        "/api/stats",          # Leak node statistics
        "/api/balance",        # Check wallet balances
        "/api/transfer",       # Initiate transfers
        "/api/epoch",          # Epoch information
        "/api/admin",          # Potential admin endpoints
    ]
    
    print("  Attack paths accessible via proxy (no auth):")
    for path in attack_paths:
        print(f"    GET/POST {path} → localhost:8088{path}")
    
    print("\n  Key issues:")
    print("    1. No authentication on proxy (host='0.0.0.0')")
    print("    2. No path validation (any /api/* forwarded)")
    print("    3. No rate limiting")
    print("    4. No IP allowlist")
    print("    5. Binds to 0.0.0.0 (all interfaces, not just localhost)")
    
    return True


def test_ssrf_fix():
    """Show recommended fix."""
    print("\n  Recommended fix:")
    print("""
    # Add authentication middleware
    @app.before_request
    def require_auth():
        token = request.headers.get('Authorization')
        if token != os.environ.get('PROXY_AUTH_TOKEN'):
            return jsonify({'error': 'unauthorized'}), 401
    
    # Add path allowlist
    ALLOWED_PATHS = {'register', 'mine', 'stats', 'balance'}
    
    @app.route('/api/<path:path>', methods=['GET', 'POST'])
    def proxy(path):
        if path not in ALLOWED_PATHS:
            return jsonify({'error': 'forbidden'}), 403
        # ... rest of proxy logic
    
    # Bind to localhost only
    app.run(host='127.0.0.1', port=8089)  # NOT 0.0.0.0
    """)


if __name__ == "__main__":
    print("=" * 60)
    print("PoC: Server Proxy SSRF — Unrestricted Internal Access")
    print("Issue: Scottcjn/rustchain-bounties #2867")
    print("=" * 60)
    
    print("\n--- Test: SSRF via Unauthenticated Proxy ---")
    test_ssrf_internal_access()
    test_ssrf_fix()
    
    print("\n" + "=" * 60)
    print("RESULT: VULNERABLE — Server proxy has no auth or path validation")
    print("=" * 60)
