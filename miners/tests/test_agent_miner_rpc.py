# SPDX-License-Identifier: MIT
"""
Tests for Agent Miner RPC Server — auth, SSRF, status redaction.

Exercises the security layer added per JeremyZeng77 and Scottcjn review:
  - Bearer token authentication on mutating endpoints
  - Webhook SSRF protection (loopback, RFC1918, link-local, bad schemes)
  - Status redaction for unauthenticated callers
  - Fail-closed non-loopback binding without auth
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Must import Flask app and helpers
import agent_miner_rpc as rpc


class TestSSRFProtection(unittest.TestCase):
    """Test _is_safe_webhook_url rejects dangerous URLs."""

    def test_rejects_loopback_ip(self):
        safe, reason = rpc._is_safe_webhook_url("http://127.0.0.1/hook")
        self.assertFalse(safe)
        self.assertIn("Loopback", reason)

    def test_rejects_loopback_ipv6(self):
        safe, reason = rpc._is_safe_webhook_url("http://[::1]/hook")
        self.assertFalse(safe)
        self.assertIn("Loopback", reason)

    def test_rejects_localhost(self):
        safe, reason = rpc._is_safe_webhook_url("http://localhost/hook")
        self.assertFalse(safe)
        self.assertIn("Blocked hostname", reason)

    def test_rejects_link_local(self):
        safe, reason = rpc._is_safe_webhook_url("http://169.254.169.254/latest")
        self.assertFalse(safe)
        # 169.254.x.x may be caught by is_private or is_link_local depending
        # on Python version; either rejection reason is correct.
        self.assertTrue(
            "Link-local" in reason or "RFC1918" in reason or "private" in reason.lower(),
            f"Expected link-local/private rejection, got: {reason}",
        )

    def test_rejects_rfc1918_10(self):
        safe, reason = rpc._is_safe_webhook_url("http://10.0.0.1/hook")
        self.assertFalse(safe)
        self.assertIn("RFC1918", reason)

    def test_rejects_rfc1918_172(self):
        safe, reason = rpc._is_safe_webhook_url("http://172.16.0.1/hook")
        self.assertFalse(safe)
        self.assertIn("RFC1918", reason)

    def test_rejects_rfc1918_192(self):
        safe, reason = rpc._is_safe_webhook_url("http://192.168.1.1/hook")
        self.assertFalse(safe)
        self.assertIn("RFC1918", reason)

    def test_rejects_ftp_scheme(self):
        safe, reason = rpc._is_safe_webhook_url("ftp://example.com/hook")
        self.assertFalse(safe)
        self.assertIn("http", reason.lower())

    def test_rejects_file_scheme(self):
        safe, reason = rpc._is_safe_webhook_url("file:///etc/passwd")
        self.assertFalse(safe)

    def test_rejects_metadata_google(self):
        safe, reason = rpc._is_safe_webhook_url("http://metadata.google.internal/computeMetadata")
        self.assertFalse(safe)
        self.assertIn("Blocked hostname", reason)

    def test_allows_public_https(self):
        safe, reason = rpc._is_safe_webhook_url("https://hooks.example.com/callback")
        self.assertTrue(safe)

    def test_allows_public_http(self):
        safe, reason = rpc._is_safe_webhook_url("http://hooks.example.com/callback")
        self.assertTrue(safe)

    def test_rejects_empty_url(self):
        safe, reason = rpc._is_safe_webhook_url("")
        self.assertFalse(safe)

    def test_rejects_no_hostname(self):
        safe, reason = rpc._is_safe_webhook_url("http:///path")
        self.assertFalse(safe)


class TestAuthDecorator(unittest.TestCase):
    """Test bearer token authentication on Flask endpoints."""

    def setUp(self):
        rpc.app.config["TESTING"] = True
        self.client = rpc.app.test_client()
        # Reset controller state
        rpc.controller.active = False
        rpc.controller.wallet = None
        rpc.controller.webhooks = []

    def test_health_always_accessible(self):
        """Health endpoint never requires auth."""
        rpc._auth_token = "secret123"
        try:
            resp = self.client.get("/health")
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertEqual(data["status"], "healthy")
        finally:
            rpc._auth_token = None

    def test_start_requires_auth(self):
        """POST /api/mining/start returns 401 without token."""
        rpc._auth_token = "secret123"
        try:
            resp = self.client.post(
                "/api/mining/start",
                json={"wallet": "RTC_test_wallet", "threads": 1},
            )
            self.assertEqual(resp.status_code, 401)
            data = resp.get_json()
            self.assertFalse(data["ok"])
            self.assertIn("Authentication", data["error"])
        finally:
            rpc._auth_token = None

    def test_stop_requires_auth(self):
        """POST /api/mining/stop returns 401 without token."""
        rpc._auth_token = "secret123"
        try:
            resp = self.client.post("/api/mining/stop")
            self.assertEqual(resp.status_code, 401)
        finally:
            rpc._auth_token = None

    def test_threads_requires_auth(self):
        """POST /api/mining/threads returns 401 without token."""
        rpc._auth_token = "secret123"
        try:
            resp = self.client.post(
                "/api/mining/threads",
                json={"threads": 4},
            )
            self.assertEqual(resp.status_code, 401)
        finally:
            rpc._auth_token = None

    def test_webhook_register_requires_auth(self):
        """POST /api/webhooks/register returns 401 without token."""
        rpc._auth_token = "secret123"
        try:
            resp = self.client.post(
                "/api/webhooks/register",
                json={"webhook_url": "https://hooks.example.com/cb"},
            )
            self.assertEqual(resp.status_code, 401)
        finally:
            rpc._auth_token = None

    def test_webhook_list_requires_auth(self):
        """GET /api/webhooks returns 401 without token."""
        rpc._auth_token = "secret123"
        try:
            resp = self.client.get("/api/webhooks")
            self.assertEqual(resp.status_code, 401)
        finally:
            rpc._auth_token = None

    def test_webhook_delete_requires_auth(self):
        """DELETE /api/webhooks returns 401 without token."""
        rpc._auth_token = "secret123"
        try:
            resp = self.client.delete(
                "/api/webhooks",
                json={"webhook_url": "https://hooks.example.com/cb"},
            )
            self.assertEqual(resp.status_code, 401)
        finally:
            rpc._auth_token = None

    def test_valid_token_passes(self):
        """Valid bearer token allows access to mutating endpoints."""
        rpc._auth_token = "secret123"
        try:
            resp = self.client.post(
                "/api/mining/threads",
                json={"threads": 2},
                headers={"Authorization": "Bearer secret123"},
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertTrue(data["ok"])
        finally:
            rpc._auth_token = None

    def test_wrong_token_rejected(self):
        """Wrong bearer token returns 401."""
        rpc._auth_token = "secret123"
        try:
            resp = self.client.post(
                "/api/mining/threads",
                json={"threads": 2},
                headers={"Authorization": "Bearer wrong_token"},
            )
            self.assertEqual(resp.status_code, 401)
        finally:
            rpc._auth_token = None

    def test_no_auth_configured_allows_all(self):
        """When _auth_token is None, all endpoints are open."""
        rpc._auth_token = None
        resp = self.client.post(
            "/api/mining/threads",
            json={"threads": 2},
        )
        self.assertEqual(resp.status_code, 200)


class TestStatusRedaction(unittest.TestCase):
    """Test that status endpoint redacts sensitive fields without auth."""

    def setUp(self):
        rpc.app.config["TESTING"] = True
        self.client = rpc.app.test_client()
        # Set some state
        rpc.controller.wallet = "RTC_secret_wallet"
        rpc.controller.last_balance = 42.5

    def test_authenticated_sees_wallet(self):
        """Authenticated caller sees wallet and balance."""
        rpc._auth_token = "secret123"
        try:
            resp = self.client.get(
                "/api/mining/status",
                headers={"Authorization": "Bearer secret123"},
            )
            data = resp.get_json()
            self.assertIn("wallet", data)
            self.assertEqual(data["wallet"], "RTC_secret_wallet")
            self.assertIn("last_balance_rtc", data)
        finally:
            rpc._auth_token = None

    def test_unauthenticated_wallet_redacted(self):
        """Unauthenticated caller should NOT see wallet or balance."""
        rpc._auth_token = "secret123"
        try:
            resp = self.client.get("/api/mining/status")
            data = resp.get_json()
            self.assertNotIn("wallet", data)
            self.assertNotIn("last_balance_rtc", data)
            # But should still see non-sensitive fields
            self.assertIn("active", data)
            self.assertIn("threads", data)
        finally:
            rpc._auth_token = None

    def test_no_auth_configured_shows_all(self):
        """When auth is disabled, all fields are visible."""
        rpc._auth_token = None
        resp = self.client.get("/api/mining/status")
        data = resp.get_json()
        self.assertIn("wallet", data)
        self.assertIn("last_balance_rtc", data)


class TestWebhookSSRFIntegration(unittest.TestCase):
    """Test that webhook registration rejects SSRF targets via the API."""

    def setUp(self):
        rpc.app.config["TESTING"] = True
        self.client = rpc.app.test_client()
        rpc._auth_token = None  # No auth for simplicity
        rpc.controller.webhooks = []

    def test_register_public_url_succeeds(self):
        resp = self.client.post(
            "/api/webhooks/register",
            json={"webhook_url": "https://hooks.example.com/cb"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["ok"])

    def test_register_loopback_rejected(self):
        resp = self.client.post(
            "/api/webhooks/register",
            json={"webhook_url": "http://127.0.0.1:8080/steal"},
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data["ok"])
        self.assertIn("rejected", data["message"].lower())

    def test_register_metadata_rejected(self):
        resp = self.client.post(
            "/api/webhooks/register",
            json={"webhook_url": "http://169.254.169.254/latest/meta-data"},
        )
        self.assertEqual(resp.status_code, 400)

    def test_register_rfc1918_rejected(self):
        resp = self.client.post(
            "/api/webhooks/register",
            json={"webhook_url": "http://10.0.0.5:9000/internal"},
        )
        self.assertEqual(resp.status_code, 400)


class TestMiningController(unittest.TestCase):
    """Test MiningController basic operations."""

    def setUp(self):
        self.ctrl = rpc.MiningController()

    def test_stop_when_not_active(self):
        ok, msg = self.ctrl.stop()
        self.assertFalse(ok)
        self.assertIn("not active", msg)

    def test_set_threads_clamps(self):
        ok, msg = self.ctrl.set_threads(0)
        self.assertTrue(ok)
        self.assertEqual(self.ctrl.threads, 1)  # clamped to min=1

        ok, msg = self.ctrl.set_threads(100)
        self.assertTrue(ok)
        self.assertEqual(self.ctrl.threads, 64)  # clamped to max=64

    def test_set_threads_normal(self):
        ok, msg = self.ctrl.set_threads(8)
        self.assertTrue(ok)
        self.assertEqual(self.ctrl.threads, 8)

    def test_status_returns_dict(self):
        status = self.ctrl.status()
        self.assertIsInstance(status, dict)
        self.assertIn("active", status)
        self.assertIn("threads", status)
        self.assertFalse(status["active"])

    def test_webhook_register_and_remove(self):
        ok, msg = self.ctrl.register_webhook("https://hooks.example.com/cb")
        self.assertTrue(ok)
        self.assertEqual(len(self.ctrl.webhooks), 1)

        ok, msg = self.ctrl.remove_webhook("https://hooks.example.com/cb")
        self.assertTrue(ok)
        self.assertEqual(len(self.ctrl.webhooks), 0)

    def test_webhook_dedup(self):
        """Registering same URL twice should deduplicate."""
        self.ctrl.register_webhook("https://hooks.example.com/cb")
        self.ctrl.register_webhook("https://hooks.example.com/cb")
        self.assertEqual(len(self.ctrl.webhooks), 1)

    def test_webhook_invalid_event(self):
        ok, msg = self.ctrl.register_webhook(
            "https://hooks.example.com/cb",
            events=["nonexistent_event"],
        )
        self.assertFalse(ok)
        self.assertIn("Unknown event", msg)


if __name__ == "__main__":
    unittest.main()
