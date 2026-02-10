#!/usr/bin/env python3
"""
RustChain Server Proxy - Port 8089
Allows G4 to connect via different port
"""

from flask import Flask, request, jsonify
from node.agent_registration import register_agent
import requests
import json

app = Flask(__name__)

# Local server on same machine
LOCAL_SERVER = "http://localhost:8088"

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

        # Return the response from local server
        return response.json(), response.status_code

    except requests.exceptions.Timeout:
        return jsonify({'error': 'Local server timeout'}), 504
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/register_agent', methods=['POST'])
def register_agent_route():
    """Register an AI agent and its hardware binding."""
    if not request.json:
        return jsonify({'error': 'Missing JSON payload'}), 400
    
    success, reason, details = register_agent(request.json)
    
    if success:
        return jsonify({'status': 'ok', 'reason': reason, 'details': details}), 200
    else:
        # 409 Conflict if hardware is already bound, 400 for bad data
        status_code = 409 if 'bound' in reason or 'collision' in reason else 400
        return jsonify({'status': 'error', 'reason': reason, 'details': details}), status_code

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
        'endpoints': ['/api/register', '/api/mine', '/api/stats', '/api/register_agent', '/status']
    })

if __name__ == '__main__':
    print(f"Starting RustChain proxy on port 8089...")
    print(f"Forwarding to: {LOCAL_SERVER}")
    print(f"G4 can connect to: http://50.28.86.131:8089")
    app.run(host='0.0.0.0', port=8089, debug=False)