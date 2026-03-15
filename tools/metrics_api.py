#!/usr/bin/env python3
"""RustChain Metrics API — Aggregate node metrics into a single JSON endpoint."""
import json, urllib.request, ssl, os, http.server

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")

def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try: return json.loads(urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx).read())
    except: return {}

def aggregate():
    h = api("/health"); e = api("/epoch"); m = api("/api/miners"); t = api("/headers/tip"); f = api("/api/fee_pool")
    ml = m if isinstance(m, list) else m.get("miners", [])
    return {
        "status": h.get("status", "unknown"),
        "version": h.get("version", "?"),
        "epoch": e.get("epoch", e.get("current_epoch", 0)),
        "slot": e.get("slot", 0),
        "height": t.get("height", t.get("slot", 0)),
        "miners": len(ml),
        "supply": e.get("total_supply", 0),
        "fee_pool": f.get("fee_pool", f.get("balance", 0)),
        "epoch_pot": e.get("epoch_pot", e.get("reward_pot", 0)),
    }

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(aggregate()).encode())
    def log_message(self, *a): pass

if __name__ == "__main__":
    port = int(os.environ.get("METRICS_PORT", "9200"))
    print(f"Metrics API on :{port}")
    http.server.HTTPServer(("", port), Handler).serve_forever()
