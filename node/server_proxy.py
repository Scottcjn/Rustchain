#!/usr/bin/env python3
"""
RustChain Server Proxy - Port 8089
Allows G4 to connect via different port
"""

from flask import Flask, request, jsonify
import requests
import json
from urllib.parse import quote

app = Flask(__name__)

# Local server on same machine
LOCAL_SERVER = "http://localhost:8088"

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
    query_params = request.args.to_dict(flat=False)
    request_kwargs = {"timeout": 10}
    if query_params:
        request_kwargs["params"] = query_params

    try:
        if request.method == 'POST':
            # Forward POST requests with JSON data
            headers = {'Content-Type': 'application/json'}
            response = requests.post(
                url,
                json=request.json,
                headers=headers,
                **request_kwargs
            )
        else:
            # Forward GET requests
            response = requests.get(url, **request_kwargs)

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
