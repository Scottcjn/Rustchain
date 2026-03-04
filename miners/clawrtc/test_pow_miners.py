#!/usr/bin/env python3
"""
Unit tests for RustChain PoW miner detection and proof generation.

Tests cover:
- Process detection
- Node RPC probing
- Pool account verification
- Subprocess launch/stop
- Monero (RandomX) integration
- Warthog (Janushash) integration
"""

import json
import os
import subprocess
import sys
import time
import unittest
from unittest.mock import patch, MagicMock
from io import StringIO

# Import the module under test
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
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

    def test_monero_config_exists(self):
        """Monero should be in KNOWN_MINERS."""
        self.assertIn("monero", KNOWN_MINERS)

    def test_monero_has_required_fields(self):
        """Monero config should have all required fields."""
        monero = KNOWN_MINERS["monero"]
        required_fields = [
            "display", "algo", "node_ports", "process_names",
            "node_info_path", "pool_api_templates", "miner_commands",
        ]
        for field in required_fields:
            self.assertIn(field, monero, f"Missing field: {field}")

    def test_monero_process_names(self):
        """Monero should have expected process names."""
        monero = KNOWN_MINERS["monero"]
        expected_procs = [
            "xmrig", "xmrig-notls", "xmrig-cuda", "xmrig-amd",
            "monerod", "p2pool", "xmr-stak",
        ]
        for proc in expected_procs:
            self.assertIn(proc, monero["process_names"])

    def test_monero_pool_apis(self):
        """Monero should have pool API templates."""
        monero = KNOWN_MINERS["monero"]
        expected_pools = ["p2pool", "herominers", "nanopool", "supportxmr", "moneroocean"]
        for pool in expected_pools:
            self.assertIn(pool, monero["pool_api_templates"])

    def test_monero_miner_commands(self):
        """Monero should have miner command templates."""
        monero = KNOWN_MINERS["monero"]
        self.assertIn("xmrig", monero["miner_commands"])
        self.assertIn("xmrig-p2pool", monero["miner_commands"])
        self.assertIn("monerod", monero["miner_commands"])

    def test_monero_algo(self):
        """Monero should use RandomX algorithm."""
        monero = KNOWN_MINERS["monero"]
        self.assertEqual(monero["algo"], "randomx")

    def test_monero_node_ports(self):
        """Monero node should use ports 18081/18082."""
        monero = KNOWN_MINERS["monero"]
        self.assertIn(18081, monero["node_ports"])
        self.assertIn(18082, monero["node_ports"])

    def test_warthog_config_exists(self):
        """Warthog should be in KNOWN_MINERS."""
        self.assertIn("warthog", KNOWN_MINERS)

    def test_all_randomx_chains(self):
        """All RandomX-based chains should be present."""
        randomx_chains = ["monero", "zephyr", "wownero", "salvium", "scala"]
        for chain in randomx_chains:
            self.assertIn(chain, KNOWN_MINERS)
            self.assertEqual(KNOWN_MINERS[chain]["algo"], "randomx")


class TestProcessDetection(unittest.TestCase):
    """Test process detection functionality."""

    @patch('pow_miners._get_running_processes')
    @patch('pow_miners._check_port_open')
    def test_detect_monero_node(self, mock_port, mock_procs):
        """Should detect Monero node running on port 18081."""
        mock_procs.return_value = ""
        mock_port.return_value = True

        detected = detect_running_miners()
        monero_detected = [d for d in detected if d["chain"] == "monero"]

        self.assertTrue(len(monero_detected) > 0)
        self.assertTrue(monero_detected[0]["node_responding"])
        self.assertEqual(monero_detected[0]["proof_type"], "node_rpc")

    @patch('pow_miners._get_running_processes')
    @patch('pow_miners._check_port_open')
    def test_detect_monero_xmrig(self, mock_port, mock_procs):
        """Should detect XMRig miner process."""
        mock_procs.return_value = "xmrig --donate-level 1 -o pool.xmr.com"
        mock_port.return_value = False

        detected = detect_running_miners()
        monero_detected = [d for d in detected if d["chain"] == "monero"]

        self.assertTrue(len(monero_detected) > 0)
        self.assertTrue(monero_detected[0]["process_found"])
        self.assertEqual(monero_detected[0]["proof_type"], "process_only")

    @patch('pow_miners._get_running_processes')
    @patch('pow_miners._check_port_open')
    def test_detect_monero_p2pool(self, mock_port, mock_procs):
        """Should detect P2Pool process."""
        mock_procs.return_value = "p2pool --wallet abc123"
        mock_port.return_value = False

        detected = detect_running_miners()
        monero_detected = [d for d in detected if d["chain"] == "monero"]

        self.assertTrue(len(monero_detected) > 0)
        self.assertTrue(monero_detected[0]["process_found"])

    @patch('pow_miners._get_running_processes')
    def test_get_running_processes(self, mock_run):
        """Should return lowercase process list."""
        mock_run.return_value = MagicMock(stdout="USER PID COMMAND\nroot 123 XMRig\n")

        procs = _get_running_processes()
        self.assertIsInstance(procs, str)
        self.assertEqual(procs, procs.lower())


