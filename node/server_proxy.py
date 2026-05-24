#!/usr/bin/env python3
"""
RustChain Server Proxy - Port 8089
Allows G4 to connect via different port
"""

from flask import Flask, request, jsonify
import requests
from urllib.parse import quote

app = Flask(__name__)

# Local server on same machine
LOCAL_SERVER = "http://localhost:8088"


def _generic_upstream_error(response, reason):
    """Hide upstream failure details from public proxy clients."""
    app.logger.warning(
        "RustChain proxy upstream %s: status=%s content_type=%r body=%r",
        reason,
        getattr(response, "status_code", None),
        getattr(response, "headers", {}).get("Content-Type", ""),
        getattr(response, "text", "")[:1000],
    )
    return jsonify({'error': 'Local server unavailable'}), 502


def _build_local_api_url(path):
    """Return a local /api URL without allowing dot-segment escapes."""
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return None
    safe_path = "/".join(quote(part, safe="") for part in parts)
    return f"{LOCAL_SERVER}/api/{safe_path}"

@app.route('/api/<path:path>', methods=['GET', 'POST'])
def proxy(path):
    """Forward all API requests to local server"""
    url = _build_local_api_url(path)
    if not url:
        return jsonify({'error': 'Invalid API path'}), 400

    try:
        # SECURITY: Forward auth and identity headers to preserve admin checks
        # on the backend. Without these, requests through the proxy bypass
        # admin authentication on all protected endpoints.
        SAFE_HEADERS = (
            'content-type', 'accept', 'authorization',
            'x-admin-key', 'x-api-key', 'x-agent-id', 'x-agent-key',
            'x-agent-signature', 'x-agent-pubkey', 'x-agent-timestamp',
            'x-agent-nonce',
        )
        forward_headers = {
            k: v for k, v in request.headers.items()
            if k.lower() in SAFE_HEADERS
        }

        if request.method == 'POST':
            # Forward POST requests with JSON data
            response = requests.post(
                url,
                json=request.json,
                headers=forward_headers,
                timeout=10
            )
        else:
            # Forward GET requests with auth headers
            response = requests.get(url, headers=forward_headers, timeout=10)

        # Return the response from local server
        if response.status_code >= 500:
            return _generic_upstream_error(response, "error response")

        # Safely handle non-JSON responses from upstream
        content_type = response.headers.get('Content-Type', '')
        if 'application/json' in content_type:
            try:
                return response.json(), response.status_code
            except ValueError:
                return _generic_upstream_error(response, "invalid json")
        if response.status_code >= 400:
            return _generic_upstream_error(response, "non-json error response")

        # Successful non-JSON response (for example, plain health text).
        return response.text, response.status_code

    except requests.exceptions.Timeout:
        return jsonify({'error': 'Local server timeout'}), 504
    except Exception:
        app.logger.exception("RustChain proxy upstream request failed")
        return jsonify({'error': 'Local server unavailable'}), 502

@app.route('/status')
def status():
    """Proxy status"""
    return jsonify({
        'proxy': 'active',
        'local_server': LOCAL_SERVER,
        'message': 'RustChain proxy for vintage hardware'
    })

@app.route('/')
def home():
    return jsonify({
        'service': 'RustChain G4 Proxy',
        'endpoints': ['/api/register', '/api/mine', '/api/stats', '/status']
    })

if __name__ == '__main__':
    print("Starting RustChain proxy on port 8089...")
    print(f"Forwarding to: {LOCAL_SERVER}")
    print("G4 can connect to: https://rustchain.org:8089")
    app.run(host='0.0.0.0', port=8089, debug=False)
