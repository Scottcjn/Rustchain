#!/usr/bin/env python3
"""
RustChain Explorer - Tier 2 + Tier 3 Features Server
Serves static SPA with proxy to RustChain API endpoints
Includes: Charts, Advanced Analytics, Real-time Updates
"""

import os
import json
import time
import requests
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, quote, unquote
from datetime import datetime

# Configuration
EXPLORER_PORT = int(os.environ.get('EXPLORER_PORT', 8080))
API_BASE = os.environ.get('RUSTCHAIN_API_BASE', 'https://rustchain.org').rstrip('/')
API_TIMEOUT = float(os.environ.get('API_TIMEOUT', '8'))
STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static')
ALLOWED_PROXY_ENDPOINTS = {
    ('health',),
    ('epoch',),
    ('api', 'miners'),
    ('blocks',),
    ('api', 'transactions'),
    ('hall', 'leaderboard'),
}


def normalize_proxy_endpoint(endpoint):
    """Return allowed endpoint segments or None for paths the Explorer never uses."""
    if not endpoint:
        return None

    segments = []
    for raw_segment in endpoint.split('/'):
        if not raw_segment:
            return None
        segment = unquote(raw_segment)
        if segment in {'.', '..'} or '/' in segment or '\\' in segment:
            return None
        segments.append(segment)

    segments = tuple(segments)
    if segments not in ALLOWED_PROXY_ENDPOINTS:
        return None
    return segments


def build_proxy_url(api_base, segments):
    encoded_path = '/'.join(quote(segment, safe='') for segment in segments)
    return f"{api_base.rstrip('/')}/{encoded_path}"

class ExplorerHandler(SimpleHTTPRequestHandler):
    """Custom HTTP handler with API proxy and caching"""
    
    # Cache for API responses
    _cache = {}
    _cache_ttl = 10  # seconds
    
    def do_GET(self):
        """Handle GET requests"""
        parsed = urlparse(self.path)
        path = parsed.path
        
        # API proxy endpoints
        if path.startswith('/api/proxy/'):
            self.handle_proxy(path[len('/api/proxy/'):], parsed)
            return
        
        # Health check for explorer itself
        if path == '/explorer-health':
            self.send_json({
                'status': 'ok',
                'version': '1.0.0',
                'timestamp': int(time.time()),
                'api_base': API_BASE
            })
            return
        
        # Serve static files
        if path == '/':
            self.path = '/explorer/index.html'
        elif path.startswith('/static/'):
            pass  # Serve as-is
        elif path == '/explorer':
            self.path = '/explorer/index.html'
        else:
            # Try to serve from explorer directory
            explorer_path = os.path.join(os.path.dirname(__file__), path.lstrip('/'))
            if os.path.isfile(explorer_path):
                self.path = path
            else:
                self.path = '/explorer/index.html'
        
        return super().do_GET()
    
    def handle_proxy(self, endpoint, parsed):
        """Proxy requests to RustChain API with caching"""
        segments = normalize_proxy_endpoint(endpoint)
        if segments is None:
            self.send_error_json(404, 'Not Found')
            return

        endpoint_path = '/'.join(segments)
        cache_key = f"{endpoint_path}:{parsed.query}"
        
        # Check cache
        cached = self._cache.get(cache_key)
        if cached and (time.time() - cached['time']) < self._cache_ttl:
            self.send_json(cached['data'], headers={'X-Cache': 'HIT'})
            return
        
        # Fetch from API
        try:
            url = build_proxy_url(API_BASE, segments)
            params = parse_qs(parsed.query, keep_blank_values=True) if parsed.query else None
            
            response = requests.get(url, params=params, timeout=API_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            
            # Cache response
            self._cache[cache_key] = {
                'data': data,
                'time': time.time()
            }
            
            self.send_json(data, headers={'X-Cache': 'MISS'})
        except requests.exceptions.Timeout:
            self.send_error_json(504, 'Gateway Timeout')
        except requests.exceptions.RequestException:
            self.send_error_json(502, 'Bad Gateway')
        except json.JSONDecodeError:
            self.send_error_json(502, 'Invalid JSON from upstream')
    
    def send_json(self, data, status=200, headers=None):
        """Send JSON response"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        if headers:
            for key, value in headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def send_error_json(self, status, message):
        """Send JSON error response"""
        self.send_json({
            'error': True,
            'status': status,
            'message': message,
            'timestamp': int(time.time())
        }, status=status)
    
    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()
    
    def log_message(self, format, *args):
        """Custom log format"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {args[0]}")


def get_analytics_data():
    """Fetch comprehensive analytics data"""
    endpoints = [
        '/health',
        '/epoch',
        '/api/miners',
        '/blocks',
        '/api/transactions'
    ]
    
    results = {}
    with requests.Session() as session:
        for endpoint in endpoints:
            try:
                response = session.get(f"{API_BASE}{endpoint}", timeout=API_TIMEOUT)
                response.raise_for_status()
                results[endpoint] = response.json()
            except Exception as e:
                results[endpoint] = {'error': str(e)}
    
    return results


def main():
    """Start the explorer server"""
    server_address = ('', EXPLORER_PORT)
    httpd = HTTPServer(server_address, ExplorerHandler)
    
    print(f"""
╔══════════════════════════════════════════════════════════╗
║           RustChain Explorer Server                      ║
╠══════════════════════════════════════════════════════════╣
║  Serving at: http://localhost:{EXPLORER_PORT}                  ║
║  API Base: {API_BASE}                    ║
║  Static: {STATIC_DIR}                           ║
║                                                          ║
║  Tier 1: Blocks, Miners, Epoch                           ║
║  Tier 2: Transactions, Search, Analytics                 ║
║  Tier 3: Hall of Rust, Real-time Updates                 ║
╚══════════════════════════════════════════════════════════╝
    
    Press Ctrl+C to stop
    """)
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down explorer server...")
        httpd.shutdown()


if __name__ == '__main__':
    main()
