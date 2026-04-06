"""
Test for F1: Full State Sync Bypasses Signature Verification

Verifies that:
1. _handle_state rejects messages with empty signatures
2. _handle_state rejects messages with invalid signatures
3. _handle_state accepts messages with valid signatures
4. _handle_get_state returns signed state responses
5. Full exploit path (empty-sig state injection) is blocked

Run: python test_f1_state_sync_bypass.py
"""

import sys
import os
import json
import unittest
from unittest.mock import MagicMock, patch

# Add node directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "Rustchain", "node"))


class TestStateSyncSignatureBypass(unittest.TestCase):
    """Test that state sync requires valid signatures (F1 fix verification)"""

    def setUp(self):
        """Create a GossipLayer instance for testing"""
        from rustchain_p2p_gossip import GossipLayer

        self.gossip = GossipLayer(
            node_id="test_node_1",
            peers={"peer1": "http://peer1:8099"},
        )

    def test_handle_state_rejects_empty_signature(self):
        """_handle_state must reject messages with empty signatures"""
        from rustchain_p2p_gossip import GossipMessage, MessageType

        msg = GossipMessage(
            msg_type=MessageType.STATE.value,
            msg_id="test_empty_sig",
            sender_id="attacker",
            timestamp=1234567890,
            ttl=0,
            signature="",  # Empty signature — the original bypass
            payload={
                "state": {
                    "attestations": {"increments": {}, "decrements": {}},
                    "epochs": {"epochs": [], "metadata": {}},
                    "balances": {
                        "increments": {"victim_miner": {"fake_node": 999999999}},
                        "decrements": {}
                    }
                }
            }
        )

        result = self.gossip._handle_state(msg)

        # After fix: should reject empty signature
        self.assertEqual(result.get("status"), "error")
        self.assertIn("signature", result.get("error", "").lower())

    def test_handle_state_rejects_invalid_signature(self):
        """_handle_state must reject messages with invalid signatures"""
        from rustchain_p2p_gossip import GossipMessage, MessageType

        msg = GossipMessage(
            msg_type=MessageType.STATE.value,
            msg_id="test_bad_sig",
            sender_id="attacker",
            timestamp=1234567890,
            ttl=0,
            signature="fake_signature_not_valid_hmac",
            payload={
                "state": {
                    "attestations": {"increments": {}, "decrements": {}},
                    "epochs": {"epochs": [], "metadata": {}},
                    "balances": {
                        "increments": {"victim_miner": {"fake_node": 999999999}},
                        "decrements": {}
                    }
                }
            }
        )

        result = self.gossip._handle_state(msg)

        # After fix: should reject invalid signature
        self.assertEqual(result.get("status"), "error")
        self.assertIn("signature", result.get("error", "").lower())

    def test_handle_state_accepts_valid_signature(self):
        """_handle_state must accept messages with valid signatures"""
        from rustchain_p2p_gossip import GossipMessage, MessageType
        import time

        state_data = {
            "attestations": {},
            "epochs": {"epochs": [], "metadata": {}},
            "balances": {
                "increments": {"honest_miner": {"honest_node": 1000}},
                "decrements": {}
            }
        }

        # Create a properly signed message — signature must match verify_message format
        payload = {"state": state_data}
        content = f"{MessageType.STATE.value}:{json.dumps(payload, sort_keys=True)}"
        signature, timestamp = self.gossip._sign_message(content)

        msg = GossipMessage(
            msg_type=MessageType.STATE.value,
            msg_id="test_valid_sig",
            sender_id="honest_peer",
            timestamp=timestamp,
            ttl=0,
            signature=signature,
            payload=payload
        )

        result = self.gossip._handle_state(msg)

        # Should accept valid signature
        self.assertEqual(result.get("status"), "ok")
        # Verify balance was merged
        balance = self.gossip.balance_crdt.get_balance("honest_miner")
        self.assertEqual(balance, 1000)

    def test_handle_get_state_returns_signature(self):
        """_handle_get_state must return signed state responses"""
        from rustchain_p2p_gossip import GossipMessage, MessageType

        msg = GossipMessage(
            msg_type=MessageType.GET_STATE.value,
            msg_id="test_get_state",
            sender_id="requester",
            timestamp=1234567890,
            ttl=0,
            signature="",
            payload={"requester": "requester"}
        )

        result = self.gossip._handle_get_state(msg)

        # After fix: response should include signature
        self.assertIn("signature", result)
        self.assertTrue(result["signature"])
        self.assertIn("state", result)

    def test_handle_get_state_signature_is_valid(self):
        """_handle_get_state signature must be verifiable"""
        from rustchain_p2p_gossip import GossipMessage, MessageType

        msg = GossipMessage(
            msg_type=MessageType.GET_STATE.value,
            msg_id="test_get_state_verify",
            sender_id="requester",
            timestamp=1234567890,
            ttl=0,
            signature="",
            payload={"requester": "requester"}
        )

        result = self.gossip._handle_get_state(msg)

        # Verify the signature can be validated using verify_message format
        state_data = result["state"]
        payload = {"state": state_data}
        content = f"{MessageType.STATE.value}:{json.dumps(payload, sort_keys=True)}"
        self.assertTrue(
            self.gossip._verify_signature(content, result["signature"], result["timestamp"])
        )


