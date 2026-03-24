# -*- coding: utf-8 -*-
"""
RustChain SDK - Unit Tests (25 tests)
Run with: pytest test_sdk.py -v
"""
import pytest, asyncio, hashlib
from unittest.mock import AsyncMock, patch, MagicMock
from rustchain_sdk.client import RustChainClient
from rustchain_sdk.exceptions import APIError, ValidationError
from rustchain_sdk.models import Epoch, Miner, Wallet, Transaction, Block, Attestation

# ─── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    return RustChainClient(node_url="https://test.example.com")

# ─── Test Models ────────────────────────────────────────────────────────────

class TestModels:
    def test_epoch_from_dict(self):
        d = {
            "epoch_number": 42,
            "start_block": 1000,
            "end_block": 2000,
            "total_rewards": 1500.5,
            "miners_count": 128
        }
        e = Epoch.from_dict(d)
        assert e.number == 42
        assert e.start_block == 1000
        assert e.end_block == 2000
        assert e.total_rewards == 1500.5
        assert e.miners_count == 128

    def test_miner_from_dict(self):
        d = {
            "miner_id": "miner-abc123",
            "architecture": "POWER8",
            "hashrate": 10.5,
            "attestation_score": 0.94,
            "last_seen": "2026-03-24T00:00:00Z"
        }
        m = Miner.from_dict(d)
        assert m.miner_id == "miner-abc123"
        assert m.architecture == "POWER8"
        assert m.hashrate == 10.5
        assert m.attestation_score == 0.94

    def test_wallet_from_dict(self):
        d = {"wallet_id": "w1", "balance": 500.0, "locked": 50.0, "pending": 10.0}
        w = Wallet.from_dict(d)
        assert w.wallet_id == "w1"
        assert w.balance == 500.0
        assert w.locked == 50.0
        assert w.pending == 10.0

    def test_transaction_from_dict(self):
        d = {
            "tx_hash": "0xtxhash",
            "from": "wallet-a",
            "to": "wallet-b",
            "amount": 100.0,
            "timestamp": "2026-03-24T00:00:00Z",
            "status": "confirmed"
        }
        t = Transaction.from_dict(d)
        assert t.tx_hash == "0xtxhash"
        assert t.amount == 100.0
        assert t.status == "confirmed"

    def test_block_from_dict(self):
        d = {
            "block_number": 999,
            "hash": "0xblockhash",
            "timestamp": "2026-03-24T00:00:00Z",
            "miner": "miner-x",
            "tx_count": 5,
            "attestations": 12
        }
        b = Block.from_dict(d)
        assert b.number == 999
        assert b.tx_count == 5

    def test_attestation_from_dict(self):
        d = {
            "miner_id": "m1",
            "score": 0.88,
            "fingerprint": "fp123",
            "status": "verified",
            "last_attestation": "2026-03-24T00:00:00Z"
        }
        a = Attestation.from_dict(d)
        assert a.miner_id == "m1"
        assert a.score == 0.88
        assert a.status == "verified"

# ─── Test Client Methods ────────────────────────────────────────────────────

class TestClientValidation:
    def test_balance_empty_wallet_raises(self, client):
        with pytest.raises(ValidationError):
            asyncio.run(client.balance(""))

    def test_miner_empty_id_raises(self, client):
        with pytest.raises(ValidationError):
            asyncio.run(client.miner(""))

    def test_attestation_empty_miner_raises(self, client):
        with pytest.raises(ValidationError):
            asyncio.run(client.attestation_status(""))

