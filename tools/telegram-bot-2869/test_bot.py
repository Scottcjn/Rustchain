#!/usr/bin/env python3
"""
Smoke tests for RustChain Telegram Bot (Issue #2869).

Tests cover:
- Rate limiter logic
- API response parsing
- Error handling for offline nodes
- MarkdownV2 escaping
- Configuration validation

Run: python test_bot.py
"""

from __future__ import annotations

import asyncio
import sys
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Test Rate Limiter
# ---------------------------------------------------------------------------

class TestRateLimiter(unittest.TestCase):
    """Test rate limiter with fresh instances to avoid shared state."""

    def test_first_request_allowed(self):
        from bot import RateLimiter
        limiter = RateLimiter(window=5)
        self.assertTrue(limiter.is_allowed(123))

    def test_second_request_within_window_blocked(self):
        from bot import RateLimiter
        limiter = RateLimiter(window=5)
        self.assertTrue(limiter.is_allowed(123))
        self.assertFalse(limiter.is_allowed(123))

    def test_different_users_independent(self):
        from bot import RateLimiter
        limiter = RateLimiter(window=5)
        self.assertTrue(limiter.is_allowed(123))
        self.assertTrue(limiter.is_allowed(456))  # different user

    def test_retry_after_calculation(self):
        from bot import RateLimiter
        limiter = RateLimiter(window=5)
        limiter.is_allowed(123)
        retry = limiter.retry_after(123)
        self.assertGreater(retry, 0)
        self.assertLessEqual(retry, 5)

    def test_retry_after_for_unused_user(self):
        from bot import RateLimiter
        limiter = RateLimiter(window=5)
        retry = limiter.retry_after(999)
        self.assertEqual(retry, 5.0)

    def test_window_expiry(self):
        """After window passes, user can request again."""
        from bot import RateLimiter
        limiter = RateLimiter(window=5)
        limiter.is_allowed(123)
        # Manually advance the last_hit time
        limiter._last_hit[123] = time.monotonic() - 6
        self.assertTrue(limiter.is_allowed(123))


# ---------------------------------------------------------------------------
# Test API Error Handling
# ---------------------------------------------------------------------------

class TestAPIErrorHandling(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, ".")
        from bot import RustChainAPI, _error_text
        self.api = RustChainAPI("https://rustchain.org")
        self._error_text = _error_text

    def test_error_text_extracts_internal_error(self):
        data = {"_error": "Node is unreachable."}
        self.assertEqual(self._error_text(data), "Node is unreachable.")

    def test_error_text_extracts_standard_error(self):
        data = {"error": "Something went wrong"}
        self.assertEqual(self._error_text(data), "Something went wrong")

    def test_error_text_returns_empty_for_ok_response(self):
        data = {"ok": True, "amount_rtc": 42.0}
        self.assertEqual(self._error_text(data), "")

    def test_connect_error_message(self):
        """Verify that connect errors produce user-friendly messages."""
        data = {"_error": "Node is unreachable. The RustChain node may be offline."}
        err = self._error_text(data)
        self.assertIn("unreachable", err.lower())
        self.assertIn("offline", err.lower())


# ---------------------------------------------------------------------------
# Test API Response Parsing (mocked)
# ---------------------------------------------------------------------------

