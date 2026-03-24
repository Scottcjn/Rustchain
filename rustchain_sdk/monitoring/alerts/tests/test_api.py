"""Tests for RustChain API client (uses live API where available, mocks otherwise)."""

from __future__ import annotations

import pytest
import respx
import httpx

from rustchain_alerts.api import RustChainClient, MinerInfo, WalletBalance, EpochInfo, HealthInfo


BASE = "https://test.rustchain.local"


@pytest.mark.anyio
async def test_health_parses_response():
    with respx.mock(base_url=BASE) as mock:
        mock.get("/health").mock(return_value=httpx.Response(200, json={
            "ok": True, "version": "2.2.1", "uptime_s": 100.0,
            "tip_age_slots": 0, "db_rw": True, "backup_age_hours": 1.0
        }))
        async with RustChainClient(BASE, verify_ssl=False) as client:
            h = await client.health()
            assert h.ok is True
            assert h.version == "2.2.1"


@pytest.mark.anyio
async def test_epoch_parses_response():
    with respx.mock(base_url=BASE) as mock:
        mock.get("/epoch").mock(return_value=httpx.Response(200, json={
            "epoch": 103, "slot": 14860, "blocks_per_epoch": 144,
            "enrolled_miners": 28, "epoch_pot": 1.5, "total_supply_rtc": 8388608
        }))
        async with RustChainClient(BASE, verify_ssl=False) as client:
            e = await client.epoch()
            assert e.epoch == 103
            assert e.enrolled_miners == 28


@pytest.mark.anyio
async def test_get_miners_returns_list():
    with respx.mock(base_url=BASE) as mock:
        mock.get("/api/miners").mock(return_value=httpx.Response(200, json=[
            {"miner": "miner-abc", "last_attest": 1000, "entropy_score": 0.5,
             "device_arch": "x86", "device_family": "x86_64", "hardware_type": "x86-64",
             "antiquity_multiplier": 1.0, "first_attest": None},
        ]))
        async with RustChainClient(BASE, verify_ssl=False) as client:
            miners = await client.get_miners()
            assert len(miners) == 1
            assert miners[0].miner == "miner-abc"


@pytest.mark.anyio
async def test_wallet_balance_parses():
    with respx.mock(base_url=BASE) as mock:
        mock.get("/wallet/balance").mock(return_value=httpx.Response(200, json={
            "miner_id": "miner-abc", "amount_rtc": 5.0, "amount_i64": 5000000
        }))
        async with RustChainClient(BASE, verify_ssl=False) as client:
            bal = await client.wallet_balance("miner-abc")
            assert bal.amount_rtc == 5.0
            assert bal.miner_id == "miner-abc"


@pytest.mark.anyio
async def test_http_error_propagates():
    with respx.mock(base_url=BASE) as mock:
        mock.get("/health").mock(return_value=httpx.Response(500))
        async with RustChainClient(BASE, verify_ssl=False) as client:
            with pytest.raises(httpx.HTTPStatusError):
                await client.health()
