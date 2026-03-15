"""
RustChain MCP Server
Exposes RustChain node API as Model Context Protocol tools
for use with Claude Code and other MCP-compatible clients.
"""

import json
import logging
from typing import Any

import requests
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

BASE_URL = "https://rustchain.org"
REQUEST_TIMEOUT = 15

mcp = FastMCP("rustchain")


def _get(path: str, params: dict | None = None) -> dict[str, Any]:
    """Make a GET request to the RustChain node."""
    url = f"{BASE_URL}{path}"
    resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT, verify=True)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def get_health() -> str:
    """Check RustChain node health status.

    Returns node version, uptime, database read/write status,
    backup age, and tip age.
    """
    data = _get("/health")
    return json.dumps(data, indent=2)


@mcp.tool()
def get_epoch() -> str:
    """Get current RustChain epoch information.

    Returns current epoch number, slot, enrolled miners,
    epoch reward pot, blocks per epoch, and total supply.
    """
    data = _get("/epoch")
    return json.dumps(data, indent=2)


@mcp.tool()
def get_balance(miner_id: str) -> str:
    """Get wallet balance for a miner.

    Args:
        miner_id: The miner's wallet identifier (e.g. "Ivan-houzhiwen").

    Returns balance in RTC and micro-units.
    """
    data = _get("/wallet/balance", params={"miner_id": miner_id})
    return json.dumps(data, indent=2)


@mcp.tool()
def get_miners() -> str:
    """List all active miners on the RustChain network.

    Returns miner IDs, hardware types, device architectures,
    antiquity multipliers, and attestation timestamps.
    """
    data = _get("/api/miners")
    return json.dumps(data, indent=2)


@mcp.tool()
def get_chain_tip() -> str:
    """Get the current chain tip.

    Returns the latest slot number, the miner who produced it,
    tip age in seconds, and signature prefix.
    """
    data = _get("/headers/tip")
    return json.dumps(data, indent=2)


@mcp.tool()
def get_block(height: int) -> str:
    """Get a block at a specific height.

    Args:
        height: Block height to retrieve.

    Returns block data from the P2P sync endpoint.
    """
    data = _get("/p2p/blocks", params={"start": height, "limit": 1})
    return json.dumps(data, indent=2)


if __name__ == "__main__":
    mcp.run()
