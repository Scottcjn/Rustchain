#!/usr/bin/env python3
"""
RustChain Server Proxy - Port 8089
Allows G4 to connect via different port
"""

from flask import Flask, request, jsonify
import requests
import json

app = Flask(__name__)

# Local server on same machine
LOCAL_SERVER = "http://localhost:8088"

@app.route('/api/<path:path>', methods=['GET', 'POST'])
def proxy(path):
    """Forward all API requests to local server with security headers"""
    # FIX: Whitelist endpoints to prevent SSRF or access to internal metrics
    ALLOWED_PATHS = {'register', 'mine', 'stats', 'balance', 'blocks', 'transactions'}
    base_path = path.split('/')[0]
    if base_path not in ALLOWED_PATHS:
        return jsonify({'error': 'Forbidden endpoint'}), 403

    url = f"{LOCAL_SERVER}/api/{path}"

    # Forward relevant headers for IP tracking and auth
    headers = {
        'X-Forwarded-For': request.remote_addr,
        'User-Agent': request.headers.get('User-Agent', 'RustChain-Proxy'),
        'Content-Type': 'application/json'
    }

    # Forward authentication if present
    if 'Authorization' in request.headers:
        headers['Authorization'] = request.headers['Authorization']

    try:
        if request.method == 'POST':
            response = requests.post(
                url,
                json=request.json,
                headers=headers,
                timeout=15
            )
        else:
            response = requests.get(url, headers=headers, timeout=15)

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
        return jsonify({'error': str(e)}), 500

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