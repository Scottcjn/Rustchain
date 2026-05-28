#!/usr/bin/env python3
"""
RustChain P2P Initialization Helper
===================================

Updated 2025-12-17: Added POWER8 Funnel URL for public access
"""

import ipaddress
import os
from urllib.parse import urlparse

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


def _env_flag(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _is_private_host(host):
    try:
        return ipaddress.ip_address(host).is_private
    except ValueError:
        return False


def _valid_public_url(raw_url):
    if not raw_url:
        return None
    parsed = urlparse(raw_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return raw_url.strip().rstrip("/")


def _discover_upnp_external_url(local_ip, local_port):
    """Return a public P2P URL via UPnP IGD when miniupnpc is available."""
    try:
        import miniupnpc
    except ImportError:
        return None

    try:
        upnp = miniupnpc.UPnP()
        upnp.discoverdelay = int(os.environ.get("RC_P2P_UPNP_DISCOVER_DELAY_MS", "200"))
        if upnp.discover() <= 0:
            return None
        upnp.selectigd()
        external_ip = upnp.externalipaddress()
        if not external_ip:
            return None

        description = os.environ.get("RC_P2P_UPNP_DESCRIPTION", "RustChain P2P")
        try:
            upnp.addportmapping(local_port, "TCP", local_ip, local_port, description, "")
        except Exception as exc:
            print(f"[P2P] UPnP port mapping failed: {exc}")
            return None

        return f"http://{external_ip}:{local_port}"
    except Exception as exc:
        print(f"[P2P] UPnP discovery failed: {exc}")
        return None


def resolve_advertised_url(local_ip, local_port=8099):
    """Choose the URL this node should advertise to peers."""
    explicit_url = _valid_public_url(os.environ.get("RC_P2P_EXTERNAL_URL"))
    if explicit_url:
        return explicit_url

    if (
        _is_private_host(local_ip)
        and _env_flag("RC_P2P_ENABLE_UPNP", default=True)
        and not _env_flag("RC_P2P_DISABLE_UPNP")
    ):
        return _discover_upnp_external_url(local_ip, local_port)

    return None


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

    local_ip = None
    if my_ips:
        local_ip = next((ip for ip in my_ips if "." in ip and not ip.startswith("127.")), None)

    p2p_port = int(os.environ.get("RC_P2P_PORT", "8099"))
    advertised_url = resolve_advertised_url(local_ip or "127.0.0.1", p2p_port)

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
    if advertised_url:
        print(f"[P2P] Advertising public P2P URL: {advertised_url}")

    p2p_node = RustChainP2PNode(node_id, db_path, peers, advertised_url=advertised_url)
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
