#!/usr/bin/env python3
"""
RustChain Server Proxy - Port 8089
Allows G4 to connect via different port

Usage:
    python3 server_proxy.py

Endpoints:
    /api/<path> - Forward to local server (port 8088)
    /status     - Proxy status
    /           - Service info
"""

from __future__ import annotations

from typing import Any, Dict, Tuple
from flask import Flask, request, jsonify, Response
import requests
import json

app = Flask(__name__)

# Local server on same machine
LOCAL_SERVER: str = "http://localhost:8088"


@app.route('/api/<path:path>', methods=['GET', 'POST'])
def proxy(path: str) -> Tuple[Dict[str, Any], int]:
    """
    Forward all API requests to local server.
    
    Args:
        path: API path to forward (e.g., 'register', 'mine', 'stats')
    
    Returns:
        Tuple[dict, int]: (response_data, status_code)
    
    Errors:
        504: Local server timeout
        500: Other errors
    """
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
        return {'error': 'Local server timeout'}, 504
    except Exception as e:
        return {'error': str(e)}, 500


@app.route('/status')
def status() -> Tuple[Dict[str, str], int]:
    """
    Get proxy status.
    
    Returns:
        Tuple[dict, int]: Status info with proxy state and local server URL
    """
    return {
        'proxy': 'active',
        'local_server': LOCAL_SERVER,
        'message': 'RustChain proxy for vintage hardware'
    }, 200


@app.route('/')
def home() -> Tuple[Dict[str, Any], int]:
    """
    Get service info and available endpoints.
    
    Returns:
        Tuple[dict, int]: Service name and endpoint list
    """
    return {
        'service': 'RustChain G4 Proxy',
        'endpoints': ['/api/register', '/api/mine', '/api/stats', '/status']
    }, 200


if __name__ == '__main__':
    print(f"Starting RustChain proxy on port 8089...")
    print(f"Forwarding to: {LOCAL_SERVER}")
    print(f"G4 can connect to: https://rustchain.org:8089")
    app.run(host='0.0.0.0', port=8089, debug=False)