class TestStateSyncExploitPath(unittest.TestCase):
    """Demonstrate the full exploit path is now blocked"""

    def test_exploit_inflate_balance_via_unsigned_state(self):
        """Full exploit: attacker sends unsigned state to inflate balances — must be blocked"""
        from rustchain_p2p_gossip import GossipLayer, GossipMessage, MessageType

        victim = GossipLayer(
            node_id="victim_node",
            peers={"peer1": "http://peer1:8099"},
        )

        # Attacker crafts state with inflated balances
        attacker_state = {
            "attestations": {
                "increments": {},
                "decrements": {},
                "metadata": {}
            },
            "epochs": {
                "epochs": [1, 2, 3],
                "metadata": {1: {"finalized": True}}
            },
            "balances": {
                "increments": {
                    "attacker_miner": {
                        "attacker_node_1": 1000000000,
                        "attacker_node_2": 1000000000,
                        "attacker_node_3": 1000000000,
                    }
                },
                "decrements": {}
            }
        }

        # Before fix: signature="" bypassed all verification
        msg = GossipMessage(
            msg_type=MessageType.STATE.value,
            msg_id="exploit",
            sender_id="attacker",
            timestamp=1234567890,
            ttl=0,
            signature="",  # THE BYPASS
            payload={"state": attacker_state}
        )

        result = victim._handle_state(msg)

        # After fix: this must be rejected
        self.assertEqual(result.get("status"), "error",
            "State sync with empty signature must be rejected")

        # Verify balance was NOT inflated
        balance = victim.balance_crdt.get_balance("attacker_miner")
        self.assertEqual(balance, 0,
            "Attacker balance should be 0 (state was rejected)")

    def test_exploit_inject_fake_epochs_via_unsigned_state(self):
        """Attacker injects fake settled epochs via unsigned state — must be blocked"""
        from rustchain_p2p_gossip import GossipLayer, GossipMessage, MessageType

        victim = GossipLayer(
            node_id="victim_node",
            peers={"peer1": "http://peer1:8099"},
        )

        attacker_state = {
            "attestations": {},
            "epochs": {
                "epochs": [999, 1000, 1001],
                "metadata": {999: {"finalized": True, "proposal_hash": "fake"}}
            },
            "balances": {}
        }

        msg = GossipMessage(
            msg_type=MessageType.STATE.value,
            msg_id="exploit_epochs",
            sender_id="attacker",
            timestamp=1234567890,
            ttl=0,
            signature="",
            payload={"state": attacker_state}
        )

        result = victim._handle_state(msg)
        self.assertEqual(result.get("status"), "error")

        # Epochs should NOT be injected
        self.assertFalse(victim.epoch_crdt.contains(999))
        self.assertFalse(victim.epoch_crdt.contains(1000))

    def test_exploit_overwrite_attestation_via_unsigned_state(self):
        """Attacker overwrites legitimate attestation via unsigned state — must be blocked"""
        from rustchain_p2p_gossip import GossipLayer, GossipMessage, MessageType
        import time

        victim = GossipLayer(
            node_id="victim_node",
            peers={"peer1": "http://peer1:8099"},
        )

        # Set a legitimate attestation
        now = int(time.time())
        victim.attestation_crdt.set("legit_miner", {
            "miner": "legit_miner",
            "device_family": "arm64",
            "device_arch": "aarch64",
            "entropy_score": 95
        }, now)

        # Attacker tries to overwrite with bad attestation
        attacker_state = {
            "attestations": {
                "legit_miner": {
                    "ts": now + 100,
                    "value": {
                        "miner": "legit_miner",
                        "device_family": "x86",
                        "device_arch": "unknown",
                        "entropy_score": 0
                    }
                }
            },
            "epochs": {},
            "balances": {}
        }

        msg = GossipMessage(
            msg_type=MessageType.STATE.value,
            msg_id="exploit_attest",
            sender_id="attacker",
            timestamp=1234567890,
            ttl=0,
            signature="",
            payload={"state": attacker_state}
        )

        result = victim._handle_state(msg)
        self.assertEqual(result.get("status"), "error")

        # Legitimate attestation should be preserved
        legit = victim.attestation_crdt.get("legit_miner")
        self.assertIsNotNone(legit)
        self.assertEqual(legit["entropy_score"], 95)


if __name__ == "__main__":
    unittest.main(verbosity=2)
