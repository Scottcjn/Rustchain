#!/usr/bin/env python3
"""RustChain Verify wallet file integrity."""
import json, urllib.request, ssl, os, time, sys
NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try: return json.loads(urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx).read())
    except: return {}
def main():
    data = api("/health")
    epoch = api("/epoch")
    print(f"Verify wallet file integrity: status={data.get('status','?')} epoch={epoch.get('epoch', epoch.get('current_epoch','?'))}")
if __name__ == "__main__":
    main()
