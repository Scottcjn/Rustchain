#!/usr/bin/env python3
"""RustChain P2P Gossip Protocol Simulator — Test network propagation."""
import json, random, time, hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Set

@dataclass
class Node:
    id: str
    peers: Set[str] = field(default_factory=set)
    received: Set[str] = field(default_factory=set)
    latency_ms: float = 50.0

class GossipSimulator:
    def __init__(self, num_nodes=10, connectivity=0.4):
        self.nodes: Dict[str, Node] = {}
        for i in range(num_nodes):
            nid = f"node-{i:03d}"
            self.nodes[nid] = Node(id=nid, latency_ms=random.uniform(20, 200))
        # Connect peers
        for nid, node in self.nodes.items():
            for oid in self.nodes:
                if oid != nid and random.random() < connectivity:
                    node.peers.add(oid)
                    self.nodes[oid].peers.add(nid)

    def broadcast(self, origin, msg_id=None):
        msg_id = msg_id or hashlib.sha256(f"{origin}{time.time()}".encode()).hexdigest()[:12]
        queue = [(origin, 0)]
        self.nodes[origin].received.add(msg_id)
        rounds = 0
        total_time = 0
        while queue:
            rounds += 1
            next_queue = []
            for nid, delay in queue:
                for peer in self.nodes[nid].peers:
                    if msg_id not in self.nodes[peer].received:
                        self.nodes[peer].received.add(msg_id)
                        peer_delay = delay + self.nodes[peer].latency_ms
                        next_queue.append((peer, peer_delay))
                        total_time = max(total_time, peer_delay)
            queue = next_queue
        reached = sum(1 for n in self.nodes.values() if msg_id in n.received)
        return {"rounds": rounds, "reached": reached, "total": len(self.nodes),
                "coverage": f"{reached/len(self.nodes)*100:.1f}%",
                "propagation_ms": round(total_time, 1)}

    def run(self, trials=100):
        print("RustChain Gossip Protocol Simulation")
        print(f"Nodes: {len(self.nodes)} | Trials: {trials}")
        print("=" * 50)
        results = [self.broadcast(random.choice(list(self.nodes.keys()))) for _ in range(trials)]
        avg_rounds = sum(r["rounds"] for r in results) / trials
        avg_coverage = sum(r["reached"] for r in results) / trials / len(self.nodes) * 100
        avg_time = sum(r["propagation_ms"] for r in results) / trials
        print(f"Avg rounds: {avg_rounds:.1f}")
        print(f"Avg coverage: {avg_coverage:.1f}%")
        print(f"Avg propagation: {avg_time:.0f}ms")
        for n in self.nodes.values():
            n.received.clear()

if __name__ == "__main__":
    GossipSimulator(num_nodes=20, connectivity=0.3).run()
