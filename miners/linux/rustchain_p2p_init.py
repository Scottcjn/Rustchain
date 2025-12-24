#!/usr/bin/env python3
"""
RustChain P2P Initialization Helper
===================================

Call this module's init_p2p() after Flask app creation to enable P2P sync.
"""

import os

# Node configuration - add all known nodes
# Each node should know about the others
PEER_NODES = {
    "node1": "http://50.28.86.131:8099",
    "node2": "http://50.28.86.153:8099",
    "node3": "http://76.8.228.245:8099"
}


def init_p2p(app, db_path, node_id=None):
    """
    Initialize P2P subsystem and register endpoints.

    Args:
        app: Flask application instance
        db_path: Path to SQLite database
        node_id: This node's identifier (auto-detected if None)

    Returns:
        RustChainP2PNode instance
    """
    try:
        from rustchain_p2p_gossip import RustChainP2PNode, register_p2p_endpoints
    except ImportError:
        print("[P2P] Module not found, running without P2P sync")
        return None

    # Auto-detect node ID from environment or hostname
    if node_id is None:
        node_id = os.environ.get("RC_NODE_ID")

        if node_id is None:
            # Try to detect from IP
            import socket
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()

                # Match IP to node
                for nid, url in PEER_NODES.items():
                    if local_ip in url or local_ip.replace(".", "") in url:
                        node_id = nid
                        break
            except:
                pass

        if node_id is None:
            import hashlib
            hostname = socket.gethostname()
            node_id = f"node_{hashlib.sha256(hostname.encode()).hexdigest()[:8]}"

    # Build peer list (excluding self)
    peers = {k: v for k, v in PEER_NODES.items() if k != node_id}

    # Also check if our IP is in any peer URL and remove those
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        peers = {k: v for k, v in peers.items() if local_ip not in v}
    except:
        pass

    print(f"[P2P] Initializing node {node_id} with {len(peers)} peers")
    print(f"[P2P] Peers: {list(peers.keys())}")

    # Create P2P node
    p2p_node = RustChainP2PNode(node_id, db_path, peers)

    # Register endpoints
    register_p2p_endpoints(app, p2p_node)

    # Start background sync
    p2p_node.start()

    print(f"[P2P] Node {node_id} started successfully")

    return p2p_node


def get_node_id_for_ip(ip: str) -> str:
    """Get node ID for a given IP address"""
    for node_id, url in PEER_NODES.items():
        if ip in url:
            return node_id
    return f"unknown_{ip}"


if __name__ == "__main__":
    print("RustChain P2P Configuration")
    print("=" * 40)
    print("Known Nodes:")
    for node_id, url in PEER_NODES.items():
        print(f"  {node_id}: {url}")
    print()
    print("Usage:")
    print("  from rustchain_p2p_init import init_p2p")
    print("  p2p_node = init_p2p(app, DB_PATH)")
