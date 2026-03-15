#!/usr/bin/env python3
"""RustChain Peer Reputation Scoring — Rate P2P peers by reliability."""
import json, urllib.request, os, time

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")

def api(path):
    try:
        import ssl; ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        return json.loads(urllib.request.urlopen(f"{NODE}{path}", timeout=10, context=ctx).read())
    except:
        return {}

def score_peers():
    peers = api("/api/nodes")
    if not peers:
        peers = api("/api/peers")
    
    peer_list = peers if isinstance(peers, list) else peers.get("nodes", peers.get("peers", []))
    
    print("RustChain Peer Reputation Scores")
    print("=" * 60)
    print(f"{'Peer':<20} {'Uptime':<10} {'Latency':<10} {'Score':<10} {'Grade'}")
    print("-" * 60)
    
    for peer in peer_list:
        pid = str(peer.get("node_id", peer.get("id", "?")))[:18]
        uptime = peer.get("uptime", peer.get("uptime_pct", 0))
        latency = peer.get("latency_ms", peer.get("avg_latency", 0))
        
        # Score: 0-100 based on uptime and latency
        uptime_score = min(uptime, 100) if isinstance(uptime, (int, float)) else 50
        latency_score = max(0, 100 - (latency / 10)) if isinstance(latency, (int, float)) else 50
        total = int(uptime_score * 0.7 + latency_score * 0.3)
        
        grade = "A+" if total >= 95 else "A" if total >= 85 else "B" if total >= 70 else "C" if total >= 50 else "F"
        print(f"  {pid:<18} {uptime:>6.1f}%   {latency:>6.0f}ms   {total:>5}/100  {grade}")

if __name__ == "__main__":
    score_peers()
