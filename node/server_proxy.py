#!/usr/bin/env python3
"""
RustChain Server Proxy - Port 8089
Allows G4 to connect via different port
"""

from flask import Flask, Response, request, jsonify
import requests

app = Flask(__name__)

# Local server on same machine
LOCAL_SERVER = "http://localhost:8088"


def _forward_upstream_response(response):
    """Return upstream responses without crashing on non-JSON bodies."""
    content_type = response.headers.get('Content-Type', '')
    if 'application/json' in content_type.lower():
        try:
            return jsonify(response.json()), response.status_code
        except ValueError:
            return Response(
                response.text,
                status=response.status_code,
                content_type='text/plain; charset=utf-8',
            )

    return Response(
        response.text,
        status=response.status_code,
        content_type=content_type or 'text/plain; charset=utf-8',
    )


@app.route('/api/<path:path>', methods=['GET', 'POST'])
def proxy(path):
    """Forward all API requests to local server"""
    url = f"{LOCAL_SERVER}/api/{path}"

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

        return _forward_upstream_response(response)

    except requests.exceptions.Timeout:
        return jsonify({'error': 'Local server timeout'}), 504
    except requests.exceptions.RequestException:
        return jsonify({'error': 'Local server request failed'}), 502
    except Exception:
        app.logger.exception("Proxy request failed")
        return jsonify({'error': 'Proxy request failed'}), 500

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
