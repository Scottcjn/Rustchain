#!/usr/bin/env python3
"""
RustChain MCP Server
Query the RustChain blockchain from Claude Code
"""

import os
import json
import requests
from typing import Any, Optional
from datetime import datetime

# MCP Server imports
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server

# Node endpoints
NODES = [
    "https://50.28.86.131",  # Primary
    "https://50.28.86.153",  # Node Beta
    "https://50.28.86.154",  # Node Gamma
]


def get_node_url() -> str:
    """Get the first available node URL"""
    return NODES[0]


def make_request(endpoint: str, params: Optional[dict] = None) -> dict:
    """Make a request to the RustChain node with fallback"""
    for node in NODES:
        try:
            url = f"{node}{endpoint}"
            response = requests.get(url, params=params, timeout=10, verify=False)
            if response.status_code == 200:
                return response.json()
        except Exception:
            continue
    return {"error": "All nodes unavailable"}


# Initialize MCP Server
app = Server("rustchain-mcp-server")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools"""
    return [
        Tool(
            name="rustchain_health",
            description="Check the health status of all RustChain attestation nodes",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="rustchain_miners",
            description="List all active miners on the RustChain network with their architectures",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of miners to return",
                        "default": 50
                    }
                }
            }
        ),
        Tool(
            name="rustchain_epoch",
            description="Get current epoch information including slot, height, and rewards",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="rustchain_balance",
            description="Check RTC token balance for any wallet address",
            inputSchema={
                "type": "object",
                "properties": {
                    "miner_id": {
                        "type": "string",
                        "description": "Wallet address or miner ID to check balance for"
                    }
                },
                "required": ["miner_id"]
            }
        ),
        Tool(
            name="rustchain_transfer",
            description="Transfer RTC tokens to another wallet address",
            inputSchema={
                "type": "object",
                "properties": {
                    "to_address": {
                        "type": "string",
                        "description": "Recipient wallet address"
                    },
                    "amount": {
                        "type": "number",
                        "description": "Amount of RTC to transfer"
                    },
                    "from_key": {
                        "type": "string",
                        "description": "Sender's private key or wallet key"
                    }
                },
                "required": ["to_address", "amount", "from_key"]
            }
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls"""
    
    if name == "rustchain_health":
        result = check_health()
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    elif name == "rustchain_miners":
        limit = arguments.get("limit", 50)
        result = get_miners(limit)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    elif name == "rustchain_epoch":
        result = get_epoch()
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    elif name == "rustchain_balance":
        miner_id = arguments.get("miner_id")
        if not miner_id:
            return [TextContent(type="text", text="Error: miner_id is required")]
        result = get_balance(miner_id)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    elif name == "rustchain_transfer":
        to_address = arguments.get("to_address")
        amount = arguments.get("amount")
        from_key = arguments.get("from_key")
        
        if not all([to_address, amount, from_key]):
            return [TextContent(type="text", text="Error: to_address, amount, and from_key are all required")]
        
        result = transfer_rtc(to_address, amount, from_key)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    return [TextContent(type="text", text=f"Unknown tool: {name}")]


def check_health() -> dict:
    """Check health of all nodes"""
    health_status = {}
    
    for i, node in enumerate(NODES):
        try:
            response = requests.get(f"{node}/health", timeout=5, verify=False)
            health_status[f"node_{i+1}"] = {
                "url": node,
                "status": "online" if response.status_code == 200 else "error",
                "status_code": response.status_code,
                "response": response.json() if response.status_code == 200 else response.text[:200]
            }
        except Exception as e:
            health_status[f"node_{i+1}"] = {
                "url": node,
                "status": "unreachable",
                "error": str(e)
            }
    
    return health_status


def get_miners(limit: int = 50) -> dict:
    """Get list of active miners"""
    data = make_request("/api/miners", {"limit": limit})
    return data


def get_epoch() -> dict:
    """Get current epoch information"""
    data = make_request("/epoch")
    return data


def get_balance(miner_id: str) -> dict:
    """Get balance for a wallet"""
    data = make_request("/wallet/balance", {"miner_id": miner_id})
    return data


def transfer_rtc(to_address: str, amount: float, from_key: str) -> dict:
    """Transfer RTC tokens"""
    try:
        response = requests.post(
            f"{get_node_url()}/wallet/transfer",
            json={
                "to": to_address,
                "amount": amount,
                "from_key": from_key
            },
            timeout=30,
            verify=False
        )
        return response.json() if response.status_code == 200 else {
            "error": f"HTTP {response.status_code}",
            "message": response.text
        }
    except Exception as e:
        return {"error": str(e)}


async def main():
    """Main entry point"""
    async with stdio_server() as server:
        server.run()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
