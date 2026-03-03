#!/usr/bin/env python3
"""
Unit tests for RustChain PoW miner detection and proof generation.

Tests cover:
- Process detection
- Node RPC probing
- Pool account verification
- Subprocess launch/stop
- Warthog-specific integration
"""

import json
import subprocess
import sys
import time
import unittest
from unittest.mock import patch, MagicMock
from io import StringIO

# Import the module under test
sys.path.insert(0, '/root/.openclaw/workspace/rustchain-repo/miners/clawrtc')
from pow_miners import (
    KNOWN_MINERS,
    POW_BONUS,
    detect_running_miners,
    generate_pow_proof,
    launch_miner_subprocess,
    stop_miner_subprocess,
    _get_running_processes,
    _check_port_open,
    _check_command_exists,
    print_detection_report,
    get_supported_chains,
    get_chain_info,
)


class TestKnownMiners(unittest.TestCase):
    """Test KNOWN_MINERS configuration."""

    def test_warthog_config_exists(self):
        """Warthog should be in KNOWN_MINERS."""
        self.assertIn("warthog", KNOWN_MINERS)

    def test_warthog_has_required_fields(self):
        """Warthog config should have all required fields."""
        warthog = KNOWN_MINERS["warthog"]
        required_fields = [
            "display", "algo", "node_ports", "process_names",
            "node_info_path", "pool_api_templates", "miner_commands",
        ]
        for field in required_fields:
            self.assertIn(field, warthog, f"Missing field: {field}")

    def test_warthog_process_names(self):
        """Warthog should have expected process names."""
        warthog = KNOWN_MINERS["warthog"]
        expected_procs = [
            "wart-node-linux", "wart-node", "janusminer",
            "janusminer-ubuntu", "janusminer-ubuntu22", "bzminer",
        ]
        for proc in expected_procs:
            self.assertIn(proc, warthog["process_names"])

    def test_warthog_pool_apis(self):
        """Warthog should have pool API templates."""
        warthog = KNOWN_MINERS["warthog"]
        expected_pools = ["woolypooly", "cedric-crispin", "herominers", "acc-pool"]
        for pool in expected_pools:
            self.assertIn(pool, warthog["pool_api_templates"])

    def test_warthog_miner_commands(self):
        """Warthog should have miner command templates."""
        warthog = KNOWN_MINERS["warthog"]
        self.assertIn("bzminer", warthog["miner_commands"])
        self.assertIn("janusminer", warthog["miner_commands"])

    def test_warthog_algo(self):
        """Warthog should use Janushash algorithm."""
        warthog = KNOWN_MINERS["warthog"]
        self.assertEqual(warthog["algo"], "janushash")

    def test_warthog_node_ports(self):
        """Warthog node should use port 3000."""
        warthog = KNOWN_MINERS["warthog"]
        self.assertIn(3000, warthog["node_ports"])


class TestProcessDetection(unittest.TestCase):
    """Test process detection functionality."""

    @patch('pow_miners._get_running_processes')
    @patch('pow_miners._check_port_open')
    def test_detect_warthog_node(self, mock_port, mock_procs):
        """Should detect Warthog node running on port 3000."""
        mock_procs.return_value = ""
        mock_port.return_value = True

        detected = detect_running_miners()
        warthog_detected = [d for d in detected if d["chain"] == "warthog"]

        self.assertTrue(len(warthog_detected) > 0)
        self.assertTrue(warthog_detected[0]["node_responding"])
        self.assertEqual(warthog_detected[0]["proof_type"], "node_rpc")

    @patch('pow_miners._get_running_processes')
    @patch('pow_miners._check_port_open')
    def test_detect_warthog_process(self, mock_port, mock_procs):
        """Should detect Warthog miner process."""
        mock_procs.return_value = "janusminer-ubuntu22 -a wallet123"
        mock_port.return_value = False

        detected = detect_running_miners()
        warthog_detected = [d for d in detected if d["chain"] == "warthog"]

        self.assertTrue(len(warthog_detected) > 0)
        self.assertTrue(warthog_detected[0]["process_found"])
        self.assertEqual(warthog_detected[0]["proof_type"], "process_only")

    @patch('pow_miners._get_running_processes')
    def test_get_running_processes(self, mock_run):
        """Should return lowercase process list."""
        mock_run.return_value = MagicMock(stdout="USER PID COMMAND\nroot 123 JanusMiner\n")

        procs = _get_running_processes()
        self.assertIsInstance(procs, str)
        self.assertEqual(procs, procs.lower())


