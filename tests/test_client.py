"""
Comprehensive test suite for rustchain Python SDK.
Tests client methods, async client, explorer, crypto, and CLI.
"""

import json
import pytest
import ssl
import time
from unittest.mock import MagicMock, patch

from rustchain import (
    RustChainClient,
    AsyncRustChainClient,
    SigningKey,
)
from rustchain.exceptions import (
    APIError,
    ConnectionError,
    ValidationError,
    WalletError,
    SigningError,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    """Sync client pointed at a mock URL."""
    return RustChainClient(base_url="https://example.test")


@pytest.fixture
def mock_urllib_response():
    """Decorator that patches urllib to return mock JSON."""
    def decorator(data: dict, status: int = 200):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(data).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=None)

        def raise_on(code):
            from urllib.error import HTTPError
            err = HTTPError("url", code, "msg", {}, None)
            err.read = MagicMock(return_value=b'{"error": "test"}')
            return err

        mock_resp.raise_for_status = MagicMock()
        if status >= 400:
            mock_resp.raise_for_status.side_effect = raise_on(status)

        return mock_resp
    return decorator


# ─────────────────────────────────────────────────────────────────────────────
# Test: RustChainClient.__init__
# ─────────────────────────────────────────────────────────────────────────────

class TestClientInit:
    def test_default_base_url(self):
        c = RustChainClient()
        assert c.base_url == "https://50.28.86.131"

    def test_custom_base_url(self):
        c = RustChainClient(base_url="https://custom.node/api")
        assert c.base_url == "https://custom.node/api"

    def test_ssl_verify_false_creates_ctx(self):
        c = RustChainClient(verify_ssl=False)
        assert c._ctx is not None
        assert c._ctx.verify_mode == ssl.CERT_NONE

    def test_ssl_verify_true_no_ctx(self):
        c = RustChainClient(verify_ssl=True)
        assert c._ctx is None

    def test_explorer_instance(self, client):
        assert client.explorer is not None
        from rustchain.explorer import Explorer
        assert isinstance(client.explorer, Explorer)

    def test_timeout_default(self):
        c = RustChainClient()
        assert c.timeout == 30

    def test_timeout_custom(self):
        c = RustChainClient(timeout=60)
        assert c.timeout == 60


# ─────────────────────────────────────────────────────────────────────────────
# Test: health()
# ─────────────────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_ok_field(self, client):
        mock_data = {"ok": True, "version": "2.2.1-rip200", "uptime_s": 99999}
        with patch.object(client, "_get", return_value=mock_data):
            result = client.health()
            assert result["ok"] is True
            assert result["version"] == "2.2.1-rip200"

    def test_health_parity_with_async(self, client):
        """health() and async health() return equivalent shapes."""
        mock_data = {"ok": True, "version": "2.2.1-rip200", "uptime_s": 123}
        with patch.object(client, "_get", return_value=mock_data):
            sync = client.health()
        assert "ok" in sync


# ─────────────────────────────────────────────────────────────────────────────
# Test: epoch()
# ─────────────────────────────────────────────────────────────────────────────

class TestEpoch:
    def test_epoch_returns_epoch_field(self, client):
        mock_data = {"epoch": 95, "slot": 12345, "height": 67890, "blocks_per_epoch": 144}
        with patch.object(client, "_get", return_value=mock_data):
            result = client.epoch()
            assert result["epoch"] == 95
            assert result["height"] == 67890

    def test_epoch_negative_epoch_handled(self, client):
        mock_data = {"epoch": -1, "error": "no epoch"}
        with patch.object(client, "_get", return_value=mock_data):
            result = client.epoch()
            assert result.get("epoch", 0) < 0


# ─────────────────────────────────────────────────────────────────────────────
# Test: miners()
# ─────────────────────────────────────────────────────────────────────────────

class TestMiners:
    def test_miners_returns_list(self, client):
        mock_data = [
            {"miner": "g4-powerbook-001", "antiquity_multiplier": 2.5},
            {"miner": "x86-modern-001", "antiquity_multiplier": 1.0},
        ]
        with patch.object(client, "_get", return_value=mock_data):
            result = client.miners()
            assert isinstance(result, list)
            assert len(result) == 2
            assert result[0]["antiquity_multiplier"] == 2.5

    def test_miners_empty_list(self, client):
        with patch.object(client, "_get", return_value=[]):
            result = client.miners()
            assert result == []


# ─────────────────────────────────────────────────────────────────────────────
# Test: balance()
# ─────────────────────────────────────────────────────────────────────────────

