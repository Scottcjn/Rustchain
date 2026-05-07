#!/usr/bin/env python3
"""
RustChain Epoch Visualizer Server
Serves static files and proxies API requests to bypass CORS
"""

import http.server
import json
import re
import urllib.request
import urllib.error
from pathlib import Path

NODE_URL = "https://50.28.86.131"
PORT = 8888

# Allowed API path patterns (prevent SSRF)
ALLOWED_PATHS = re.compile(r"^/(?:api/(?:epoch|block|status|reputation)|epoch)$")

class ProxyHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # Proxy API requests
        if self.path.startswith('/api/') or self.path == '/epoch':
            self.proxy_request(self.path)
        else:
            # Serve static files
            super().do_GET()
    
    def proxy_request(self, path):
        """Proxy request to RustChain node with SSRF protection"""
        import ssl
        
        # SSRF protection: validate path
        if not ALLOWED_PATHS.match(path):
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid API path"}).encode())
            return
        
        # Strip query strings for path validation but pass through
        clean_path = path.split('?')[0]
        if not ALLOWED_PATHS.match(clean_path):
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid API path"}).encode())
            return
        
        url = f"{NODE_URL}{path}"
        try:
            # Proper SSL verification (no CERT_NONE)
            ctx = ssl.create_default_context()
            
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                data = resp.read()
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.URLError as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def end_headers(self):
        # Add CORS headers to all responses
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

if __name__ == '__main__':
    import os
    os.chdir(Path(__file__).parent)
    
    with http.server.HTTPServer(('', PORT), ProxyHandler) as httpd:
        print(f"Server running on port {PORT}")
        httpd.serve_forever()
