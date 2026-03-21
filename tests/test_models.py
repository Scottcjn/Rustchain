"""Unit tests for RustChain Pydantic models."""

import pytest
from datetime import datetime
from rustchain.models import (
    HealthResponse,
    EpochInfo,
    Miner,
    BalanceResponse,
    TransferResponse,
    AttestationStatus,
    Block,
    Transaction,
    BlockListResponse,
    TransactionListResponse,
)


class TestHealthResponse:
    def test_from_dict(self):
        h = HealthResponse(status="ok", version="2.0.0")
        assert h.status == "ok"
        assert h.version == "2.0.0"

    def test_optional_fields(self):
        h = HealthResponse(status="ok")
        assert h.version is None


class TestEpochInfo:
    def test_required_fields(self):
        e = EpochInfo(epoch=10, start_block=0, end_block=999)
        assert e.epoch == 10
        assert e.end_block == 999


class TestMiner:
    def test_miner_fields(self):
        m = Miner(
            miner_id="m1",
            wallet_id="wallet1",
            status="active",
            power=500,
            rewards=12.5,
        )
        assert m.status == "active"
        assert m.power == 500


class TestBalanceResponse:
    def test_default_locked(self):
        b = BalanceResponse(wallet_id="w1", balance=100.0)
        assert b.locked == 0.0

    def test_all_fields(self):
        b = BalanceResponse(wallet_id="w1", balance=100.0, locked=25.0)
        assert b.locked == 25.0


class TestTransferResponse:
    def test_required_fields(self):
        t = TransferResponse(
            tx_hash="tx1",
            from_wallet="w1",
            to_wallet="w2",
            amount=10.0,
            fee=0.001,
            status="pending",
        )
        assert t.status == "pending"
        assert t.block is None


class TestAttestationStatus:
    def test_defaults(self):
        a = AttestationStatus(miner_id="m1", attested=True)
        assert a.attestations_count == 0
        assert a.score == 0.0

    def test_full_attestation(self):
        a = AttestationStatus(
            miner_id="m1",
            attested=True,
            attestations_count=500,
            score=99.9,
        )
        assert a.attested is True
        assert a.score == 99.9


class TestBlock:
    def test_block_fields(self):
        b = Block(hash="abc", height=100, tx_count=5)
        assert b.height == 100
        assert b.tx_count == 5

    def test_block_optional_parent(self):
        b = Block(hash="abc", height=1)
        assert b.parent_hash is None


class TestTransaction:
    def test_transaction_defaults(self):
        t = Transaction(
            tx_hash="tx1",
            from_wallet="w1",
            to_wallet="w2",
            amount=1.0,
            fee=0.001,
            status="confirmed",
        )
        assert t.type == "transfer"
        assert t.block is None


class TestBlockListResponse:
    def test_pagination(self):
        r = BlockListResponse(blocks=[], total=100, page=2, per_page=20)
        assert r.page == 2
        assert r.per_page == 20
        assert r.total == 100

    def test_blocks_list(self):
        blocks = [
            Block(hash="b1", height=1),
            Block(hash="b2", height=2),
        ]
        r = BlockListResponse(blocks=blocks, total=2, page=1, per_page=20)
        assert len(r.blocks) == 2


class TestTransactionListResponse:
    def test_pagination(self):
        r = TransactionListResponse(
            transactions=[],
            total=50,
            page=1,
            per_page=10,
        )
        assert r.total == 50
        assert r.per_page == 10
