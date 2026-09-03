# SPDX-License-Identifier: MIT
"""
Peer-list hygiene for rustchain_p2p_init.PEER_NODES.

The sync loop POSTs to every entry here every 30s with the fleet P2P key
attached, so dead hosts are both wasted traffic and a secret-leak surface
(audit A3). node3 (Ryan's Proxmox, offline ~3 months) and node4 (POWER8,
down) were removed on 2026-09-03; node2 moved to https:// because
50.28.86.153 answers /health over TLS and the plain :8099 port is not
reachable from outside.
"""

import os
import sys
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rustchain_p2p_init import PEER_NODES  # noqa: E402

DEAD_HOSTS = {
    "76.8.228.245",      # node3 public (Ryan)
    "100.88.109.32",     # node3 Tailscale (Ryan)
    "38.76.217.189",     # old node4 (createkr, now an unrelated SPA)
    "100.94.28.32",      # node4 POWER8 Tailscale
    "sophiapower8.tailbac22e.ts.net",  # node4 POWER8 Funnel
}


def test_only_live_fleet_nodes_are_hardcoded():
    assert set(PEER_NODES) == {"node1", "node1_ts", "node2"}
    assert not any(k.startswith(("node3", "node4")) for k in PEER_NODES)


def test_no_dead_hosts_in_peer_list():
    hosts = {urlparse(url).hostname for url in PEER_NODES.values()}
    assert not (hosts & DEAD_HOSTS), hosts & DEAD_HOSTS


def test_node1_entries_unchanged_and_node2_uses_tls():
    assert PEER_NODES["node1"] == "https://rustchain.org"
    assert PEER_NODES["node1_ts"] == "http://100.125.31.50:8099"
    node2 = urlparse(PEER_NODES["node2"])
    assert node2.scheme == "https"
    assert node2.hostname == "50.28.86.153"


def test_every_peer_url_passes_gossip_scheme_validation():
    for url in PEER_NODES.values():
        parsed = urlparse(url)
        assert parsed.scheme in {"http", "https"} and parsed.netloc, url
