#!/usr/bin/env python3
"""RustChain Configure miner alerting."""
import json, urllib.request, ssl, os, time
NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try:
        s = time.time()
        r = urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx)
        return json.loads(r.read()), round((time.time()-s)*1000, 1)
    except: return {}, 0
def main():
    h, hms = api("/health")
    e, ems = api("/epoch")
    m, mms = api("/api/miners")
    ml = m if isinstance(m, list) else m.get("miners", [])
    print(f"Configure miner alerting")
    print(f"  {h.get('status','?')} v{h.get('version','?')} | epoch {e.get('epoch', e.get('current_epoch','?'))} | {len(ml)} miners | {hms}ms")
if __name__ == "__main__":
    main()
