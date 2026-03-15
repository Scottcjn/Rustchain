#!/usr/bin/env python3
"""RustChain Mock API Server — For local development and testing."""
import json, http.server, os
MOCK_DATA = {
    "/health": {"status": "ok", "version": "2.2.1-mock", "uptime": "24h"},
    "/epoch": {"epoch": 100, "slot": 42, "enrolled_miners": 3, "epoch_pot": 5.0, "total_supply": 10000},
    "/api/miners": [{"miner_id": "mock-1", "hardware": "x86-64", "antiquity_multiplier": 1.0}],
    "/headers/tip": {"height": 4200, "slot": 42},
    "/api/fee_pool": {"fee_pool": 12.5},
    "/api/stats": {"total_blocks": 4200, "active_miners": 3},
}
class MockHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?")[0]
        data = MOCK_DATA.get(path, {"error": "not found"})
        self.send_response(200 if path in MOCK_DATA else 404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    def log_message(self, *a): pass
if __name__ == "__main__":
    port = int(os.environ.get("MOCK_PORT", "8088"))
    print(f"Mock RustChain API on :{port}")
    http.server.HTTPServer(("", port), MockHandler).serve_forever()