class TestClientHealth:
    @pytest.mark.asyncio
    async def test_health_returns_dict(self):
        with patch.object(RustChainClient, '_get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"status": "ok", "uptime": 3600, "version": "1.0"}
            async with RustChainClient() as c:
                result = await c.health()
            assert result["status"] == "ok"
            mock_get.assert_called_once_with("/health")

    @pytest.mark.asyncio
    async def test_info(self):
        with patch.object(RustChainClient, '_get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"node_id": "test-node", "version": "1.0"}
            async with RustChainClient() as c:
                result = await c.info()
            assert "node_id" in result

class TestClientEpoch:
    @pytest.mark.asyncio
    async def test_epoch(self):
        with patch.object(RustChainClient, '_get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {
                "epoch_number": 42,
                "start_block": 1000,
                "end_block": 2000,
                "total_rewards": 1500.0,
                "miners_count": 128
            }
            async with RustChainClient() as c:
                result = await c.epoch()
            assert result["epoch_number"] == 42

    @pytest.mark.asyncio
    async def test_epoch_history(self):
        with patch.object(RustChainClient, '_get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"epochs": [{"epoch_number": 1}, {"epoch_number": 2}]}
            async with RustChainClient() as c:
                result = await c.epoch_history(limit=10)
            assert len(result) == 2

class TestClientMiners:
    @pytest.mark.asyncio
    async def test_miners_list(self):
        with patch.object(RustChainClient, '_get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {
                "miners": [
                    {"miner_id": "m1", "architecture": "POWER8", "hashrate": 10.0, "attestation_score": 0.9, "last_seen": "2026-03-24T00:00:00Z"}
                ]
            }
            async with RustChainClient() as c:
                result = await c.miners(limit=50)
            assert len(result) == 1
            assert result[0]["architecture"] == "POWER8"

    @pytest.mark.asyncio
    async def test_miner_by_arch(self):
        with patch.object(RustChainClient, '_get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"miners": []}
            async with RustChainClient() as c:
                await c.miner_by_arch("G5")
            mock_get.assert_called_once()

class TestClientWallet:
    @pytest.mark.asyncio
    async def test_balance(self):
        with patch.object(RustChainClient, '_get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"wallet_id": "w1", "balance": 1000.0, "locked": 0.0, "pending": 0.0}
            async with RustChainClient() as c:
                result = await c.balance("w1")
            assert result["balance"] == 1000.0

    @pytest.mark.asyncio
    async def test_wallet_history(self):
        with patch.object(RustChainClient, '_get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"transactions": []}
            async with RustChainClient() as c:
                result = await c.wallet_history("w1", limit=20)
            assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_transfer_unsigned(self):
        with patch.object(RustChainClient, '_get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {
                "from": "w1", "to": "w2", "amount": 100.0,
                "sign_data": "data-to-sign"
            }
            async with RustChainClient() as c:
                result = await c.transfer_unsigned("w1", "w2", 100.0)
            assert result["amount"] == 100.0

    @pytest.mark.asyncio
    async def test_transfer_signed(self):
        with patch.object(RustChainClient, '_post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {"tx_hash": "0xnewtx", "status": "confirmed"}
            async with RustChainClient() as c:
                result = await c.transfer("w1", "w2", 100.0, "signature")
            assert result["tx_hash"] == "0xnewtx"

class TestClientExplorer:
    @pytest.mark.asyncio
    async def test_explorer_blocks(self):
        with patch.object(RustChainClient, '_get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {
                "blocks": [
                    {"block_number": 100, "hash": "0xh", "timestamp": "2026-03-24T00:00:00Z",
                     "miner": "m1", "tx_count": 3, "attestations": 10}
                ]
            }
            async with RustChainClient() as c:
                result = await c.explorer_blocks(limit=20)
            assert len(result) == 1
            assert result[0]["block_number"] == 100

    @pytest.mark.asyncio
    async def test_explorer_transactions(self):
        with patch.object(RustChainClient, '_get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"transactions": []}
            async with RustChainClient() as c:
                result = await c.explorer_transactions(limit=50)
            assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_explorer_tx(self):
        with patch.object(RustChainClient, '_get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"tx_hash": "0xtx", "status": "confirmed"}
            async with RustChainClient() as c:
                result = await c.explorer_tx("0xtx")
            assert result["tx_hash"] == "0xtx"

class TestClientAttestation:
    @pytest.mark.asyncio
    async def test_attestation_status(self):
        with patch.object(RustChainClient, '_get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {
                "miner_id": "m1", "score": 0.92, "status": "verified",
                "fingerprint": "fp1", "last_attestation": "2026-03-24T00:00:00Z"
            }
            async with RustChainClient() as c:
                result = await c.attestation_status("m1")
            assert result["score"] == 0.92

    @pytest.mark.asyncio
    async def test_attestation_submit(self):
        with patch.object(RustChainClient, '_post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {"miner_id": "m1", "status": "verified", "score": 0.95}
            async with RustChainClient() as c:
                result = await c.attestation_submit("m1", "fingerprint-data")
            assert result["status"] == "verified"

class TestAPIError:
    @pytest.mark.asyncio
    async def test_http_error_raises_api_error(self):
        with patch.object(RustChainClient, '_get', new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = APIError("Not found", status_code=404, path="/unknown")
            async with RustChainClient() as c:
                with pytest.raises(APIError) as exc_info:
                    await c.health()
                assert exc_info.value.status_code == 404

class TestSignData:
    def test_sign_data_returns_hex(self, client):
        sig = client.sign_data("test-wallet", b"hello world")
        assert isinstance(sig, str)
        assert len(sig) == 192  # NIST384p signature is 96 bytes = 192 hex chars

# ─── Run ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
