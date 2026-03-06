#!/usr/bin/env python3
"""
RustChain P2P Initialization Helper
===================================

Updated 2025-12-17: Added POWER8 Funnel URL for public access
"""

import os

# All RustChain nodes - includes both Tailscale and public URLs
PEER_NODES = {
    "node1": "https://rustchain.org",           # VPS Primary (public)
    "node1_ts": "http://100.125.31.50:8099",       # VPS via Tailscale
    "node2": "http://50.28.86.153:8099",           # VPS Secondary / Ergo Anchor
    "node3": "http://100.88.109.32:8099",          # Ryan's (Tailscale)
    "node3_public": "http://76.8.228.245:8099",    # Ryan's (public)
    "node4": "http://100.94.28.32:8099",           # POWER8 S824 (Tailscale)
    "node4_public": "https://sophiapower8.tailbac22e.ts.net"  # POWER8 (Funnel - public!)
}


def init_p2p(app, db_path, node_id=None):
    try:
        from rustchain_p2p_gossip import RustChainP2PNode, register_p2p_endpoints
    except ImportError:
        print("[P2P] Module not found, running without P2P sync")
        return None

    if node_id is None:
        node_id = os.environ.get("RC_NODE_ID")

        if node_id is None:
            import socket
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()

                for nid, url in PEER_NODES.items():
                    if local_ip in url:
                        node_id = nid
                        break
            except:
                pass

        if node_id is None:
            import socket
            import hashlib
            hostname = socket.gethostname()
            node_id = f"node_{hashlib.sha256(hostname.encode()).hexdigest()[:8]}"

    # Build peer list excluding self
    peers = {}
    my_ips = set()
    
    try:
        import socket
        for info in socket.getaddrinfo(socket.gethostname(), None):
            my_ips.add(info[4][0])
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        my_ips.add(s.getsockname()[0])
        s.close()
    except:
        pass
    
    for k, v in PEER_NODES.items():
        if k == node_id:
            continue
        skip = False
        for ip in my_ips:
            if ip in v:
                skip = True
                break
        if not skip:
            peers[k] = v

    print(f"[P2P] Initializing node {node_id} with {len(peers)} peers")
    print(f"[P2P] Peers: {list(peers.keys())}")

    p2p_node = RustChainP2PNode(node_id, db_path, peers)
    register_p2p_endpoints(app, p2p_node)
    p2p_node.start()

    print(f"[P2P] Node {node_id} started successfully")
    return p2p_node


def get_node_id_for_ip(ip: str) -> str:
    for node_id, url in PEER_NODES.items():
        if ip in url:
            return node_id
    return f"unknown_{ip}"


if __name__ == "__main__":
    print("RustChain P2P Configuration")
    print("=" * 60)
    print("Known Nodes:")
    for node_id, url in PEER_NODES.items():
        print(f"  {node_id:15} : {url}")
    print()
    print("POWER8 Funnel URL: https://sophiapower8.tailbac22e.ts.net")
    print("  - Publicly accessible from any network!")
