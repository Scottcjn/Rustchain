"""Unit tests for RustChain SDK."""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from rustchain import RustChainClient, AsyncRustChainClient
from rustchain.exceptions import ValidationError, APIError, ConnectionError
from rustchain.models import HealthStatus, EpochInfo, Miner, Balance, Block, Transaction

# --- Fixtures ---

HEALTH_RESP = {"status": "ok", "uptime": 12345.6, "version": "0.8.1"}
EPOCH_RESP = {"epoch": 42, "start_time": "2026-03-25T00:00:00Z", "end_time": "2026-03-26T00:00:00Z", "miners_active": 15}
MINERS_RESP = [
    {"id": "miner-1", "wallet": "w1", "hardware": "hw1", "score": 95.5, "status": "active"},
    {"id": "miner-2", "wallet": "w2", "hardware": "hw2", "score": 80.0, "status": "idle"},
]
BALANCE_RESP = {"balance": 123.45, "currency": "RTC"}
TRANSFER_RESP = {"tx_hash": "0xabc", "from": "w1", "to": "w2", "amount": 10.0, "status": "confirmed"}
ATTESTATION_RESP = {"attested": True, "epoch": 42, "hardware_hash": "0xdeadbeef"}
BLOCKS_RESP = [{"height": 100, "hash": "0xblock1", "timestamp": "2026-03-25T06:00:00Z", "miner": "m1", "tx_count": 5}]
TXS_RESP = [{"tx_hash": "0xtx1", "from": "w1", "to": "w2", "amount": 2.5, "block_height": 100, "timestamp": "2026-03-25T06:00:00Z"}]

