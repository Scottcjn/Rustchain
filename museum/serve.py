#!/usr/bin/env python3
"""
Simple static file server for the Vintage Hardware Museum.
Usage: python3 serve.py [port]
Then open http://localhost:8080 in a browser.
"""

import http.server
import socketserver
import sys
import os

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
DIRECTORY = os.path.dirname(os.path.abspath(__file__))


class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Serve files with CORS headers enabled."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} - {fmt % args}")


def main():
    os.chdir(DIRECTORY)
    with socketserver.TCPServer(("", PORT), CORSRequestHandler) as httpd:
        httpd.allow_reuse_address = True
        print(f"")
        print(f"  ╔══════════════════════════════════════════╗")
        print(f"  ║  Elyan Labs Vintage Hardware Museum      ║")
        print(f"  ║  Serving on http://localhost:{PORT}         ║")
        print(f"  ║  Press Ctrl+C to stop                    ║")
        print(f"  ╚══════════════════════════════════════════╝")
        print(f"")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  Server stopped.")


if __name__ == '__main__':
    main()
