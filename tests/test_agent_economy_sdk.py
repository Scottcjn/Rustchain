import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agent_economy_sdk


class StubAgentEconomyClient:
    stats_by_node = {}

    def __init__(self, node):
        self.node = node

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False

    async def get_marketplace_stats(self):
        result = self.stats_by_node[self.node]
        if isinstance(result, Exception):
            raise result
        return result


def test_get_network_stats_aggregates_partial_node_stats(monkeypatch):
    StubAgentEconomyClient.stats_by_node = {
        "https://node-a.example": {"total_jobs": 3},
        "https://node-b.example": {"total_agents": 2, "total_volume": 4.5},
    }
    monkeypatch.setattr(agent_economy_sdk, "AgentEconomyClient", StubAgentEconomyClient)
    sdk = agent_economy_sdk.AgentEconomySDK(
        ["https://node-a.example", "https://node-b.example"]
    )

    stats = asyncio.run(sdk.get_network_stats())

    assert stats["nodes"] == [
        {"url": "https://node-a.example", "stats": {"total_jobs": 3}},
        {
            "url": "https://node-b.example",
            "stats": {"total_agents": 2, "total_volume": 4.5},
        },
    ]
    assert stats["aggregate"] == {
        "total_jobs": 3,
        "total_agents": 2,
        "total_volume": 4.5,
    }


def test_get_network_stats_records_node_errors_without_stopping(monkeypatch):
    StubAgentEconomyClient.stats_by_node = {
        "https://node-a.example": {"total_jobs": 1, "total_agents": 1, "total_volume": 2.0},
        "https://node-b.example": RuntimeError("node offline"),
        "https://node-c.example": {"total_jobs": 2, "total_agents": 3, "total_volume": 5.0},
    }
    monkeypatch.setattr(agent_economy_sdk, "AgentEconomyClient", StubAgentEconomyClient)
    sdk = agent_economy_sdk.AgentEconomySDK(
        ["https://node-a.example", "https://node-b.example", "https://node-c.example"]
    )

    stats = asyncio.run(sdk.get_network_stats())

    assert stats["nodes"][0] == {
        "url": "https://node-a.example",
        "stats": {"total_jobs": 1, "total_agents": 1, "total_volume": 2.0},
    }
    assert stats["nodes"][1] == {
        "url": "https://node-b.example",
        "error": "node offline",
    }
    assert stats["nodes"][2] == {
        "url": "https://node-c.example",
        "stats": {"total_jobs": 2, "total_agents": 3, "total_volume": 5.0},
    }
    assert stats["aggregate"] == {
        "total_jobs": 3,
        "total_agents": 4,
        "total_volume": 7.0,
    }
