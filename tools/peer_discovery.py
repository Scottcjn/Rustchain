#!/usr/bin/env python3
"""RustChain Peer Discovery — Find and test network peers."""
import json, urllib.request, ssl, os, socket

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
KNOWN_PEERS = ["rustchain.org", "50.28.86.131"]

def discover():
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    print("RustChain Peer Discovery\n" + "=" * 45)
    peers = set(KNOWN_PEERS)
    try:
        r = json.loads(urllib.request.urlopen(f"{NODE}/api/nodes", timeout=10, context=ctx).read())
        nodes = r if isinstance(r, list) else r.get("nodes", [])
        for n in nodes:
            addr = n.get("address", n.get("host", n.get("ip", "")))
            if addr: peers.add(addr)
    except: pass
    
    for peer in peers:
        try:
            ip = socket.gethostbyname(peer) if not peer[0].isdigit() else peer
            sock = socket.create_connection((ip, 8088), timeout=3)
            sock.close()
            print(f"  ALIVE  {peer} ({ip})")
        except:
            print(f"  DOWN   {peer}")

if __name__ == "__main__":
    discover()
