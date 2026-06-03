"""Tests for RustChain bounties MCP miner client normalization."""

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rustchain_bounties_mcp.client import RustChainClient


class AsyncContextManager:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, *args):
        return None


class MockResponse:
    def __init__(self, data, status=200):
        self._data = data
        self.status = status

    async def json(self):
        return self._data


def client_for_response(data) -> RustChainClient:
    response = MockResponse(data)
    session = MagicMock()
    session.request = MagicMock(return_value=AsyncContextManager(response))

    client = RustChainClient(node_url="https://node.example")
    client._session = session
    client._owns_session = False
    return client


@pytest.mark.asyncio
async def test_miners_accepts_raw_array_payload():
    client = client_for_response([
        {
            "miner_id": "alice",
            "hardware": "PowerPC G4",
            "device_family": "PowerPC",
            "device_arch": "g4",
            "entropy_score": 0.9,
        }
    ])

    result = await client.miners()

    assert result["total_count"] == 1
    assert result["miners"][0].miner == "alice"
    assert result["miners"][0].hardware_type == "PowerPC G4"


@pytest.mark.asyncio
async def test_miners_accepts_data_envelope_and_filters_aliases():
    client = client_for_response({
        "data": [
            {
                "name": "gpu-miner",
                "hardware": "GPU Rig",
                "device_family": "GPU",
            },
            {
                "miner": "cpu-miner",
                "hardware_type": "CPU",
                "device_family": "x86",
            },
            "not-a-row",
        ],
        "pagination": {"total": 3, "offset": 5},
    })

    result = await client.miners(limit=10, hardware_type="gpu")

    assert result["total_count"] == 3
    assert result["offset"] == 5
    assert [miner.miner for miner in result["miners"]] == ["gpu-miner"]
    assert result["miners"][0].hardware_type == "GPU Rig"
