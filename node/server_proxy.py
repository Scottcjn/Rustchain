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

def _build_local_api_url(path):
    """Return a local /api URL without allowing dot-segment escapes."""
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return None
    safe_path = "/".join(quote(part, safe="") for part in parts)
    return f"{LOCAL_SERVER}/api/{safe_path}"


def _relay_upstream_response(response):
    """Relay upstream responses without exposing internal 5xx details."""
    if response.status_code >= 500:
        app.logger.warning("Upstream server returned %s for proxied request", response.status_code)
        return jsonify({'error': 'Upstream server error'}), 502

    content_type = response.headers.get('Content-Type', '')
    if 'application/json' in content_type:
        try:
            return jsonify(response.json()), response.status_code
        except ValueError:
            app.logger.warning("Upstream server returned invalid JSON with JSON content type")
            return jsonify({'error': 'Invalid upstream JSON response'}), 502

    return response.text, response.status_code

@app.route('/api/<path:path>', methods=['GET', 'POST'])
def proxy(path):
    """Forward all API requests to local server"""
    url = _build_local_api_url(path)
    if not url:
        return jsonify({'error': 'Invalid API path'}), 400

    try:
        if request.method == 'POST':
            # Forward POST requests with JSON data
            headers = {'Content-Type': 'application/json'}
            response = requests.post(
                url,
                json=request.json,
                headers=headers,
                timeout=10
            )
        else:
            # Forward GET requests
            response = requests.get(url, timeout=10)

        return _relay_upstream_response(response)

    except requests.exceptions.Timeout:
        return jsonify({'error': 'Local server timeout'}), 504
    except requests.exceptions.RequestException:
        app.logger.warning("Local server request failed", exc_info=True)
        return jsonify({'error': 'Local server unavailable'}), 502
    except Exception:
        app.logger.exception("Unexpected proxy error")
        return jsonify({'error': 'Proxy error'}), 500

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
