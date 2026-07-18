#!/usr/bin/env python3
"""Regression test: NetworkHealth.total_miners must not multiply by node count.

The attestation nodes are replicas of one shared ledger, so every online node
reports the SAME network-wide miner count (ledger_verify / node_sync_validator
flag any divergence as a mismatch). total_miners must therefore be the agreed
value, not the sum across nodes.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.node_health_monitor import NodeHealthMonitor, NodeStatus


def _node(url, epoch, miners, status="online"):
    return NodeStatus(
        url=url, status=status, response_time_ms=10.0,
        epoch=epoch, miners=miners, error=None,
    )


def test_replicas_are_not_summed():
    m = NodeHealthMonitor()
    statuses = [_node("n1", 42, 150), _node("n2", 42, 150), _node("n3", 42, 150)]
    h = m.get_network_health(statuses)
    # Buggy code returned 450 (3 * 150); correct network count is 150.
    assert h.total_miners == 150, h.total_miners


def test_lagging_node_does_not_lower_count():
    m = NodeHealthMonitor()
    statuses = [_node("n1", 42, 150), _node("n2", 42, 149), _node("n3", 42, 150)]
    h = m.get_network_health(statuses)
    assert h.total_miners == 150, h.total_miners


def test_offline_and_missing_data():
    m = NodeHealthMonitor()
    statuses = [_node("n1", 42, 150), _node("n2", None, None, "offline"), _node("n3", 42, 150)]
    h = m.get_network_health(statuses)
    assert h.total_miners == 150 and h.nodes_online == 2

    h = m.get_network_health([_node("n1", 42, None), _node("n2", 42, None)])
    assert h.total_miners == 0


if __name__ == "__main__":
    test_replicas_are_not_summed()
    test_lagging_node_does_not_lower_count()
    test_offline_and_missing_data()
    print("all node_health total_miners regression tests passed")