class TestProofGeneration(unittest.TestCase):
    """Test proof generation functionality."""

    @patch('pow_miners._probe_node_rpc')
    @patch('pow_miners._get_running_processes')
    def test_generate_warthog_node_proof(self, mock_procs, mock_rpc):
        """Should generate node RPC proof for Warthog."""
        mock_procs.return_value = ""
        mock_rpc.return_value = {
            "endpoint": "localhost:3000",
            "chain_height": 12345,
            "best_block": "abc123",
            "proof_hash": "def456",
        }

        proof = generate_pow_proof("warthog", "test_nonce")

        self.assertIsNotNone(proof)
        self.assertEqual(proof["chain"], "warthog")
        self.assertEqual(proof["proof_type"], "node_rpc")
        self.assertEqual(proof["bonus_multiplier"], POW_BONUS["node_rpc"])

    @patch('pow_miners._verify_pool_account')
    @patch('pow_miners._probe_node_rpc')
    @patch('pow_miners._get_running_processes')
    def test_generate_warthog_pool_proof(self, mock_procs, mock_rpc, mock_pool):
        """Should generate pool account proof for Warthog."""
        mock_procs.return_value = ""
        mock_rpc.return_value = None  # Node not responding
        mock_pool.return_value = {
            "pool": "woolypooly",
            "hashrate": 1000,
            "last_share_ts": time.time(),
        }

        proof = generate_pow_proof(
            "warthog",
            "test_nonce",
            pool_address="test_wallet",
            pool_name="woolypooly",
        )

        self.assertIsNotNone(proof)
        self.assertEqual(proof["proof_type"], "pool_account")
        self.assertEqual(proof["bonus_multiplier"], POW_BONUS["pool_account"])

    @patch('pow_miners._probe_node_rpc')
    @patch('pow_miners._get_running_processes')
    def test_generate_warthog_process_proof(self, mock_procs, mock_rpc):
        """Should generate process-only proof for Warthog."""
        mock_procs.return_value = "janusminer"
        mock_rpc.return_value = None

        proof = generate_pow_proof("warthog", "test_nonce")

        self.assertIsNotNone(proof)
        self.assertEqual(proof["proof_type"], "process_only")
        self.assertEqual(proof["bonus_multiplier"], POW_BONUS["process_only"])

    def test_generate_proof_unknown_chain(self):
        """Should return None for unknown chain."""
        proof = generate_pow_proof("unknown_chain", "test_nonce")
        self.assertIsNone(proof)


class TestSubprocessLaunch(unittest.TestCase):
    """Test subprocess launch functionality."""

    @patch('pow_miners._check_command_exists')
    def test_launch_dry_run(self, mock_check):
        """Dry run should return command without executing."""
        mock_check.return_value = True

        success, proc, msg = launch_miner_subprocess(
            chain="warthog",
            wallet="test_wallet",
            pool_url="stratum+tcp://pool.woolypooly.com:3140",
            dry_run=True,
        )

        self.assertTrue(success)
        self.assertIsNone(proc)
        self.assertIn("Would execute:", msg)

    @patch('subprocess.Popen')
    @patch('pow_miners._check_command_exists')
    @patch('pow_miners._get_running_processes')
    def test_launch_miner_success(self, mock_procs, mock_check, mock_popen):
        """Should successfully launch miner subprocess."""
        mock_procs.return_value = ""  # No miners running
        mock_check.return_value = True
        mock_popen.return_value = MagicMock(pid=12345)

        success, proc, msg = launch_miner_subprocess(
            chain="warthog",
            wallet="test_wallet",
            miner_name="bzminer",
            dry_run=False,
        )

        self.assertTrue(success)
        self.assertIsNotNone(proc)
        self.assertIn("PID: 12345", msg)

    @patch('subprocess.Popen')
    @patch('pow_miners._check_command_exists')
    @patch('pow_miners._get_running_processes')
    def test_launch_miner_already_running(self, mock_procs, mock_check, mock_popen):
        """Should fail if miner already running."""
        mock_procs.return_value = "janusminer"
        mock_check.return_value = True  # Miner is available

        success, proc, msg = launch_miner_subprocess(
            chain="warthog",
            wallet="test_wallet",
        )

        self.assertFalse(success)
        self.assertIsNone(proc)
        self.assertIn("already running", msg)

    @patch('pow_miners._check_command_exists')
    def test_launch_miner_not_found(self, mock_check):
        """Should fail if miner executable not found."""
        mock_check.return_value = False

        success, proc, msg = launch_miner_subprocess(
            chain="warthog",
            wallet="test_wallet",
            miner_name="nonexistent_miner",
        )

        self.assertFalse(success)
        self.assertIn("No available miner found", msg)

    @patch('subprocess.run')
    @patch('pow_miners._get_running_processes')
    def test_stop_miner_success(self, mock_procs, mock_run):
        """Should successfully stop running miner."""
        mock_procs.return_value = "janusminer"
        mock_run.return_value = MagicMock(returncode=0)

        success, msg = stop_miner_subprocess("warthog")

        self.assertTrue(success)
        self.assertIn("Stopped", msg)

    @patch('pow_miners._get_running_processes')
    def test_stop_miner_not_running(self, mock_procs):
        """Should fail if no miners running."""
        mock_procs.return_value = ""

        success, msg = stop_miner_subprocess("warthog")

        self.assertFalse(success)
        self.assertIn("No running miners found", msg)


