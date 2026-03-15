#!/usr/bin/env python3
"""RustChain API Documentation Generator — Auto-generate docs from live API."""
import json, urllib.request, ssl, os

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
ENDPOINTS = ["/health","/epoch","/api/miners","/api/stats","/headers/tip","/api/fee_pool",
             "/beacon/digest","/genesis/export","/api/bounty-multiplier"]

def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try:
        r = urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx)
        return json.loads(r.read()), r.status
    except: return {}, 0

def generate():
    doc = ["# RustChain API Reference (Auto-Generated)\n"]
    for ep in ENDPOINTS:
        data, status = api(ep)
        doc.append(f"## `GET {ep}`\n")
        doc.append(f"**Status:** {status}\n")
        if data:
            doc.append(f"**Response:**\n```json\n{json.dumps(data, indent=2)[:500]}\n```\n")
        doc.append("")
    with open("API_REFERENCE.md", "w") as f:
        f.write("\n".join(doc))
    print(f"Generated API_REFERENCE.md ({len(ENDPOINTS)} endpoints)")

if __name__ == "__main__":
    generate()
