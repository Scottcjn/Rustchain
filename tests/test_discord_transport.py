#!/usr/bin/env python3
"""
tests/test_discord_transport.py
Transport-level tests for the FlameNet Beacon Discord integration.

Covers:
- 429 rate-limit handling with Retry-After honoured
- Webhook 4xx / 5xx error parsing and retry behaviour
- Dry-run payload shape validation
- Listener poll path (message fetch + last_id tracking)
- build_webhook_payload field validation

Run with:
    python -m pytest tests/test_discord_transport.py -v
"""

import json
import sys
import time
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

# Make sure the package root is importable when run from the repo root
import importlib.util
import os

# rustchain-poa has a hyphen so it can't be imported as a regular package.
# Use importlib to load flame_beacon directly from its path, then register it
# in sys.modules so unittest.mock.patch can resolve "flame_beacon.*".
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FLAME_BEACON_PATH = os.path.join(
    _REPO_ROOT, "rustchain-poa", "net", "flame_beacon.py"
)
_spec = importlib.util.spec_from_file_location("flame_beacon", _FLAME_BEACON_PATH)
flame_beacon = importlib.util.module_from_spec(_spec)
sys.modules["flame_beacon"] = flame_beacon
_spec.loader.exec_module(flame_beacon)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entry(**overrides):
    """Return a minimal valid beacon entry."""
    base = {
        "fingerprint": "deadbeef1234567890ab",
        "device": "Amiga 4000",
        "score": 9001,
        "rom": "Kickstart 3.1",
        "timestamp": "2026-01-01T00:00:00+00:00",
    }
    base.update(overrides)
    return base


