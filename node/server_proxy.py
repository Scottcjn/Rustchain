#!/usr/bin/env python3
"""
RustChain Server Proxy - Port 8089
Allows G4 to connect via different port
"""

from flask import Flask, request, jsonify
import requests
import json
import logging

app = Flask(__name__)
logger = logging.getLogger(__name__)

# Local server on same machine
LOCAL_SERVER = "http://localhost:8088"

ALLOWED_PROXY_ROUTES = {
    ("GET", "stats"),
    ("GET", "miners"),
    ("GET", "wallet/balance"),
    ("POST", "register"),
    ("POST", "mine"),
}


def _normalize_proxy_path(path):
    """Normalize and reject path traversal before proxying."""
    normalized = (path or "").strip().strip("/")
    if not normalized or "\\" in normalized:
        return None
    parts = [part for part in normalized.split("/") if part]
    if any(part in {".", ".."} for part in parts):
        return None
    return "/".join(parts)


def _is_allowed_proxy_route(method, path):
    """Return True only for explicitly supported public proxy routes."""
    return (method.upper(), path) in ALLOWED_PROXY_ROUTES


@app.route('/api/<path:path>', methods=['GET', 'POST'])
def proxy(path):
    """Forward only explicitly allowlisted public API requests."""
    normalized_path = _normalize_proxy_path(path)
    if not normalized_path or not _is_allowed_proxy_route(request.method, normalized_path):
        return jsonify({'error': 'Proxy path not allowed'}), 403

    url = f"{LOCAL_SERVER}/api/{normalized_path}"

    try:
        if request.method == 'POST':
            payload = request.get_json(silent=True)
            if payload is None:
                return jsonify({'error': 'JSON object required'}), 400

            # Forward POST requests with JSON data
            headers = {'Content-Type': 'application/json'}
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=10
            )
        else:
            # Forward GET requests
            response = requests.get(
                url,
                params=request.args,
                timeout=10
            )

        # Return the response from local server
        # Safely handle non-JSON responses from upstream
        content_type = response.headers.get('Content-Type', '')
        if 'application/json' in content_type:
            try:
                return response.json(), response.status_code
            except (ValueError, Exception):
                # JSON parse failed, fall back to text
                return response.text, response.status_code
        else:
            # Non-JSON response (e.g., HTML error page), return as-is with text
            return response.text, response.status_code

    except requests.exceptions.Timeout:
        return jsonify({'error': 'Local server timeout'}), 504
    except Exception as e:
        logger.warning("Local proxy request failed for %s %s: %s", request.method, normalized_path, e)
        return jsonify({'error': 'Local server proxy error'}), 502

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
    print(f"Starting RustChain proxy on port 8089...")
    print(f"Forwarding to: {LOCAL_SERVER}")
    print(f"G4 can connect to: https://rustchain.org:8089")
    app.run(host='0.0.0.0', port=8089, debug=False)