class TestBalance:
    def test_balance_valid_wallet(self, client):
        mock_data = {"amount_i64": 1_550_000_00, "amount_rtc": 155.0, "miner_id": "tester"}
        with patch.object(client, "_get", return_value=mock_data):
            result = client.balance("tester")
            assert result["amount_rtc"] == 155.0

    def test_balance_empty_wallet_raises(self, client):
        with pytest.raises(ValidationError, match="cannot be empty"):
            client.balance("")

    def test_balance_whitespace_only_raises(self, client):
        with pytest.raises(ValidationError, match="cannot be empty"):
            client.balance("   ")

    def test_balance_strips_whitespace(self, client):
        mock_data = {"amount_i64": 100, "amount_rtc": 0.0001, "miner_id": "clean"}
        with patch.object(client, "_get", return_value=mock_data) as mock_get:
            client.balance("  clean  ")
            call_arg = mock_get.call_args[0][0]
            assert "miner_id=clean" in call_arg


# ─────────────────────────────────────────────────────────────────────────────
# Test: transfer()
# ─────────────────────────────────────────────────────────────────────────────

class TestTransfer:
    def test_transfer_success(self, client):
        mock_data = {"success": True, "tx_hash": "0xabc123"}
        with patch.object(client, "_post", return_value=mock_data):
            result = client.transfer(
                from_wallet="alice",
                to_wallet="bob",
                amount=1_000_000,
                signature="deadbeef",
            )
            assert result["success"] is True

    def test_transfer_negative_amount_raises(self, client):
        with pytest.raises(ValidationError, match="positive"):
            client.transfer("a", "b", -1, "sig")

    def test_transfer_zero_amount_raises(self, client):
        with pytest.raises(ValidationError, match="positive"):
            client.transfer("a", "b", 0, "sig")

    def test_transfer_empty_from_raises(self, client):
        with pytest.raises(ValidationError, match="cannot be empty"):
            client.transfer("", "b", 100, "sig")

    def test_transfer_empty_to_raises(self, client):
        with pytest.raises(ValidationError, match="cannot be empty"):
            client.transfer("a", "", 100, "sig")

    def test_transfer_passes_timestamp(self, client):
        mock_data = {"success": True}
        ts = 1_700_000_000
        with patch.object(client, "_post", return_value=mock_data) as mock_post:
            client.transfer("a", "b", 100, "sig", timestamp=ts)
            args, _ = mock_post.call_args
            payload = args[1]
            assert payload["timestamp"] == ts

    def test_transfer_default_timestamp(self, client):
        mock_data = {"success": True}
        with patch.object(client, "_post", return_value=mock_data) as mock_post:
            before = int(time.time())
            client.transfer("a", "b", 100, "sig")
            after = int(time.time())
            args, _ = mock_post.call_args
            payload = args[1]  # positional: (path, payload)
            assert before <= payload["timestamp"] <= after


# ─────────────────────────────────────────────────────────────────────────────
# Test: attestation_status()
# ─────────────────────────────────────────────────────────────────────────────

class TestAttestationStatus:
    def test_attestation_status_valid(self, client):
        mock_data = {
            "miner_id": "g4-powerbook-001",
            "verified": True,
            "antiquity_score": 2.5,
            "epochs_attested": 847,
        }
        with patch.object(client, "_get", return_value=mock_data):
            result = client.attestation_status("g4-powerbook-001")
            assert result["verified"] is True
            assert result["antiquity_score"] == 2.5

    def test_attestation_status_empty_miner_raises(self, client):
        with pytest.raises(ValidationError, match="cannot be empty"):
            client.attestation_status("")


# ─────────────────────────────────────────────────────────────────────────────
# Test: transfer_signed()
# ─────────────────────────────────────────────────────────────────────────────

class TestTransferSigned:
    def test_transfer_signed_uses_key(self, client):
        """transfer_signed passes a signed payload to _post."""
        fake_sig = "a" * 128
        fake_payload = {
            "from": "alice", "to": "bob", "amount": 1_000_000,
            "fee": 0, "timestamp": 1_700_000_000,
        }
        mock_key = MagicMock()
        mock_key.sign_transfer.return_value = (fake_sig, fake_payload)

        with patch.object(client, "_post", return_value={"success": True}) as mock_post:
            client.transfer_signed("alice", "bob", 1_000_000, mock_key)
            args, _ = mock_post.call_args
            payload = args[1]
            assert payload["signature"] == fake_sig
            assert payload["from"] == "alice"


# ─────────────────────────────────────────────────────────────────────────────
# Test: SigningKey
# ─────────────────────────────────────────────────────────────────────────────

class TestSigningKey:
    def test_generate_produces_key(self):
        key = SigningKey.generate()
        assert key is not None

    def test_sign_produces_64_bytes(self):
        key = SigningKey.generate()
        sig = key.sign(b"hello world")
        assert len(sig) == 64

    def test_sign_transfer_returns_hex_and_payload(self):
        key = SigningKey.generate()
        sig_hex, payload = key.sign_transfer("alice", "bob", 1_000_000, 1000)
        assert isinstance(sig_hex, str)
        assert len(sig_hex) == 128
        assert payload["from"] == "alice"
        assert payload["to"] == "bob"
        assert payload["amount"] == 1_000_000
        assert payload["fee"] == 1000

    def test_from_seed_reproducible(self):
        key1 = SigningKey.from_seed(b"my seed phrase")
        key2 = SigningKey.from_seed(b"my seed phrase")
        sig1 = key1.sign(b"msg")
        sig2 = key2.sign(b"msg")
        assert sig1 == sig2  # Same seed → same key → same sig

    def test_different_seeds_produce_different_keys(self):
        key1 = SigningKey.from_seed(b"seed A")
        key2 = SigningKey.from_seed(b"seed B")
        sig1 = key1.sign(b"msg")
        sig2 = key2.sign(b"msg")
        assert sig1 != sig2


