#!/usr/bin/env python3
"""
RustChain P2P Initialization Helper
===================================

Initializes and configures P2P gossip node for RustChain blockchain synchronization.
Automatically detects node identity and builds peer list excluding self.

Updated 2025-12-17: Added POWER8 Funnel URL for public access

Usage:
    from rustchain_p2p_init import init_p2p, get_node_id_for_ip
    
    # Initialize P2P node with Flask app
    p2p_node = init_p2p(app, db_path="/root/rustchain/rustchain_v2.db")
    
    # Or specify node ID explicitly
    p2p_node = init_p2p(app, db_path, node_id="node1")

Peer Configuration:
    PEER_NODES dictionary contains all known RustChain nodes with both
    Tailscale and public URLs. The init function automatically excludes
    the local node from the peer list.
"""

import os
from typing import Any, Dict, Optional
from flask import Flask

# All RustChain nodes - includes both Tailscale and public URLs
# Format: node_id -> URL (public or Tailscale)
PEER_NODES: Dict[str, str] = {
    "node1": "https://rustchain.org",           # VPS Primary (public)
    "node1_ts": "http://100.125.31.50:8099",       # VPS via Tailscale
    "node2": "http://50.28.86.153:8099",           # VPS Secondary / Ergo Anchor
    "node3": "http://100.88.109.32:8099",          # Ryan's (Tailscale)
    "node3_public": "http://76.8.228.245:8099",    # Ryan's (public)
    "node4": "http://100.94.28.32:8099",           # POWER8 S824 (Tailscale)
    "node4_public": "https://sophiapower8.tailbac22e.ts.net"  # POWER8 (Funnel - public!)
}


def init_p2p(app: Flask, db_path: str, node_id: Optional[str] = None) -> Optional[Any]:
    """
    Initialize and start RustChain P2P gossip node.
    
    Automatically detects node identity based on local IP address or hostname,
    builds peer list excluding self, and starts the P2P synchronization thread.
    
    Args:
        app: Flask application instance to register P2P endpoints
        db_path: Path to SQLite database for blockchain state
        node_id: Optional explicit node ID (default: auto-detect from IP/hostname)
        
    Returns:
        Optional[Any]: RustChainP2PNode instance if successful, None if P2P module not available
        
    Note:
        - Node ID detection order: env var RC_NODE_ID → IP match → hostname hash
        - Peers are filtered to exclude local node based on IP matching
        - P2P module import failure is handled gracefully (returns None)
        
    Example:
        >>> app = Flask(__name__)
        >>> p2p = init_p2p(app, "/root/rustchain/rustchain_v2.db")
        [P2P] Initializing node node1 with 5 peers
        [P2P] Node node1 started successfully
    """
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
    """
    Map IP address to node ID from PEER_NODES configuration.
    
    Searches through known node URLs to find one containing the given IP address.
    Used for identifying nodes from connection logs or peer reports.
    
    Args:
        ip: IP address to look up (e.g., "100.125.31.50")
        
    Returns:
        str: Node ID if found (e.g., "node1_ts"), or "unknown_{ip}" if not in registry
        
    Example:
        >>> get_node_id_for_ip("100.125.31.50")
        'node1_ts'
        >>> get_node_id_for_ip("192.168.1.100")
        'unknown_192.168.1.100'
    """
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