def mock_response(data, status=200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = data
    r.text = str(data)
    return r


class TestHealthParsing:
    def test_parse_health(self):
        with patch("httpx.Client") as MockClient:
            inst = MockClient.return_value
            inst.get.return_value = mock_response(HEALTH_RESP)
            c = RustChainClient.__new__(RustChainClient)
            c._client = inst
            c._base = "http://test"
            from rustchain.client import _ExplorerMixin
            c.explorer = _ExplorerMixin(c._get)
            h = c.health()
            assert isinstance(h, HealthStatus)
            assert h.status == "ok"
            assert h.uptime == 12345.6
            assert h.version == "0.8.1"


class TestEpochParsing:
    def test_parse_epoch(self):
        with patch("httpx.Client") as MockClient:
            inst = MockClient.return_value
            inst.get.return_value = mock_response(EPOCH_RESP)
            c = RustChainClient.__new__(RustChainClient)
            c._client = inst
            c._base = "http://test"
            from rustchain.client import _ExplorerMixin
            c.explorer = _ExplorerMixin(c._get)
            e = c.epoch()
            assert isinstance(e, EpochInfo)
            assert e.epoch == 42
            assert e.miners_active == 15


class TestMinersParsing:
    def test_parse_miners_list(self):
        with patch("httpx.Client") as MockClient:
            inst = MockClient.return_value
            inst.get.return_value = mock_response(MINERS_RESP)
            c = RustChainClient.__new__(RustChainClient)
            c._client = inst
            c._base = "http://test"
            from rustchain.client import _ExplorerMixin
            c.explorer = _ExplorerMixin(c._get)
            miners = c.miners()
            assert len(miners) == 2
            assert miners[0].id == "miner-1"
            assert miners[1].score == 80.0

    def test_parse_miners_dict(self):
        with patch("httpx.Client") as MockClient:
            inst = MockClient.return_value
            inst.get.return_value = mock_response({"miners": MINERS_RESP})
            c = RustChainClient.__new__(RustChainClient)
            c._client = inst
            c._base = "http://test"
            from rustchain.client import _ExplorerMixin
            c.explorer = _ExplorerMixin(c._get)
            miners = c.miners()
            assert len(miners) == 2


class TestBalance:
    def test_parse_balance(self):
        with patch("httpx.Client") as MockClient:
            inst = MockClient.return_value
            inst.get.return_value = mock_response(BALANCE_RESP)
            c = RustChainClient.__new__(RustChainClient)
            c._client = inst
            c._base = "http://test"
            from rustchain.client import _ExplorerMixin
            c.explorer = _ExplorerMixin(c._get)
            b = c.balance("w1")
            assert isinstance(b, Balance)
            assert b.balance == 123.45
            assert b.wallet_id == "w1"

    def test_empty_wallet_raises(self):
        c = RustChainClient.__new__(RustChainClient)
        c._client = MagicMock()
        c._base = "http://test"
        from rustchain.client import _ExplorerMixin
        c.explorer = _ExplorerMixin(c._get)
        with pytest.raises(ValidationError):
            c.balance("")


class TestTransfer:
    def test_parse_transfer(self):
        with patch("httpx.Client") as MockClient:
            inst = MockClient.return_value
            inst.post.return_value = mock_response(TRANSFER_RESP)
            c = RustChainClient.__new__(RustChainClient)
            c._client = inst
            c._base = "http://test"
            from rustchain.client import _ExplorerMixin
            c.explorer = _ExplorerMixin(c._get)
            t = c.transfer("w1", "w2", 10.0, "sig123")
            assert t.tx_hash == "0xabc"
            assert t.amount == 10.0

    def test_negative_amount_raises(self):
        c = RustChainClient.__new__(RustChainClient)
        c._client = MagicMock()
        c._base = "http://test"
        from rustchain.client import _ExplorerMixin
        c.explorer = _ExplorerMixin(c._get)
        with pytest.raises(ValidationError):
            c.transfer("w1", "w2", -5, "sig")

    def test_zero_amount_raises(self):
        c = RustChainClient.__new__(RustChainClient)
        c._client = MagicMock()
        c._base = "http://test"
        from rustchain.client import _ExplorerMixin
        c.explorer = _ExplorerMixin(c._get)
        with pytest.raises(ValidationError):
            c.transfer("w1", "w2", 0, "sig")


class TestAttestation:
    def test_parse_attestation(self):
        with patch("httpx.Client") as MockClient:
            inst = MockClient.return_value
            inst.get.return_value = mock_response(ATTESTATION_RESP)
            c = RustChainClient.__new__(RustChainClient)
            c._client = inst
            c._base = "http://test"
            from rustchain.client import _ExplorerMixin
            c.explorer = _ExplorerMixin(c._get)
            a = c.attestation_status("m1")
            assert a.attested is True
            assert a.epoch == 42

    def test_empty_miner_raises(self):
        c = RustChainClient.__new__(RustChainClient)
        c._client = MagicMock()
        c._base = "http://test"
        from rustchain.client import _ExplorerMixin
        c.explorer = _ExplorerMixin(c._get)
        with pytest.raises(ValidationError):
            c.attestation_status("")


class TestExplorer:
    def test_blocks(self):
        with patch("httpx.Client") as MockClient:
            inst = MockClient.return_value
            inst.get.return_value = mock_response(BLOCKS_RESP)
            c = RustChainClient.__new__(RustChainClient)
            c._client = inst
            c._base = "http://test"
            from rustchain.client import _ExplorerMixin
            c.explorer = _ExplorerMixin(c._get)
            blocks = c.explorer.blocks(5)
            assert len(blocks) == 1
            assert blocks[0].height == 100

    def test_transactions(self):
        with patch("httpx.Client") as MockClient:
            inst = MockClient.return_value
            inst.get.return_value = mock_response(TXS_RESP)
            c = RustChainClient.__new__(RustChainClient)
            c._client = inst
            c._base = "http://test"
            from rustchain.client import _ExplorerMixin
            c.explorer = _ExplorerMixin(c._get)
            txs = c.explorer.transactions(5)
            assert len(txs) == 1
            assert txs[0].amount == 2.5


class TestErrors:
    def test_api_error_on_400(self):
        with patch("httpx.Client") as MockClient:
            inst = MockClient.return_value
            inst.get.return_value = mock_response({"error": "bad"}, status=400)
            c = RustChainClient.__new__(RustChainClient)
            c._client = inst
            c._base = "http://test"
            from rustchain.client import _ExplorerMixin
            c.explorer = _ExplorerMixin(c._get)
            with pytest.raises(APIError) as exc:
                c.health()
            assert exc.value.status_code == 400

    def test_connection_error(self):
        import httpx as hx
        with patch("httpx.Client") as MockClient:
            inst = MockClient.return_value
            inst.get.side_effect = hx.ConnectError("fail")
            c = RustChainClient.__new__(RustChainClient)
            c._client = inst
            c._base = "http://test"
            from rustchain.client import _ExplorerMixin
            c.explorer = _ExplorerMixin(c._get)
            with pytest.raises(ConnectionError):
                c.health()

    def test_timeout_error(self):
        import httpx as hx
        with patch("httpx.Client") as MockClient:
            inst = MockClient.return_value
            inst.get.side_effect = hx.ReadTimeout("timeout")
            c = RustChainClient.__new__(RustChainClient)
            c._client = inst
            c._base = "http://test"
            from rustchain.client import _ExplorerMixin
            c.explorer = _ExplorerMixin(c._get)
            with pytest.raises(Exception):  # TimeoutError
                c.health()


class TestModels:
    def test_health_frozen(self):
        h = HealthStatus(status="ok", uptime=1.0, version="1.0")
        with pytest.raises(Exception):
            h.status = "bad"

    def test_block_frozen(self):
        b = Block(height=1, hash="h", timestamp="t", miner="m", tx_count=0)
        with pytest.raises(Exception):
            b.height = 2

    def test_balance_default_currency(self):
        b = Balance(wallet_id="w", balance=10.0)
        assert b.currency == "RTC"


class TestContextManager:
    def test_sync_context(self):
        with patch("httpx.Client") as MockClient:
            inst = MockClient.return_value
            inst.get.return_value = mock_response(HEALTH_RESP)
            with RustChainClient(node_url="http://test") as c:
                h = c.health()
                assert h.status == "ok"
            inst.close.assert_called()
