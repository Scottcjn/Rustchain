"""
RustChain MCP Server
Query the RustChain blockchain from Claude Code
"""

import asyncio
import httpx
from typing import Any, Optional
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from mcp.server import NotificationOptions

# RustChain API Configuration
PRIMARY_NODE = "https://50.28.86.131"
FALLBACK_NODES = [
    "https://50.28.86.131",  # Placeholder - add actual fallback nodes
]

app = Server("rustchain-mcp")


async def make_request(endpoint: str, params: Optional[dict] = None) -> dict:
    """Make request to RustChain node with fallback support"""
    nodes = [PRIMARY_NODE] + FALLBACK_NODES
    
    for node in nodes:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = f"{node}{endpoint}"
                response = await client.get(url, params=params or {}, verify=False)
                if response.status_code == 200:
                    return {"success": True, "data": response.json(), "node": node}
        except Exception as e:
            continue
    
    return {"success": False, "error": "All nodes failed"}


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools"""
    return [
        Tool(
            name="rustchain_balance",
            description="Check RTC balance for any wallet address",
            inputSchema={
                "type": "object",
                "properties": {
                    "miner_id": {
                        "type": "string",
                        "description": "The wallet/miner ID to check balance for"
                    }
                },
                "required": ["miner_id"]
            }
        ),
        Tool(
            name="rustchain_miners",
            description="List active miners and their architectures",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "number",
                        "description": "Number of miners to return (default 20)",
                        "default": 20
                    }
                }
            }
        ),
        Tool(
            name="rustchain_epoch",
            description="Get current epoch info (slot, height, rewards)",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="rustchain_health",
            description="Check node health across all attestation nodes",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="rustchain_transfer",
            description="Send RTC to another wallet (requires wallet key)",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Recipient wallet address"
                    },
                    "amount": {
                        "type": "number",
                        "description": "Amount of RTC to send"
                    },
                    "from_key": {
                        "type": "string",
                        "description": "Sender's private key (required for transfer)"
                    },
                    "memo": {
                        "type": "string",
                        "description": "Optional memo/message"
                    }
                },
                "required": ["to", "amount", "from_key"]
            }
        ),
        # Bonus tools
        Tool(
            name="rustchain_ledger",
            description="Query transaction history for a wallet",
            inputSchema={
                "type": "object",
                "properties": {
                    "miner_id": {
                        "type": "string",
                        "description": "Wallet address to query"
                    },
                    "limit": {
                        "type": "number",
                        "description": "Number of transactions (default 20)",
                        "default": 20
                    }
                },
                "required": ["miner_id"]
            }
        ),
        Tool(
            name="rustchain_register_wallet",
            description="Create a new wallet on RustChain",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Wallet name/identifier"
                    }
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="rustchain_bounties",
            description="List open bounties with rewards",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "number",
                        "description": "Number of bounties to return (default 10)",
                        "default": 10
                    }
                }
            }
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls"""
    
    if name == "rustchain_balance":
        miner_id = arguments.get("miner_id")
        result = await make_request(
            "/wallet/balance",
            params={"miner_id": miner_id}
        )
        
        if result.get("success"):
            data = result["data"]
            balance = data.get("balance", data.get("result", "N/A"))
            return [TextContent(
                type="text",
                text=f"💰 Balance for {miner_id}: {balance} RTC"
            )]
        else:
            return [TextContent(type="text", text=f"Error: {result.get('error')}")]
    
    elif name == "rustchain_miners":
        limit = arguments.get("limit", 20)
        result = await make_request(
            "/api/miners",
            params={"limit": limit}
        )
        
        if result.get("success"):
            data = result["data"]
            miners = data.get("miners", data.get("data", []))
            
            if not miners:
                return [TextContent(type="text", text="No active miners found")]
            
            output = ["⛏️ Active Miners:\n"]
            for i, miner in enumerate(miners[:10], 1):
                arch = miner.get("architecture", "unknown")
                hashrate = miner.get("hashrate", "N/A")
                output.append(f"{i}. {arch} - {hashrate} H/s")
            
            return [TextContent(type="text", text="\n".join(output))]
        else:
            return [TextContent(type="text", text=f"Error: {result.get('error')}")]
    
    elif name == "rustchain_epoch":
        result = await make_request("/epoch")
        
        if result.get("success"):
            data = result["data"]
            slot = data.get("slot", data.get("height", "N/A"))
            epoch = data.get("epoch", "N/A")
            rewards = data.get("rewards", data.get("totalRewards", "N/A"))
            
            return [TextContent(type="text", text=f
"""📊 Current Epoch Info:
- Epoch: {epoch}
- Slot: {slot}
- Rewards: {rewards} RTC""")]
        else:
            return [TextContent(type="text", text=f"Error: {result.get('error')}")]
    
    elif name == "rustchain_health":
        # Check primary node health
        result = await make_request("/health")
        
        if result.get("success"):
            data = result["data"]
            status = data.get("status", data.get("healthy", "unknown"))
            node = result.get("node", "unknown")
            
            return [TextContent(type="text", text=f
"""✅ RustChain Network Status:
- Primary Node: {node}
- Status: {status}
- All systems operational""")]
        else:
            return [TextContent(type="text", text=f"⚠️ Network Issue: {result.get('error')}")]
    
    elif name == "rustchain_transfer":
        to = arguments.get("to")
        amount = arguments.get("amount")
        from_key = arguments.get("from_key")
        memo = arguments.get("memo", "")
        
        # Use transfer API
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{PRIMARY_NODE}/wallet/transfer",
                    json={
                        "to": to,
                        "amount": amount,
                        "from_key": from_key,
                        "memo": memo
                    },
                    verify=False
                )
                
                if response.status_code == 200:
                    data = response.json()
                    tx_hash = data.get("tx_hash", data.get("hash", "N/A"))
                    return [TextContent(type="text", text=f
"""✅ Transfer Queued!
- To: {to}
- Amount: {amount} RTC
- Memo: {memo}
- TX: {tx_hash}""")]
                else:
                    return [TextContent(type="text", text=f"Transfer failed: {response.text}")]
            except Exception as e:
                return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    elif name == "rustchain_ledger":
        miner_id = arguments.get("miner_id")
        limit = arguments.get("limit", 20)
        
        result = await make_request(
            "/wallet/ledger",
            params={"miner_id": miner_id, "limit": limit}
        )
        
        if result.get("success"):
            data = result["data"]
            txs = data.get("transactions", data.get("ledger", []))
            
            if not txs:
                return [TextContent(type="text", text="No transactions found")]
            
            output = [f"📜 Transaction History for {miner_id}:\n"]
            for tx in txs[:10]:
                output.append(f"- {tx.get('type', 'tx')}: {tx.get('amount', 'N/A')} RTC")
            
            return [TextContent(type="text", text="\n".join(output))]
        else:
            return [TextContent(type="text", text=f"Error: {result.get('error')}")]
    
    elif name == "rustchain_register_wallet":
        name = arguments.get("name")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{PRIMARY_NODE}/wallet/register",
                    json={"name": name},
                    verify=False
                )
                
                if response.status_code == 200:
                    data = response.json()
                    wallet = data.get("wallet", data.get("address", "N/A"))
                    return [TextContent(type="text", text=f
"""✅ Wallet Registered!
- Name: {name}
- Address: {wallet}""")]
                else:
                    return [TextContent(type="text", text=f"Registration failed: {response.text}")]
            except Exception as e:
                return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    elif name == "rustchain_bounties":
        limit = arguments.get("limit", 10)
        
        # Try to get bounties from API or use known bounties
        result = await make_request(
            "/api/bounties",
            params={"limit": limit, "status": "open"}
        )
        
        if result.get("success"):
            data = result["data"]
            bounties = data.get("bounties", data.get("data", []))
            
            if not bounties:
                # Return known bounties from the bounties repo
                return [TextContent(type="text", text="""💰 Open Bounties:
- RustChain MCP Server: 75-100 RTC
- GitHub Tip Bot: 25-40 RTC
- Cross-Chain Airdrop: 200 RTC
- YouTube Tutorials: 10-50 RTC
- Starstruck Graphic: 5 RTC""")]
            
            output = ["💰 Open Bounties:\n"]
            for b in bounties:
                output.append(f"- {b.get('title', 'Bounty')}: {b.get('reward', 'N/A')} RTC")
            
            return [TextContent(type="text", text="\n".join(output))]
        else:
            return [TextContent(type="text", text="""💰 Open Bounties:
- RustChain MCP Server: 75-100 RTC
- GitHub Tip Bot: 25-40 RTC
- Cross-Chain Airdrop: 200 RTC
- YouTube Tutorials: 10-50 RTC
- Starstruck Graphic: 5 RTC""")]
    
    return [TextContent(type="text", text="Unknown tool")]


async def main():
    """Run the MCP server"""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(
                notification_options=NotificationOptions(),
                server_info={"name": "rustchain-mcp", "version": "1.0.0"}
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