class TestAPIResponseParsing(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        sys.path.insert(0, ".")
        from bot import RustChainAPI
        self.api = RustChainAPI("https://rustchain.org")

    async def test_balance_parsing(self):
        mock_response = {"amount_i64": 42500000, "amount_rtc": 42.5, "miner_id": "test-wallet"}
        with patch.object(self.api, '_get', new_callable=AsyncMock, return_value=mock_response):
            result = await self.api.balance("test-wallet")
            self.assertEqual(result["amount_rtc"], 42.5)
            self.assertEqual(result["miner_id"], "test-wallet")

    async def test_epoch_parsing(self):
        mock_response = {
            "blocks_per_epoch": 144,
            "enrolled_miners": 17,
            "epoch": 129,
            "epoch_pot": 1.5,
            "slot": 18686,
            "total_supply_rtc": 8388608,
        }
        with patch.object(self.api, '_get', new_callable=AsyncMock, return_value=mock_response):
            result = await self.api.epoch()
            self.assertEqual(result["epoch"], 129)
            self.assertEqual(result["enrolled_miners"], 17)
            self.assertEqual(result["total_supply_rtc"], 8388608)

    async def test_miners_parsing(self):
        mock_response = {
            "miners": [
                {
                    "miner": "test-miner",
                    "hardware_type": "Apple Silicon (Modern)",
                    "device_arch": "M4",
                    "antiquity_multiplier": 1.05,
                }
            ]
        }
        with patch.object(self.api, '_get', new_callable=AsyncMock, return_value=mock_response):
            result = await self.api.miners()
            self.assertIsInstance(result["miners"], list)
            self.assertEqual(len(result["miners"]), 1)

    async def test_health_parsing(self):
        mock_response = {
            "ok": True,
            "version": "2.2.1-rip200",
            "uptime_s": 336071,
            "db_rw": True,
            "tip_age_slots": 0,
        }
        with patch.object(self.api, '_get', new_callable=AsyncMock, return_value=mock_response):
            result = await self.api.health()
            self.assertTrue(result["ok"])
            self.assertEqual(result["version"], "2.2.1-rip200")


# ---------------------------------------------------------------------------
# Test MarkdownV2 Escaping
# ---------------------------------------------------------------------------

class TestMarkdownEscape(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, ".")
        from bot import _md_escape
        self.escape = _md_escape

    def test_underscore_escaped(self):
        self.assertEqual(self.escape("hello_world"), "hello\\_world")

    def test_dot_escaped(self):
        self.assertEqual(self.escape("rustchain.org"), "rustchain\\.org")

    def test_parentheses_escaped(self):
        self.assertEqual(self.escape("x(1.05)"), "x\\(1\\.05\\)")

    def test_no_special_chars_unchanged(self):
        self.assertEqual(self.escape("hello"), "hello")

    def test_complex_string(self):
        result = self.escape("Apple Silicon (Modern) x1.05")
        self.assertIn("\\(", result)
        self.assertIn("\\)", result)
        self.assertIn("\\.", result)


# ---------------------------------------------------------------------------
# Test Configuration Validation
# ---------------------------------------------------------------------------

class TestConfigValidation(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, ".")

    @patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": ""}, clear=True)
    def test_missing_token_returns_false(self):
        # Re-import to pick up patched env
        import importlib
        import bot
        importlib.reload(bot)
        self.assertFalse(bot.validate_config())

    @patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "test-token-123"}, clear=True)
    def test_valid_token_returns_true(self):
        import importlib
        import bot
        importlib.reload(bot)
        self.assertTrue(bot.validate_config())


# ---------------------------------------------------------------------------
# Test Uptime Formatting
# ---------------------------------------------------------------------------

class TestUptimeFormatting(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, ".")
        from bot import _fmt_uptime
        self.fmt = _fmt_uptime

    def test_zero_uptime(self):
        self.assertEqual(self.fmt(0), "0d 0h 0m")

    def test_one_day(self):
        self.assertEqual(self.fmt(86400), "1d 0h 0m")

    def test_hours_and_minutes(self):
        self.assertEqual(self.fmt(3661), "0d 1h 1m")

    def test_complex(self):
        self.assertEqual(self.fmt(336071), "3d 21h 21m")


# ---------------------------------------------------------------------------
# Test Real API Connectivity (integration smoke test)
# ---------------------------------------------------------------------------

class TestRealAPIConnectivity(unittest.IsolatedAsyncioTestCase):
    """These tests hit the real RustChain node — skip if offline."""

    async def test_health_endpoint(self):
        sys.path.insert(0, ".")
        from bot import RustChainAPI
        api = RustChainAPI("https://rustchain.org")
        try:
            result = await api.health()
            self.assertNotIn("_error", result)
            self.assertIn("ok", result)
        finally:
            await api.close()

    async def test_epoch_endpoint(self):
        sys.path.insert(0, ".")
        from bot import RustChainAPI
        api = RustChainAPI("https://rustchain.org")
        try:
            result = await api.epoch()
            self.assertNotIn("_error", result)
            self.assertIn("epoch", result)
        finally:
            await api.close()

    async def test_balance_endpoint(self):
        sys.path.insert(0, ".")
        from bot import RustChainAPI
        api = RustChainAPI("https://rustchain.org")
        try:
            result = await api.balance("test")
            self.assertNotIn("_error", result)
            self.assertIn("amount_rtc", result)
        finally:
            await api.close()

    async def test_miners_endpoint(self):
        sys.path.insert(0, ".")
        from bot import RustChainAPI
        api = RustChainAPI("https://rustchain.org")
        try:
            result = await api.miners()
            self.assertNotIn("_error", result)
            self.assertIn("miners", result)
            self.assertIsInstance(result["miners"], list)
        finally:
            await api.close()


# ---------------------------------------------------------------------------
# Test Offline Node Error Handling
# ---------------------------------------------------------------------------

class TestOfflineNodeHandling(unittest.IsolatedAsyncioTestCase):
    async def test_unreachable_node_returns_friendly_error(self):
        sys.path.insert(0, ".")
        from bot import RustChainAPI
        api = RustChainAPI("https://192.0.2.1", timeout=3)  # TEST-NET-1, always unreachable
        try:
            result = await api.health()
            self.assertIn("_error", result)
            self.assertIn("unreachable", result["_error"].lower())
        finally:
            await api.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