class TestProofGeneration(unittest.TestCase):
    """Test proof generation functionality."""

    @patch('pow_miners._probe_node_rpc')
    @patch('pow_miners._get_running_processes')
    def test_generate_monero_node_proof(self, mock_procs, mock_rpc):
        """Should generate node RPC proof for Monero."""
        mock_procs.return_value = ""
        mock_rpc.return_value = {
            "endpoint": "localhost:18081",
            "chain_height": 3000000,
            "difficulty": 350000000000,
            "tx_pool_size": 50,
            "proof_hash": "abc123def456",
        }

        proof = generate_pow_proof("monero", "test_nonce")

        self.assertIsNotNone(proof)
        self.assertEqual(proof["chain"], "monero")
        self.assertEqual(proof["proof_type"], "node_rpc")
        self.assertEqual(proof["bonus_multiplier"], POW_BONUS["node_rpc"])

    @patch('pow_miners._verify_pool_account')
    @patch('pow_miners._probe_node_rpc')
    @patch('pow_miners._get_running_processes')
    def test_generate_monero_pool_proof(self, mock_procs, mock_rpc, mock_pool):
        """Should generate pool account proof for Monero."""
        mock_procs.return_value = ""
        mock_rpc.return_value = None  # Node not responding
        mock_pool.return_value = {
            "pool": "herominers",
            "hashrate": 50000,
            "last_share_ts": time.time(),
        }

        proof = generate_pow_proof(
            "monero",
            "test_nonce",
            pool_address="4ABC...xyz",
            pool_name="herominers",
        )

        self.assertIsNotNone(proof)
        self.assertEqual(proof["proof_type"], "pool_account")
        self.assertEqual(proof["bonus_multiplier"], POW_BONUS["pool_account"])

    @patch('pow_miners._probe_node_rpc')
    @patch('pow_miners._get_running_processes')
    def test_generate_monero_process_proof(self, mock_procs, mock_rpc):
        """Should generate process-only proof for Monero."""
        mock_procs.return_value = "xmrig --url pool.xmr.com"
        mock_rpc.return_value = None

        proof = generate_pow_proof("monero", "test_nonce")

        self.assertIsNotNone(proof)
        self.assertEqual(proof["proof_type"], "process_only")
        self.assertEqual(proof["bonus_multiplier"], POW_BONUS["process_only"])

    @patch('pow_miners._probe_node_rpc')
    @patch('pow_miners._get_running_processes')
    def test_generate_monero_p2pool_proof(self, mock_procs, mock_rpc):
        """Should generate P2Pool proof for Monero."""
        mock_procs.return_value = "p2pool"
        mock_rpc.return_value = {
            "endpoint": "localhost:18083",
            "hashrate": 10000,
            "proof_hash": "p2pool123",
        }

        proof = generate_pow_proof("monero", "test_nonce")

        self.assertIsNotNone(proof)
        self.assertEqual(proof["chain"], "monero")

    def test_generate_proof_unknown_chain(self):
        """Should return None for unknown chain."""
        proof = generate_pow_proof("unknown_chain", "test_nonce")
        self.assertIsNone(proof)


class TestSubprocessLaunch(unittest.TestCase):
    """Test subprocess launch functionality."""

    @patch('pow_miners._check_command_exists')
    def test_launch_monero_dry_run(self, mock_check):
        """Dry run should return command without executing."""
        mock_check.return_value = True

        success, proc, msg = launch_miner_subprocess(
            chain="monero",
            wallet="4ABC...xyz",
            pool_url="stratum+tcp://pool.xmr.com:3333",
            dry_run=True,
        )

        self.assertTrue(success)
        self.assertIsNone(proc)
        self.assertIn("Would execute:", msg)
        self.assertIn("xmrig", msg)

    @patch('subprocess.Popen')
    @patch('pow_miners._check_command_exists')
    @patch('pow_miners._get_running_processes')
    def test_launch_monero_xmrig(self, mock_procs, mock_check, mock_popen):
        """Should successfully launch XMRig subprocess."""
        mock_procs.return_value = ""  # No miners running
        mock_check.return_value = True
        mock_popen.return_value = MagicMock(pid=12345)

        success, proc, msg = launch_miner_subprocess(
            chain="monero",
            wallet="4ABC...xyz",
            miner_name="xmrig",
            dry_run=False,
        )

        self.assertTrue(success)
        self.assertIsNotNone(proc)
        self.assertIn("PID: 12345", msg)

    @patch('subprocess.Popen')
    @patch('pow_miners._check_command_exists')
    @patch('pow_miners._get_running_processes')
    def test_launch_monero_already_running(self, mock_procs, mock_check, mock_popen):
        """Should fail if miner already running."""
        mock_procs.return_value = "xmrig --donate-level 1"
        mock_check.return_value = True  # Miner is available

        success, proc, msg = launch_miner_subprocess(
            chain="monero",
            wallet="4ABC...xyz",
        )

        self.assertFalse(success)
        self.assertIsNone(proc)
        self.assertIn("already running", msg)

    @patch('pow_miners._check_command_exists')
    def test_launch_monero_miner_not_found(self, mock_check):
        """Should fail if miner executable not found."""
        mock_check.return_value = False

        success, proc, msg = launch_miner_subprocess(
            chain="monero",
            wallet="4ABC...xyz",
            miner_name="nonexistent_miner",
        )

        self.assertFalse(success)
        self.assertIn("No available miner found", msg)

    @patch('subprocess.run')
    @patch('pow_miners._get_running_processes')
    def test_stop_monero_miner(self, mock_procs, mock_run):
        """Should successfully stop running XMRig miner."""
        mock_procs.return_value = "xmrig --url pool.xmr.com"
        mock_run.return_value = MagicMock(returncode=0)

        success, msg = stop_miner_subprocess("monero")

        self.assertTrue(success)
        self.assertIn("Stopped", msg)

    @patch('pow_miners._get_running_processes')
    def test_stop_monero_miner_not_running(self, mock_procs):
        """Should fail if no miners running."""
        mock_procs.return_value = ""

        success, msg = stop_miner_subprocess("monero")

        self.assertFalse(success)
        self.assertIn("No running miners found", msg)