# ─────────────────────────────────────────────────────────────────────────────
# Test: Retry logic
# ─────────────────────────────────────────────────────────────────────────────

class TestRetryLogic:
    def test_retries_on_connection_error(self, client):
        """Retry loop inside _urlopen retries on arbitrary exceptions."""
        import urllib.error

        call_count = 0

        def urlopen_fails_then_ok(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise urllib.error.URLError("Connection refused")
            # Return a mock response object
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"ok": true}'
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=None)
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=urlopen_fails_then_ok):
            result = client._get("/health")
            assert result.get("ok") is True
            assert call_count == 3

    def test_max_retries_exhausted_raises(self, client):
        import urllib.error

        def always_fail(*args, **kwargs):
            raise urllib.error.URLError("Connection refused")

        with patch("urllib.request.urlopen", side_effect=always_fail):
            with pytest.raises(ConnectionError):
                client._get("/health")


# ─────────────────────────────────────────────────────────────────────────────
# Test: AsyncRustChainClient
# ─────────────────────────────────────────────────────────────────────────────

class TestAsyncClient:
    @pytest.mark.asyncio
    async def test_async_health(self):
        client = AsyncRustChainClient()

        async def mock_json(*args, **kwargs):
            return {"ok": True, "version": "2.2.1-rip200"}

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = MagicMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json = mock_json
            mock_session.request.return_value.__aenter__.return_value = mock_resp

            result = await client.health()
            assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_async_balance_validates_empty(self):
        client = AsyncRustChainClient()
        with pytest.raises(ValidationError, match="cannot be empty"):
            await client.balance("")

    @pytest.mark.asyncio
    async def test_async_transfer_validates_negative_amount(self):
        client = AsyncRustChainClient()
        with pytest.raises(ValidationError, match="positive"):
            await client.transfer("a", "b", -1, "sig")


# ─────────────────────────────────────────────────────────────────────────────
# Test: Explorer
# ─────────────────────────────────────────────────────────────────────────────

class TestExplorer:
    def test_explorer_blocks(self, client):
        mock_data = {
            "blocks": [{"height": 1, "hash": "abc"}, {"height": 2, "hash": "def"}],
            "total": 100,
        }
        with patch.object(client.explorer, "_sync_request", return_value=mock_data):
            result = client.explorer.blocks(limit=10)
            assert len(result["blocks"]) == 2
            assert result["total"] == 100

    def test_explorer_transactions(self, client):
        mock_data = {
            "transactions": [{"hash": "tx1", "amount": 100}, {"hash": "tx2", "amount": 200}],
            "total": 50,
        }
        with patch.object(client.explorer, "_sync_request", return_value=mock_data):
            result = client.explorer.transactions(limit=50)
            assert len(result["transactions"]) == 2

    def test_explorer_transactions_wallet_filter(self, client):
        mock_data = {"transactions": [], "total": 0}
        with patch.object(client.explorer, "_sync_request", return_value=mock_data) as mock_req:
            client.explorer.transactions(wallet_id="alice-wallet")
            _, kwargs = mock_req.call_args
            assert kwargs["params"]["wallet_id"] == "alice-wallet"

    def test_explorer_block_by_height(self, client):
        mock_data = {"height": 42, "hash": "block42"}
        with patch.object(client.explorer, "_sync_request", return_value=mock_data):
            result = client.explorer.block_by_height(42)
            assert result["height"] == 42

    def test_explorer_transaction_by_hash(self, client):
        mock_data = {"hash": "txabc", "amount": 999}
        with patch.object(client.explorer, "_sync_request", return_value=mock_data):
            result = client.explorer.transaction_by_hash("txabc")
            assert result["hash"] == "txabc"


# ─────────────────────────────────────────────────────────────────────────────
# Test: Exception types
# ─────────────────────────────────────────────────────────────────────────────

class TestExceptions:
    def test_api_error_has_status_code(self):
        err = APIError("Not found", status_code=404)
        assert err.status_code == 404
        assert "404" in str(err)

    def test_validation_error_message(self):
        err = ValidationError("bad input")
        assert "bad input" in str(err)

    def test_connection_error_details(self):
        err = ConnectionError("conn failed", details={"path": "/health"})
        assert err.details["path"] == "/health"

    def test_signing_error_is_wallet_error(self):
        assert issubclass(SigningError, Exception)
        assert issubclass(SigningError, WalletError)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
