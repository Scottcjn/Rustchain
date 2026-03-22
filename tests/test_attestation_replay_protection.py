"""Tests for Issue #2296 — Attestation Replay Cross-Node Attack protection.

Verifies that:
- Each attestation payload is bound to a specific node via node_url.
- The commitment hash changes when the target node changes, so a captured
  payload cannot be silently replayed to a different node.
"""

import hashlib
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

from stress_test.miner_simulator import MinerSimulator

NODE_1 = "https://50.28.86.131"
NODE_2 = "https://50.28.86.153"
NODE_3 = "https://76.8.228.245"

NONCE = "abc123deadbeef00"


class TestNodeUrlBinding:
    def test_payload_contains_node_url(self):
        sim = MinerSimulator()
        p = sim.build_attestation_payload(NONCE, NODE_1)
        assert p["node_url"] == NODE_1

    def test_payload_node_url_changes_with_target(self):
        sim = MinerSimulator()
        p1 = sim.build_attestation_payload(NONCE, NODE_1)
        p2 = sim.build_attestation_payload(NONCE, NODE_2)
        assert p1["node_url"] != p2["node_url"]

    def test_payload_node_url_is_string(self):
        sim = MinerSimulator()
        p = sim.build_attestation_payload(NONCE, NODE_1)
        assert isinstance(p["node_url"], str)
        assert p["node_url"].startswith("https://")


class TestCommitmentBinding:
    def test_commitment_present(self):
        sim = MinerSimulator()
        p = sim.build_attestation_payload(NONCE, NODE_1)
        assert "commitment" in p["report"]

    def test_commitment_differs_across_nodes(self):
        """Same nonce + same miner on different nodes must produce different commitments."""
        sim = MinerSimulator()
        p1 = sim.build_attestation_payload(NONCE, NODE_1)
        p2 = sim.build_attestation_payload(NONCE, NODE_2)
        assert p1["report"]["commitment"] != p2["report"]["commitment"], (
            "Commitment must be node-specific to prevent cross-node replay"
        )

    def test_commitment_differs_across_three_nodes(self):
        sim = MinerSimulator()
        c1 = sim.build_attestation_payload(NONCE, NODE_1)["report"]["commitment"]
        c2 = sim.build_attestation_payload(NONCE, NODE_2)["report"]["commitment"]
        c3 = sim.build_attestation_payload(NONCE, NODE_3)["report"]["commitment"]
        assert len({c1, c2, c3}) == 3, "All three nodes must yield distinct commitments"

    def test_commitment_is_sha256_hex(self):
        sim = MinerSimulator()
        p = sim.build_attestation_payload(NONCE, NODE_1)
        commitment = p["report"]["commitment"]
        assert len(commitment) == 64
        int(commitment, 16)  # raises ValueError if not valid hex

    def test_commitment_stable_for_same_inputs(self):
        """Commitment must be deterministic given the same nonce, wallet and node."""
        sim = MinerSimulator(miner_id="stable-test")
        # Build commitment manually using the same algorithm
        entropy_report = sim.generate_entropy_report(NONCE, NODE_1)
        derived = entropy_report["derived"]
        expected = hashlib.sha256(
            (NONCE + sim.wallet + NODE_1 + json.dumps(derived, sort_keys=True)).encode()
        ).hexdigest()
        assert entropy_report["commitment"] == expected


class TestReplayScenario:
    def test_node1_payload_has_different_commitment_than_node2(self):
        """
        Simulate the exact replay scenario from Issue #2296:
        Miner attests on Node 1, attacker captures payload and sends to Node 2.
        Node 2 can detect the mismatch via node_url and commitment.
        """
        sim = MinerSimulator()

        # Legitimate attestation on Node 1
        payload_node1 = sim.build_attestation_payload(NONCE, NODE_1)

        # Attacker extracts commitment from the captured payload
        captured_commitment = payload_node1["report"]["commitment"]
        captured_node_url = payload_node1["node_url"]

        # What a legitimate Node 2 attestation would look like
        payload_node2_legit = sim.build_attestation_payload(NONCE, NODE_2)
        legit_commitment_node2 = payload_node2_legit["report"]["commitment"]

        # The captured commitment from Node 1 differs from a valid Node 2 commitment
        assert captured_commitment != legit_commitment_node2
        # The captured node_url doesn't match Node 2
        assert captured_node_url != NODE_2

    def test_malformed_payload_includes_node_url(self):
        sim = MinerSimulator()
        p = sim.build_malformed_payload(NONCE, NODE_1)
        # build_malformed_payload may return raw string for corrupt_json branch
        if isinstance(p, dict):
            assert "node_url" in p
