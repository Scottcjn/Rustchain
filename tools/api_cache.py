#!/usr/bin/env python3
"""RustChain API Response Cache — Local caching proxy for offline/fast access."""
import json, urllib.request, ssl, os, time, hashlib, http.server, threading

CACHE_DIR = os.path.expanduser("~/.rustchain/api-cache")
NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
TTL = int(os.environ.get("CACHE_TTL", "60"))

def cached_fetch(path):
    os.makedirs(CACHE_DIR, exist_ok=True)
    key = hashlib.md5(path.encode()).hexdigest()
    cache_file = os.path.join(CACHE_DIR, f"{key}.json")
    if os.path.exists(cache_file) and time.time() - os.path.getmtime(cache_file) < TTL:
        with open(cache_file) as f: return json.load(f)
    try:
        ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        data = json.loads(urllib.request.urlopen(f"{NODE}{path}", timeout=10, context=ctx).read())
        with open(cache_file, "w") as f: json.dump(data, f)
        return data
    except:
        if os.path.exists(cache_file):
            with open(cache_file) as f: return json.load(f)
        return {"error": "unreachable", "cached": False}

class CacheProxy(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        data = cached_fetch(self.path)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    def log_message(self, *a): pass

if __name__ == "__main__":
    port = int(os.environ.get("CACHE_PORT", "8089"))
    print(f"API cache proxy on :{port} (TTL={TTL}s)")
    http.server.HTTPServer(("", port), CacheProxy).serve_forever()
