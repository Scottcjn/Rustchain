#!/usr/bin/env python3
"""
RustChain Epoch Visualizer Server
Serves static files and proxies API requests to bypass CORS
"""

import http.server
import json
import urllib.request
import urllib.error
from pathlib import Path

NODE_URL = "https://50.28.86.131"
PORT = 8888

class ProxyHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # Proxy API requests
        if self.path.startswith('/api/'):
            self.proxy_request(self.path)
        elif self.path == '/epoch':
            self.proxy_request('/epoch')
        else:
            # Serve static files
            super().do_GET()
    
    def proxy_request(self, path):
        """Proxy request to RustChain node"""
        import ssl
        url = f"{NODE_URL}{path}"
        try:
            # Create SSL context that ignores certificate verification
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            
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
        print(f"🌐 Server running at http://localhost:{PORT}")
        print(f"📡 Proxying API to {NODE_URL}")
        httpd.serve_forever()
