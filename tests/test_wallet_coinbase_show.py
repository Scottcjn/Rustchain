"""
Regression tests for ClawRTC wallet coinbase show command.

Tests for issue #1490: Fix clawrtc wallet show false offline state.

The bug: `clawrtc wallet coinbase show` would incorrectly report wallet as offline
even when the wallet file exists and is valid. This was caused by:
1. Missing CLI entry point to properly dispatch wallet commands
2. No proper error handling for missing wallet files

This test suite ensures:
- Wallet show command works when wallet file exists
- Wallet show command handles missing wallet gracefully
- Wallet show command handles corrupted wallet files
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add wallet directory to path
wallet_dir = Path(__file__).parent.parent / "wallet"
sys.path.insert(0, str(wallet_dir))

from coinbase_wallet import (
    _load_coinbase_wallet,
    _save_coinbase_wallet,
    coinbase_show,
    cmd_coinbase,
    COINBASE_FILE,
    INSTALL_DIR,
)


class TestCoinbaseWalletShow(unittest.TestCase):
    """Test cases for coinbase_show function."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for test wallet files
        self.temp_dir = tempfile.mkdtemp()
        self.original_install_dir = INSTALL_DIR
        self.original_coinbase_file = COINBASE_FILE
        
        # Patch the INSTALL_DIR and COINBASE_FILE to use temp directory
        import coinbase_wallet
        coinbase_wallet.INSTALL_DIR = self.temp_dir
        coinbase_wallet.COINBASE_FILE = os.path.join(self.temp_dir, "coinbase_wallet.json")

    def tearDown(self):
        """Clean up test fixtures."""
        # Restore original values
        import coinbase_wallet
        coinbase_wallet.INSTALL_DIR = self.original_install_dir
        coinbase_wallet.COINBASE_FILE = self.original_coinbase_file
        
        # Clean up temp directory
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_load_wallet_exists(self):
        """Test loading a valid wallet file."""
        wallet_data = {
            "address": "0x1234567890abcdef1234567890abcdef12345678",
            "network": "Base (eip155:8453)",
            "created": "2026-03-09T12:00:00Z",
            "method": "agentkit",
        }
        _save_coinbase_wallet(wallet_data)
        
        loaded = _load_coinbase_wallet()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["address"], wallet_data["address"])
        self.assertEqual(loaded["network"], wallet_data["network"])

    def test_load_wallet_missing(self):
        """Test loading when wallet file doesn't exist."""
        loaded = _load_coinbase_wallet()
        self.assertIsNone(loaded)

    def test_load_wallet_corrupted(self):
        """Test loading a corrupted wallet file."""
        # Write invalid JSON
        with open(os.path.join(self.temp_dir, "coinbase_wallet.json"), "w") as f:
            f.write("{ invalid json }")
        
        loaded = _load_coinbase_wallet()
        self.assertIsNone(loaded)

    def test_coinbase_show_wallet_exists(self):
        """Test coinbase_show with valid wallet - should NOT show offline state."""
        wallet_data = {
            "address": "0x1234567890abcdef1234567890abcdef12345678",
            "network": "Base (eip155:8453)",
            "created": "2026-03-09T12:00:00Z",
            "method": "agentkit",
        }
        _save_coinbase_wallet(wallet_data)
        
        # Capture stdout
        import io
        from contextlib import redirect_stdout
        
        f = io.StringIO()
        with redirect_stdout(f):
            coinbase_show(MagicMock())
        
        output = f.getvalue()
        
        # Verify wallet info is displayed (not offline error)
        self.assertIn("Coinbase Base Wallet", output)
        self.assertIn("0x1234567890abcdef1234567890abcdef12345678", output)
        self.assertIn("Base (eip155:8453)", output)
        # Critical: should NOT show "No Coinbase wallet found" error
        self.assertNotIn("No Coinbase wallet found", output)

    def test_coinbase_show_wallet_missing(self):
        """Test coinbase_show when wallet is missing - should show helpful error."""
        import io
        from contextlib import redirect_stdout
        
        f = io.StringIO()
        with redirect_stdout(f):
            coinbase_show(MagicMock())
        
        output = f.getvalue()
        
        # Verify appropriate error message (not false offline state)
        self.assertIn("No Coinbase wallet found", output)
        self.assertIn("clawrtc wallet coinbase create", output)
        self.assertIn("clawrtc wallet coinbase link", output)

    def test_cmd_coinbase_show_dispatch(self):
        """Test cmd_coinbase properly dispatches 'show' action."""
        wallet_data = {
            "address": "0xabcdef1234567890abcdef1234567890abcdef12",
            "network": "Base (eip155:8453)",
            "created": "2026-03-09T12:00:00Z",
            "method": "manual_link",
        }
        _save_coinbase_wallet(wallet_data)
        
        args = MagicMock()
        args.coinbase_action = "show"
        
        import io
        from contextlib import redirect_stdout
        
        f = io.StringIO()
        with redirect_stdout(f):
            cmd_coinbase(args)
        
        output = f.getvalue()
        self.assertIn("Coinbase Base Wallet", output)
        self.assertIn("0xabcdef1234567890abcdef1234567890abcdef12", output)

    def test_cmd_coinbase_default_action(self):
        """Test cmd_coinbase defaults to 'show' when no action specified."""
        wallet_data = {
            "address": "0xfedcba0987654321fedcba0987654321fedcba09",
            "network": "Base (eip155:8453)",
            "created": "2026-03-09T12:00:00Z",
            "method": "agentkit",
        }
        _save_coinbase_wallet(wallet_data)
        
        args = MagicMock()
        args.coinbase_action = None  # No action specified
        
        import io
        from contextlib import redirect_stdout
        
        f = io.StringIO()
        with redirect_stdout(f):
            cmd_coinbase(args)
        
        output = f.getvalue()
        # Should default to show and display wallet info
        self.assertIn("Coinbase Base Wallet", output)


class TestWalletFilePermissions(unittest.TestCase):
    """Test wallet file security and permissions."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        import coinbase_wallet
        coinbase_wallet.INSTALL_DIR = self.temp_dir
        coinbase_wallet.COINBASE_FILE = os.path.join(self.temp_dir, "coinbase_wallet.json")

    def tearDown(self):
        """Clean up test fixtures."""
        import coinbase_wallet
        import shutil
        coinbase_wallet.INSTALL_DIR = "/tmp/.clawrtc"  # Restore default
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_wallet_file_permissions(self):
        """Test that wallet file is created with secure permissions (0o600)."""
        wallet_data = {
            "address": "0x1234567890abcdef1234567890abcdef12345678",
            "network": "Base (eip155:8453)",
            "created": "2026-03-09T12:00:00Z",
            "method": "agentkit",
        }
        _save_coinbase_wallet(wallet_data)
        
        wallet_file = os.path.join(self.temp_dir, "coinbase_wallet.json")
        self.assertTrue(os.path.exists(wallet_file))
        
        # Check file permissions (should be 0o600 = owner read/write only)
        file_stat = os.stat(wallet_file)
        file_mode = file_stat.st_mode & 0o777
        self.assertEqual(file_mode, 0o600)


if __name__ == "__main__":
    unittest.main()