class TestHelperFunctions(unittest.TestCase):
    """Test helper functions."""

    def test_get_supported_chains(self):
        """Should return list of supported chains."""
        chains = get_supported_chains()
        self.assertIsInstance(chains, list)
        self.assertIn("monero", chains)
        self.assertIn("warthog", chains)
        self.assertIn("ergo", chains)
        self.assertIn("zephyr", chains)

    def test_get_monero_chain_info(self):
        """Should return Monero chain info dict."""
        info = get_chain_info("monero")
        self.assertIsNotNone(info)
        self.assertEqual(info["algo"], "randomx")
        self.assertEqual(info["display"], "Monero (RandomX)")

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

        result = _check_port_open(18081)
        self.assertTrue(result)

    @patch('socket.socket')
    def test_check_port_open_false(self, mock_socket):
        """Should return False for closed port."""
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 1
        mock_socket.return_value = mock_sock

        result = _check_port_open(18081)
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


class TestMoneroIntegration(unittest.TestCase):
    """Monero-specific integration tests."""

    def test_monero_node_rpc_endpoint(self):
        """Monero node RPC should use /json_rpc endpoint."""
        monero = KNOWN_MINERS["monero"]
        self.assertEqual(monero["node_info_path"], "/json_rpc")

    def test_monero_pool_urls(self):
        """Monero pool URLs should be correctly formatted."""
        monero = KNOWN_MINERS["monero"]
        pools = monero["pool_api_templates"]

        # Check P2Pool (local)
        self.assertIn("localhost:18083", pools["p2pool"])

        # Check HeroMiners
        self.assertIn("herominers.com", pools["herominers"])
        self.assertIn("{address}", pools["herominers"])

        # Check NanoPool
        self.assertIn("nanopool.org", pools["nanopool"])
        self.assertIn("{address}", pools["nanopool"])

    def test_monero_xmrig_command(self):
        """xmrig command should include pool, wallet, and donate-level flags."""
        monero = KNOWN_MINERS["monero"]
        xmrig_cmd = monero["miner_commands"]["xmrig"]

        self.assertIn("-o", xmrig_cmd)
        self.assertIn("{pool}", xmrig_cmd)
        self.assertIn("-u", xmrig_cmd)
        self.assertIn("{wallet}", xmrig_cmd)
        self.assertIn("--donate-level", xmrig_cmd)

    def test_monero_xmrig_p2pool_command(self):
        """xmrig-p2pool command should use localhost:3333."""
        monero = KNOWN_MINERS["monero"]
        p2pool_cmd = monero["miner_commands"]["xmrig-p2pool"]

        self.assertIn("localhost:3333", p2pool_cmd)
        self.assertIn("{wallet}", p2pool_cmd)

    def test_monero_monero_command(self):
        """monerod command should include mining flags."""
        monero = KNOWN_MINERS["monero"]
        monerod_cmd = monero["miner_commands"]["monerod"]

        self.assertIn("--start-mining", monerod_cmd)
        self.assertIn("{wallet}", monerod_cmd)
        self.assertIn("--mine-local", monerod_cmd)

    def test_monero_randomx_algo(self):
        """Monero should use RandomX algorithm."""
        monero = KNOWN_MINERS["monero"]
        self.assertEqual(monero["algo"], "randomx")


class TestWarthogIntegration(unittest.TestCase):
    """Warthog-specific integration tests (if available)."""

    def test_warthog_config_exists(self):
        """Warthog should be in KNOWN_MINERS (optional)."""
        # This test passes if warthog exists, skips if not
        if "warthog" in KNOWN_MINERS:
            warthog = KNOWN_MINERS["warthog"]
            self.assertEqual(warthog["algo"], "janushash")


if __name__ == "__main__":
    unittest.main(verbosity=2)