class TestHelperFunctions(unittest.TestCase):
    """Test helper functions."""

    def test_get_supported_chains(self):
        """Should return list of supported chains."""
        chains = get_supported_chains()
        self.assertIsInstance(chains, list)
        self.assertIn("warthog", chains)
        self.assertIn("ergo", chains)
        self.assertIn("monero", chains)

    def test_get_chain_info(self):
        """Should return chain info dict."""
        info = get_chain_info("warthog")
        self.assertIsNotNone(info)
        self.assertEqual(info["algo"], "janushash")

    def test_get_chain_info_unknown(self):
        """Should return None for unknown chain."""
        info = get_chain_info("unknown_chain")
        self.assertIsNone(info)

    @patch('socket.socket')
    def test_check_port_open_true(self, mock_socket):
        """Should return True for open port."""
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 0
        mock_socket.return_value = mock_sock

        result = _check_port_open(3000)
        self.assertTrue(result)

    @patch('socket.socket')
    def test_check_port_open_false(self, mock_socket):
        """Should return False for closed port."""
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 1
        mock_socket.return_value = mock_sock

        result = _check_port_open(3000)
        self.assertFalse(result)


class TestBonusMultipliers(unittest.TestCase):
    """Test bonus multiplier configuration."""

    def test_node_rpc_bonus(self):
        """Node RPC proof should give 1.5x bonus."""
        self.assertEqual(POW_BONUS["node_rpc"], 1.5)

    def test_pool_account_bonus(self):
        """Pool account proof should give 1.3x bonus."""
        self.assertEqual(POW_BONUS["pool_account"], 1.3)

    def test_process_only_bonus(self):
        """Process-only proof should give 1.15x bonus."""
        self.assertEqual(POW_BONUS["process_only"], 1.15)


class TestWarthogIntegration(unittest.TestCase):
    """Warthog-specific integration tests."""

    def test_warthog_node_rpc_endpoint(self):
        """Warthog node RPC should use /chain/head endpoint."""
        warthog = KNOWN_MINERS["warthog"]
        self.assertEqual(warthog["node_info_path"], "/chain/head")

    def test_warthog_pool_urls(self):
        """Warthog pool URLs should be correctly formatted."""
        warthog = KNOWN_MINERS["warthog"]
        pools = warthog["pool_api_templates"]

        # Check WoolyPooly
        self.assertIn("woolypooly.com", pools["woolypooly"])
        self.assertIn("{address}", pools["woolypooly"])

        # Check HeroMiners
        self.assertIn("herominers.com", pools["herominers"])
        self.assertIn("{address}", pools["herominers"])

    def test_warthog_bzminer_command(self):
        """bzminer command should include -a warthog flag."""
        warthog = KNOWN_MINERS["warthog"]
        bzminer_cmd = warthog["miner_commands"]["bzminer"]

        self.assertIn("-a", bzminer_cmd)
        self.assertIn("warthog", bzminer_cmd)
        self.assertIn("{wallet}", bzminer_cmd)
        self.assertIn("{pool}", bzminer_cmd)

    def test_warthog_janusminer_command(self):
        """janusminer command should include wallet and node params."""
        warthog = KNOWN_MINERS["warthog"]
        janus_cmd = warthog["miner_commands"]["janusminer"]

        self.assertIn("janusminer-ubuntu22", janus_cmd)
        self.assertIn("-a", janus_cmd)
        self.assertIn("{wallet}", janus_cmd)
        self.assertIn("127.0.0.1", janus_cmd)
        self.assertIn("3000", janus_cmd)


if __name__ == "__main__":
    unittest.main(verbosity=2)