def _mock_response(status_code: int, body=None, headers=None):
    """Build a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = headers or {}
    if body is None:
        resp.text = ""
        resp.json.side_effect = ValueError("no body")
    elif isinstance(body, (dict, list)):
        resp.text = json.dumps(body)
        resp.json.return_value = body
    else:
        resp.text = str(body)
        resp.json.side_effect = ValueError("not json")
    return resp


# ---------------------------------------------------------------------------
# build_webhook_payload
# ---------------------------------------------------------------------------

class TestBuildWebhookPayload(unittest.TestCase):

    def test_valid_entry_returns_content_key(self):
        payload = flame_beacon.build_webhook_payload(_make_entry())
        self.assertIn("content", payload)
        self.assertIsInstance(payload["content"], str)

    def test_content_contains_device_and_score(self):
        entry = _make_entry(device="Commodore 64", score=42)
        payload = flame_beacon.build_webhook_payload(entry)
        self.assertIn("Commodore 64", payload["content"])
        self.assertIn("42", payload["content"])

    def test_fingerprint_truncated_to_12_chars(self):
        entry = _make_entry(fingerprint="aabbccddeeff00112233")
        payload = flame_beacon.build_webhook_payload(entry)
        self.assertIn("aabbccddeeff", payload["content"])
        # Full fingerprint should NOT appear
        self.assertNotIn("aabbccddeeff00112233", payload["content"])

    def test_missing_required_field_raises_value_error(self):
        for field in ("device", "score", "rom", "fingerprint"):
            entry = _make_entry()
            del entry[field]
            with self.assertRaises(ValueError, msg=f"Expected ValueError for missing {field}"):
                flame_beacon.build_webhook_payload(entry)

    def test_no_timestamp_uses_fallback(self):
        entry = _make_entry()
        del entry["timestamp"]
        # Should not raise — a fallback timestamp is inserted
        payload = flame_beacon.build_webhook_payload(entry)
        self.assertIn("content", payload)


# ---------------------------------------------------------------------------
# send_to_discord — 204 success
# ---------------------------------------------------------------------------

class TestSendToDiscordSuccess(unittest.TestCase):

    @patch("flame_beacon.requests.post")
    def test_returns_true_on_204(self, mock_post):
        mock_post.return_value = _mock_response(204)
        result = flame_beacon.send_to_discord(_make_entry())
        self.assertTrue(result)

    @patch("flame_beacon.requests.post")
    def test_posts_to_webhook_url(self, mock_post):
        mock_post.return_value = _mock_response(204)
        url = "https://discord.com/api/webhooks/test/token"
        flame_beacon.send_to_discord(_make_entry(), webhook_url=url)
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], url)


# ---------------------------------------------------------------------------
# send_to_discord — dry-run
# ---------------------------------------------------------------------------

class TestSendToDiscordDryRun(unittest.TestCase):

    @patch("flame_beacon.requests.post")
    def test_dry_run_does_not_post(self, mock_post):
        flame_beacon.send_to_discord(_make_entry(), dry_run=True)
        mock_post.assert_not_called()

    @patch("flame_beacon.requests.post")
    def test_dry_run_returns_true_for_valid_entry(self, mock_post):
        result = flame_beacon.send_to_discord(_make_entry(), dry_run=True)
        self.assertTrue(result)

    @patch("flame_beacon.requests.post")
    def test_dry_run_returns_false_for_invalid_entry(self, mock_post):
        entry = _make_entry()
        del entry["device"]
        result = flame_beacon.send_to_discord(entry, dry_run=True)
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# send_to_discord — 429 rate limiting
# ---------------------------------------------------------------------------

class TestSendToDiscord429(unittest.TestCase):

    @patch("flame_beacon.time.sleep")
    @patch("flame_beacon.requests.post")
    def test_retries_after_429_with_retry_after_header(self, mock_post, mock_sleep):
        """First call → 429, second call → 204."""
        mock_post.side_effect = [
            _mock_response(429, headers={"Retry-After": "2"}),
            _mock_response(204),
        ]
        result = flame_beacon.send_to_discord(_make_entry(), max_retries=3)
        self.assertTrue(result)
        # sleep should have been called with the Retry-After value
        mock_sleep.assert_any_call(2.0)

    @patch("flame_beacon.time.sleep")
    @patch("flame_beacon.requests.post")
    def test_respects_retry_after_in_json_body(self, mock_post, mock_sleep):
        """Discord sometimes puts retry_after in the JSON body."""
        body = {"retry_after": 5.5, "message": "You are being rate limited."}
        mock_post.side_effect = [
            _mock_response(429, body=body),
            _mock_response(204),
        ]
        result = flame_beacon.send_to_discord(_make_entry(), max_retries=3)
        self.assertTrue(result)
        mock_sleep.assert_any_call(5.5)

    @patch("flame_beacon.time.sleep")
    @patch("flame_beacon.requests.post")
    def test_exhausts_retries_on_persistent_429(self, mock_post, mock_sleep):
        """When all retries return 429, send_to_discord returns False."""
        mock_post.return_value = _mock_response(429, headers={"Retry-After": "0.01"})
        result = flame_beacon.send_to_discord(_make_entry(), max_retries=3)
        self.assertFalse(result)
        self.assertEqual(mock_post.call_count, 3)


# ---------------------------------------------------------------------------
# send_to_discord — 4xx permanent errors
# ---------------------------------------------------------------------------

class TestSendToDiscord4xx(unittest.TestCase):

    @patch("flame_beacon.requests.post")
    def test_400_does_not_retry(self, mock_post):
        mock_post.return_value = _mock_response(400, body={"code": 50006, "message": "Cannot send empty message"})
        result = flame_beacon.send_to_discord(_make_entry(), max_retries=5)
        self.assertFalse(result)
        # Only one attempt — permanent error, no retry
        self.assertEqual(mock_post.call_count, 1)

    @patch("flame_beacon.requests.post")
    def test_401_does_not_retry(self, mock_post):
        mock_post.return_value = _mock_response(401, body={"message": "401: Unauthorized"})
        result = flame_beacon.send_to_discord(_make_entry(), max_retries=5)
        self.assertFalse(result)
        self.assertEqual(mock_post.call_count, 1)

    @patch("flame_beacon.requests.post")
    def test_404_does_not_retry(self, mock_post):
        mock_post.return_value = _mock_response(404, body={"message": "Unknown Webhook"})
        result = flame_beacon.send_to_discord(_make_entry(), max_retries=5)
        self.assertFalse(result)
        self.assertEqual(mock_post.call_count, 1)


# ---------------------------------------------------------------------------
# send_to_discord — 5xx server errors (retried)
# ---------------------------------------------------------------------------

class TestSendToDiscord5xx(unittest.TestCase):

    @patch("flame_beacon.time.sleep")
    @patch("flame_beacon.requests.post")
    def test_500_retries_and_succeeds(self, mock_post, mock_sleep):
        mock_post.side_effect = [
            _mock_response(500),
            _mock_response(500),
            _mock_response(204),
        ]
        result = flame_beacon.send_to_discord(_make_entry(), max_retries=5)
        self.assertTrue(result)
        self.assertEqual(mock_post.call_count, 3)

    @patch("flame_beacon.time.sleep")
    @patch("flame_beacon.requests.post")
    def test_503_exhausts_all_retries(self, mock_post, mock_sleep):
        mock_post.return_value = _mock_response(503)
        result = flame_beacon.send_to_discord(_make_entry(), max_retries=3)
        self.assertFalse(result)
        self.assertEqual(mock_post.call_count, 3)

    @patch("flame_beacon.time.sleep")
    @patch("flame_beacon.requests.post")
    def test_exponential_backoff_sleep_calls(self, mock_post, mock_sleep):
        """Backoff delays should grow exponentially (base=1.0 by default)."""
        mock_post.return_value = _mock_response(503)
        # Temporarily set RETRY_BASE_DELAY to 1.0 for predictable values
        original = flame_beacon.RETRY_BASE_DELAY
        flame_beacon.RETRY_BASE_DELAY = 1.0
        try:
            flame_beacon.send_to_discord(_make_entry(), max_retries=4)
        finally:
            flame_beacon.RETRY_BASE_DELAY = original

        sleep_calls = [c.args[0] for c in mock_sleep.call_args_list]
        # Each delay should be >= the previous (non-decreasing)
        for i in range(1, len(sleep_calls)):
            self.assertGreaterEqual(
                sleep_calls[i], sleep_calls[i - 1],
                msg=f"Backoff not increasing: {sleep_calls}",
            )


# ---------------------------------------------------------------------------
# send_to_discord — network / connection errors
# ---------------------------------------------------------------------------

class TestSendToDiscordNetworkErrors(unittest.TestCase):

    @patch("flame_beacon.time.sleep")
    @patch("flame_beacon.requests.post")
    def test_connection_error_retried(self, mock_post, mock_sleep):
        import requests as req_lib
        mock_post.side_effect = [
            req_lib.exceptions.ConnectionError("connection refused"),
            _mock_response(204),
        ]
        result = flame_beacon.send_to_discord(_make_entry(), max_retries=3)
        self.assertTrue(result)

    @patch("flame_beacon.time.sleep")
    @patch("flame_beacon.requests.post")
    def test_timeout_retried(self, mock_post, mock_sleep):
        import requests as req_lib
        mock_post.side_effect = [
            req_lib.exceptions.Timeout("timed out"),
            _mock_response(204),
        ]
        result = flame_beacon.send_to_discord(_make_entry(), max_retries=3)
        self.assertTrue(result)


# ---------------------------------------------------------------------------
# Listener mode
# ---------------------------------------------------------------------------

class TestListenerMode(unittest.TestCase):

    @patch("flame_beacon.requests.get")
    def test_fetch_returns_messages_reversed(self, mock_get):
        """API returns newest-first; listener should reverse to chronological."""
        mock_get.return_value = _mock_response(200, body=[
            {"id": "3", "content": "newest"},
            {"id": "2", "content": "middle"},
            {"id": "1", "content": "oldest"},
        ])
        msgs = flame_beacon._fetch_channel_messages("chan123", "Bot token123")
        self.assertEqual(msgs[0]["id"], "1")
        self.assertEqual(msgs[-1]["id"], "3")

    @patch("flame_beacon.requests.get")
    def test_fetch_passes_after_param(self, mock_get):
        mock_get.return_value = _mock_response(200, body=[])
        flame_beacon._fetch_channel_messages("chan123", "Bot token123", after="999")
        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["params"]["after"], "999")

    @patch("flame_beacon.time.sleep")
    @patch("flame_beacon.requests.get")
    def test_fetch_handles_429(self, mock_get, mock_sleep):
        mock_get.return_value = _mock_response(429, headers={"Retry-After": "3"})
        msgs = flame_beacon._fetch_channel_messages("chan123", "Bot token123")
        self.assertEqual(msgs, [])
        mock_sleep.assert_called_once_with(3.0)

    @patch("flame_beacon.requests.get")
    def test_fetch_returns_empty_on_error(self, mock_get):
        mock_get.return_value = _mock_response(500)
        msgs = flame_beacon._fetch_channel_messages("chan123", "Bot token123")
        self.assertEqual(msgs, [])

    @patch("flame_beacon.time.sleep")
    @patch("flame_beacon.requests.get")
    def test_listen_beacon_aborts_without_credentials(self, mock_get, mock_sleep):
        """listen_beacon should return early if channel_id or bot_token is missing."""
        flame_beacon.listen_beacon(channel_id="", bot_token="")
        mock_get.assert_not_called()

    @patch("flame_beacon.time.sleep", side_effect=[None, StopIteration])
    @patch("flame_beacon.requests.get")
    def test_listen_beacon_calls_callback(self, mock_get, mock_sleep):
        """listen_beacon should call event_callback for each new message."""
        messages = [{"id": "10", "content": "hello beacon", "timestamp": "2026-01-01", "author": {"username": "bot"}}]
        mock_get.side_effect = [
            _mock_response(200, body=messages),
            _mock_response(200, body=[]),
        ]
        received = []
        try:
            flame_beacon.listen_beacon(
                channel_id="chan",
                bot_token="tok",
                poll_interval=0.01,
                event_callback=received.append,
            )
        except StopIteration:
            pass
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["id"], "10")

    @patch("flame_beacon.time.sleep", side_effect=[None, StopIteration])
    @patch("flame_beacon.requests.get")
    def test_listen_beacon_advances_last_id(self, mock_get, mock_sleep):
        """The listener must pass the last seen message ID as 'after' on the next poll."""
        first_batch = [
            {"id": "100", "content": "msg1", "timestamp": "", "author": {"username": "a"}},
        ]
        mock_get.side_effect = [
            _mock_response(200, body=first_batch),
            _mock_response(200, body=[]),
        ]
        try:
            flame_beacon.listen_beacon(
                channel_id="chan",
                bot_token="tok",
                poll_interval=0.01,
            )
        except StopIteration:
            pass
        # Second call must have after="100"
        second_call_params = mock_get.call_args_list[1][1]["params"]
        self.assertEqual(second_call_params.get("after"), "100")


# ---------------------------------------------------------------------------
# _backoff_delay helper
# ---------------------------------------------------------------------------

class TestBackoffDelay(unittest.TestCase):

    def test_increases_exponentially(self):
        delays = [flame_beacon._backoff_delay(i) for i in range(6)]
        for i in range(1, len(delays)):
            self.assertGreaterEqual(delays[i], delays[i - 1])

    def test_capped_at_max_delay(self):
        original = flame_beacon.RETRY_MAX_DELAY
        flame_beacon.RETRY_MAX_DELAY = 10.0
        try:
            delay = flame_beacon._backoff_delay(100)
            self.assertLessEqual(delay, 10.0)
        finally:
            flame_beacon.RETRY_MAX_DELAY = original


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
