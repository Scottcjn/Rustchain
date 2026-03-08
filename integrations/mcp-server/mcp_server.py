#!/usr/bin/env python3
"""
RustChain MCP Server

Model Context Protocol (MCP) server that exposes RustChain blockchain data,
miner tools, and agent economy capabilities to AI assistants.

Usage:
    python mcp_server.py
    
Or via npx (for MCP clients):
    npx -y @modelcontextprotocol/server-python rustchain-mcp-server
"""

import asyncio
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
import logging

# MCP SDK
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import (
        Tool,
        Resource,
        ResourceTemplate,
        Prompt,
        TextContent,
        ImageContent,
        EmbeddedResource,
    )
except ImportError:
    print("Error: MCP SDK not installed. Run: pip install mcp", file=sys.stderr)
    sys.exit(1)

# HTTP client for API calls
try:
    import aiohttp
except ImportError:
    print("Error: aiohttp not installed. Run: pip install aiohttp", file=sys.stderr)
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger('rustchain-mcp')

# Configuration
RUSTCHAIN_API_BASE = os.getenv('RUSTCHAIN_API_BASE', 'https://50.28.86.131')
RUSTCHAIN_NODE_URL = os.getenv('RUSTCHAIN_NODE_URL', 'https://50.28.86.131:5000')
BEACON_URL = os.getenv('BEACON_URL', 'https://50.28.86.131:5001')


@dataclass
class MinerInfo:
    miner_id: str
    wallet: str
    hardware: str
    score: float
    epochs_mined: int
    last_seen: int
    status: str


@dataclass
class BlockInfo:
    epoch: int
    hash: str
    timestamp: int
    miner: str
    transactions: int
    reward: float


@dataclass
class EpochInfo:
    epoch: int
    start_time: int
    end_time: int
    active_miners: int
    total_rewards: float
    status: str


class RustChainMCP:
    """RustChain MCP Server implementation."""
    
    def __init__(self):
        self.app = Server("rustchain-mcp")
        self.session: Optional[aiohttp.ClientSession] = None
        self._setup_handlers()
    
    async def start(self):
        """Initialize HTTP session."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={"User-Agent": "RustChain-MCP-Server/1.0"}
        )
        logger.info("RustChain MCP Server started")
    
    async def stop(self):
        """Cleanup resources."""
        if self.session:
            await self.session.close()
        logger.info("RustChain MCP Server stopped")
    
    def _setup_handlers(self):
        """Setup MCP request handlers."""
        
        # List available tools
        @self.app.list_tools()
        async def list_tools() -> List[Tool]:
            return [
                Tool(
                    name="get_miner_info",
                    description="Get information about a RustChain miner by ID or wallet address",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "miner_id": {
                                "type": "string",
                                "description": "Miner ID or wallet address"
                            }
                        },
                        "required": ["miner_id"]
                    }
                ),
                Tool(
                    name="get_block_info",
                    description="Get block information by epoch number or block hash",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "block_id": {
                                "type": "string",
                                "description": "Epoch number or block hash"
                            }
                        },
                        "required": ["block_id"]
                    }
                ),
                Tool(
                    name="get_epoch_info",
                    description="Get current or specific epoch information",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "epoch": {
                                "type": "integer",
                                "description": "Epoch number (optional, defaults to current)"
                            }
                        }
                    }
                ),
                Tool(
                    name="get_network_stats",
                    description="Get current RustChain network statistics",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="get_active_miners",
                    description="Get list of currently active miners with optional filters",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of miners to return (default: 50)"
                            },
                            "hardware_type": {
                                "type": "string",
                                "description": "Filter by hardware type (e.g., 'PowerPC G4', 'x86')"
                            },
                            "min_score": {
                                "type": "number",
                                "description": "Minimum score threshold"
                            }
                        }
                    }
                ),
                Tool(
                    name="get_wallet_balance",
                    description="Get RTC balance and transaction history for a wallet",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "wallet": {
                                "type": "string",
                                "description": "Wallet address or beacon ID"
                            }
                        },
                        "required": ["wallet"]
                    }
                ),
                Tool(
                    name="get_bounty_info",
                    description="Get information about open bounties",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "issue_number": {
                                "type": "integer",
                                "description": "GitHub issue number (optional)"
                            },
                            "min_reward": {
                                "type": "integer",
                                "description": "Minimum reward in RTC"
                            }
                        }
                    }
                ),
                Tool(
                    name="get_agent_info",
                    description="Get information about a RustChain AI agent",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "agent_id": {
                                "type": "string",
                                "description": "Agent ID (beacon ID)"
                            }
                        },
                        "required": ["agent_id"]
                    }
                ),
                Tool(
                    name="verify_hardware",
                    description="Verify if hardware configuration is eligible for RustChain mining",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "cpu_model": {
                                "type": "string",
                                "description": "CPU model name"
                            },
                            "architecture": {
                                "type": "string",
                                "description": "CPU architecture (e.g., 'PowerPC', 'x86_64', 'arm64')"
                            },
                            "is_vm": {
                                "type": "boolean",
                                "description": "Whether running in a VM"
                            }
                        },
                        "required": ["cpu_model", "architecture"]
                    }
                ),
                Tool(
                    name="calculate_mining_rewards",
                    description="Calculate estimated mining rewards based on hardware and uptime",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "hardware_type": {
                                "type": "string",
                                "description": "Hardware type (e.g., 'PowerPC G4', 'Modern x86')"
                            },
                            "epochs": {
                                "type": "integer",
                                "description": "Number of epochs mined"
                            },
                            "uptime_percent": {
                                "type": "number",
                                "description": "Uptime percentage (0-100)"
                            }
                        },
                        "required": ["hardware_type", "epochs"]
                    }
                )
            ]
        
        # List available resources
        @self.app.list_resources()
        async def list_resources() -> List[Resource]:
            return [
                Resource(
                    uri="rustchain://network/stats",
                    name="RustChain Network Statistics",
                    description="Real-time network statistics including active miners, epoch info, and total rewards",
                    mimeType="application/json"
                ),
                Resource(
                    uri="rustchain://miners/active",
                    name="Active Miners List",
                    description="List of currently active miners with their scores and hardware",
                    mimeType="application/json"
                ),
                Resource(
                    uri="rustchain://epochs/current",
                    name="Current Epoch",
                    description="Information about the current epoch",
                    mimeType="application/json"
                ),
                Resource(
                    uri="rustchain://bounties/open",
                    name="Open Bounties",
                    description="List of open bounties with rewards",
                    mimeType="application/json"
                ),
                Resource(
                    uri="rustchain://docs/quickstart",
                    name="Quickstart Guide",
                    description="How to start mining on RustChain",
                    mimeType="text/markdown"
                )
            ]
        
        # List resource templates
        @self.app.list_resource_templates()
        async def list_resource_templates() -> List[ResourceTemplate]:
            return [
                ResourceTemplate(
                    uriTemplate="rustchain://miner/{miner_id}",
                    name="Miner Information",
                    description="Get detailed information about a specific miner"
                ),
                ResourceTemplate(
                    uriTemplate="rustchain://block/{epoch_or_hash}",
                    name="Block Information",
                    description="Get block information by epoch number or hash"
                ),
                ResourceTemplate(
                    uriTemplate="rustchain://wallet/{address}",
                    name="Wallet Information",
                    description="Get wallet balance and transaction history"
                ),
                ResourceTemplate(
                    uriTemplate="rustchain://epoch/{epoch_number}",
                    name="Epoch Information",
                    description="Get information about a specific epoch"
                ),
                ResourceTemplate(
                    uriTemplate="rustchain://bounty/{issue_number}",
                    name="Bounty Information",
                    description="Get details about a specific bounty"
                )
            ]
        
        # List available prompts
        @self.app.list_prompts()
        async def list_prompts() -> List[Prompt]:
            return [
                Prompt(
                    name="analyze_miner_performance",
                    description="Analyze a miner's performance and provide optimization suggestions",
                    arguments=[
                        {
                            "name": "miner_id",
                            "description": "Miner ID to analyze",
                            "required": True
                        }
                    ]
                ),
                Prompt(
                    name="bounty_recommendations",
                    description="Get personalized bounty recommendations based on skills",
                    arguments=[
                        {
                            "name": "skill_level",
                            "description": "Skill level (beginner, intermediate, advanced)",
                            "required": False
                        },
                        {
                            "name": "interest_area",
                            "description": "Area of interest (blockchain, AI, hardware, web)",
                            "required": False
                        }
                    ]
                ),
                Prompt(
                    name="hardware_compatibility_check",
                    description="Check if vintage hardware is compatible with RustChain mining",
                    arguments=[
                        {
                            "name": "hardware_description",
                            "description": "Description of the hardware (e.g., 'PowerBook G4 1.5GHz')",
                            "required": True
                        }
                    ]
                )
            ]
        
        # Handle tool calls
        @self.app.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            handler = getattr(self, f'_tool_{name}', None)
            if not handler:
                raise ValueError(f"Unknown tool: {name}")
            
            try:
                result = await handler(arguments)
                return [TextContent(type="text", text=json.dumps(result, indent=2))]
            except Exception as e:
                logger.error(f"Tool error {name}: {e}")
                return [TextContent(type="text", text=f"Error: {str(e)}")]
        
        # Handle resource reads
        @self.app.read_resource()
        async def read_resource(uri: str) -> tuple[str, str]:
            try:
                result = await self._read_resource_impl(uri)
                return result
            except Exception as e:
                logger.error(f"Resource error {uri}: {e}")
                raise
    
    async def _read_resource_impl(self, uri: str) -> tuple[str, str]:
        """Read resource implementation."""
        if uri == "rustchain://network/stats":
            data = await self._get_network_stats()
            return json.dumps(data, indent=2), "application/json"
        
        elif uri == "rustchain://miners/active":
            data = await self._get_active_miners_impl(limit=100)
            return json.dumps(data, indent=2), "application/json"
        
        elif uri == "rustchain://epochs/current":
            data = await self._get_epoch_info_impl(None)
            return json.dumps(data, indent=2), "application/json"
        
        elif uri == "rustchain://bounties/open":
            data = await self._get_bounty_info_impl(None, None)
            return json.dumps(data, indent=2), "application/json"
        
        elif uri == "rustchain://docs/quickstart":
            content = self._get_quickstart_guide()
            return content, "text/markdown"
        
        # Handle templates
        elif uri.startswith("rustchain://miner/"):
            miner_id = uri.split("/")[-1]
            data = await self._get_miner_info_impl(miner_id)
            return json.dumps(data, indent=2), "application/json"
        
        elif uri.startswith("rustchain://block/"):
            block_id = uri.split("/")[-1]
            data = await self._get_block_info_impl(block_id)
            return json.dumps(data, indent=2), "application/json"
        
        elif uri.startswith("rustchain://wallet/"):
            address = uri.split("/")[-1]
            data = await self._get_wallet_balance_impl(address)
            return json.dumps(data, indent=2), "application/json"
        
        elif uri.startswith("rustchain://epoch/"):
            epoch_str = uri.split("/")[-1]
            epoch = int(epoch_str) if epoch_str.isdigit() else None
            data = await self._get_epoch_info_impl(epoch)
            return json.dumps(data, indent=2), "application/json"
        
        elif uri.startswith("rustchain://bounty/"):
            issue_str = uri.split("/")[-1]
            issue_number = int(issue_str) if issue_str.isdigit() else None
            data = await self._get_bounty_info_impl(issue_number, None)
            return json.dumps(data, indent=2), "application/json"
        
        raise ValueError(f"Unknown resource: {uri}")
    
    # Tool implementations
    
    async def _tool_get_miner_info(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get miner information."""
        miner_id = args.get("miner_id", "")
        return await self._get_miner_info_impl(miner_id)
    
    async def _get_miner_info_impl(self, miner_id: str) -> Dict[str, Any]:
        """Get miner info implementation."""
        url = f"{RUSTCHAIN_API_BASE}/api/miners"
        
        async with self.session.get(url) as resp:
            if resp.status != 200:
                return {"error": f"API error: {resp.status}", "miner_id": miner_id}
            
            miners = await resp.json()
            
            # Search for matching miner
            for miner in miners.get("miners", []):
                if (miner.get("miner_id") == miner_id or 
                    miner.get("wallet") == miner_id or
                    miner.get("id") == miner_id):
                    return {
                        "found": True,
                        "miner": miner
                    }
            
            return {"found": False, "miner_id": miner_id, "hint": "Miner not found in active list"}
    
    async def _tool_get_block_info(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get block information."""
        block_id = args.get("block_id", "")
        return await self._get_block_info_impl(block_id)
    
    async def _get_block_info_impl(self, block_id: str) -> Dict[str, Any]:
        """Get block info implementation."""
        try:
            # Try as epoch number first
            epoch = int(block_id)
            url = f"{RUSTCHAIN_API_BASE}/api/epochs/{epoch}"
        except ValueError:
            # Treat as hash
            url = f"{RUSTCHAIN_API_BASE}/api/blocks/{block_id}"
        
        async with self.session.get(url) as resp:
            if resp.status == 200:
                block = await resp.json()
                return {"found": True, "block": block}
            elif resp.status == 404:
                return {"found": False, "block_id": block_id, "error": "Block not found"}
            else:
                return {"error": f"API error: {resp.status}"}
    
    async def _tool_get_epoch_info(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get epoch information."""
        epoch = args.get("epoch")
        return await self._get_epoch_info_impl(epoch)
    
    async def _get_epoch_info_impl(self, epoch: Optional[int]) -> Dict[str, Any]:
        """Get epoch info implementation."""
        if epoch is None:
            # Get current epoch from network stats
            stats = await self._get_network_stats()
            epoch = stats.get("current_epoch", 0)
        
        url = f"{RUSTCHAIN_API_BASE}/api/epochs/{epoch}"
        
        async with self.session.get(url) as resp:
            if resp.status == 200:
                epoch_data = await resp.json()
                return {"found": True, "epoch": epoch, "data": epoch_data}
            else:
                return {"error": f"Could not fetch epoch {epoch}: {resp.status}"}
    
    async def _tool_get_network_stats(self, args: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get network statistics."""
        return await self._get_network_stats()
    
    async def _get_network_stats(self) -> Dict[str, Any]:
        """Get network stats implementation."""
        url = f"{RUSTCHAIN_API_BASE}/api/stats"
        
        try:
            async with self.session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    return {"error": f"API error: {resp.status}"}
        except Exception as e:
            return {"error": f"Failed to fetch stats: {str(e)}"}
    
    async def _tool_get_active_miners(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get active miners."""
        limit = args.get("limit", 50)
        hardware_type = args.get("hardware_type")
        min_score = args.get("min_score")
        
        return await self._get_active_miners_impl(limit, hardware_type, min_score)
    
    async def _get_active_miners_impl(self, limit: int = 50, 
                                       hardware_type: Optional[str] = None,
                                       min_score: Optional[float] = None) -> Dict[str, Any]:
        """Get active miners implementation."""
        url = f"{RUSTCHAIN_API_BASE}/api/miners"
        
        async with self.session.get(url) as resp:
            if resp.status != 200:
                return {"error": f"API error: {resp.status}"}
            
            data = await resp.json()
            miners = data.get("miners", [])
            
            # Apply filters
            if hardware_type:
                miners = [m for m in miners if hardware_type.lower() in m.get("hardware", "").lower()]
            
            if min_score is not None:
                miners = [m for m in miners if m.get("score", 0) >= min_score]
            
            # Sort by score descending
            miners = sorted(miners, key=lambda x: x.get("score", 0), reverse=True)
            
            return {
                "count": len(miners),
                "limit": limit,
                "miners": miners[:limit]
            }
    
    async def _tool_get_wallet_balance(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get wallet balance."""
        wallet = args.get("wallet", "")
        return await self._get_wallet_balance_impl(wallet)
    
    async def _get_wallet_balance_impl(self, wallet: str) -> Dict[str, Any]:
        """Get wallet balance implementation."""
        url = f"{RUSTCHAIN_API_BASE}/api/wallets/{wallet}"
        
        async with self.session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                return {"found": True, "wallet": wallet, "balance": data}
            elif resp.status == 404:
                return {"found": False, "wallet": wallet, "error": "Wallet not found"}
            else:
                return {"error": f"API error: {resp.status}"}
    
    async def _tool_get_bounty_info(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get bounty information."""
        issue_number = args.get("issue_number")
        min_reward = args.get("min_reward")
        
        return await self._get_bounty_info_impl(issue_number, min_reward)
    
    async def _get_bounty_info_impl(self, issue_number: Optional[int] = None,
                                     min_reward: Optional[int] = None) -> Dict[str, Any]:
        """Get bounty info implementation."""
        # Fetch from GitHub API
        if issue_number:
            url = f"https://api.github.com/repos/Scottcjn/RustChain/issues/{issue_number}"
            async with self.session.get(url) as resp:
                if resp.status == 200:
                    issue = await resp.json()
                    return {"found": True, "bounty": self._parse_bounty_issue(issue)}
                else:
                    return {"error": f"Could not fetch issue #{issue_number}"}
        else:
            # Search for bounty issues
            url = "https://api.github.com/repos/Scottcjn/RustChain/issues?labels=bounty&state=open"
            async with self.session.get(url) as resp:
                if resp.status != 200:
                    return {"error": f"GitHub API error: {resp.status}"}
                
                issues = await resp.json()
                bounties = [self._parse_bounty_issue(issue) for issue in issues]
                
                if min_reward:
                    bounties = [b for b in bounties if b.get("reward_rtc", 0) >= min_reward]
                
                return {"count": len(bounties), "bounties": bounties}
    
    def _parse_bounty_issue(self, issue: Dict[str, Any]) -> Dict[str, Any]:
        """Parse a GitHub issue into bounty info."""
        title = issue.get("title", "")
        body = issue.get("body", "")
        
        # Extract reward from title or body
        reward_rtc = 0
        import re
        matches = re.findall(r'(\d+)\s*RTC', title + ' ' + body, re.IGNORECASE)
        if matches:
            reward_rtc = int(matches[0])
        
        return {
            "issue_number": issue.get("number"),
            "title": title,
            "reward_rtc": reward_rtc,
            "created_at": issue.get("created_at"),
            "url": issue.get("html_url"),
            "labels": [label.get("name") for label in issue.get("labels", [])]
        }
    
    async def _tool_get_agent_info(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get agent information."""
        agent_id = args.get("agent_id", "")
        url = f"{BEACON_URL}/api/agents/{agent_id}"
        
        async with self.session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                return {"found": True, "agent": data}
            elif resp.status == 404:
                return {"found": False, "agent_id": agent_id, "error": "Agent not found"}
            else:
                return {"error": f"API error: {resp.status}"}
    
    async def _tool_verify_hardware(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Verify hardware compatibility."""
        cpu_model = args.get("cpu_model", "")
        architecture = args.get("architecture", "")
        is_vm = args.get("is_vm", False)
        
        # Hardware multipliers (from RustChain docs)
        multipliers = {
            "powerpc g4": 2.5,
            "powerpc g5": 2.0,
            "powerpc g3": 1.8,
            "ibm power8": 2.0,
            "ibm power": 2.0,
            "apple silicon": 1.15,
            "m1": 1.15,
            "m2": 1.15,
            "m3": 1.15,
            "arm64": 1.0,
            "x86_64": 1.0,
            "x86": 1.0,
        }
        
        cpu_lower = cpu_model.lower()
        arch_lower = architecture.lower()
        
        # Find multiplier
        multiplier = 1.0
        matched_type = "Modern x86"
        
        for key, mult in multipliers.items():
            if key in cpu_lower or key in arch_lower:
                multiplier = mult
                matched_type = key.title()
                break
        
        # VM penalty
        if is_vm:
            multiplier *= 0.01  # VMs earn ~1% of normal rewards
            warning = "⚠️ Running in a VM will significantly reduce rewards"
        else:
            warning = None
        
        eligible = multiplier > 0.5
        
        return {
            "eligible": eligible,
            "hardware_type": matched_type,
            "multiplier": multiplier,
            "estimated_bonus": f"{(multiplier - 1) * 100:+.0f}%",
            "warning": warning,
            "notes": "Vintage hardware (PowerPC G3/G4/G5) receives the highest bonuses"
        }
    
    async def _tool_calculate_mining_rewards(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate estimated mining rewards."""
        hardware_type = args.get("hardware_type", "Modern x86")
        epochs = args.get("epochs", 0)
        uptime_percent = args.get("uptime_percent", 100)
        
        # Base reward per epoch (example value)
        base_reward_per_epoch = 0.1  # RTC
        
        # Hardware multipliers
        multipliers = {
            "powerpc g4": 2.5,
            "powerpc g5": 2.0,
            "powerpc g3": 1.8,
            "ibm power": 2.0,
            "apple silicon": 1.15,
            "modern x86": 1.0,
        }
        
        multiplier = multipliers.get(hardware_type.lower(), 1.0)
        
        # Calculate rewards
        base_rewards = epochs * base_reward_per_epoch
        adjusted_rewards = base_rewards * multiplier * (uptime_percent / 100)
        
        return {
            "hardware_type": hardware_type,
            "multiplier": multiplier,
            "epochs": epochs,
            "uptime_percent": uptime_percent,
            "base_reward_per_epoch": base_reward_per_epoch,
            "estimated_rewards_rtc": round(adjusted_rewards, 2),
            "breakdown": {
                "base": round(base_rewards, 2),
                "hardware_bonus": round(base_rewards * (multiplier - 1), 2),
                "uptime_adjustment": uptime_percent / 100
            }
        }
    
    def _get_quickstart_guide(self) -> str:
        """Get quickstart guide content."""
        return """# RustChain Quickstart Guide

## What is RustChain?

RustChain is a blockchain that rewards **vintage hardware** for being old, not fast. Your PowerPC G4 earns more than a modern Threadripper. That's the point.

## Quick Start (3 steps)

### 1. Install

```bash
pip install clawrtc
```

### 2. Run

```bash
clawrtc --wallet YOUR_WALLET_NAME
```

### 3. Monitor

Visit the [live explorer](https://rustchain.org/explorer) to see your miner!

## Hardware Multipliers

| Hardware | Multiplier | Examples |
|----------|------------|----------|
| PowerPC G4 | 2.5x | PowerBook G4, Power Mac G4 |
| PowerPC G5 | 2.0x | Power Mac G5, Xserve G5 |
| PowerPC G3 | 1.8x | iBook G3, Power Mac G3 |
| IBM POWER8+ | 2.0x | IBM S824, S822 |
| Apple Silicon | 1.15x | Mac Mini M2, MacBook M1/M2/M3 |
| Modern x86 | 1.0x | Any PC, laptop, NUC, Raspberry Pi |

## Important Notes

- **Real hardware only** — VMs earn near-zero rewards
- **Python 3.7+** required
- **No GPU needed** — CPU-based mining
- **Low power** — Runs on a Raspberry Pi

## Resources

- [Full Documentation](https://github.com/Scottcjn/RustChain)
- [Whitepaper](https://github.com/Scottcjn/RustChain/blob/main/docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf)
- [Discord](https://discord.gg/rustchain)
- [Bounties](https://github.com/Scottcjn/rustchain-bounties/issues)

## Get Help

- Check existing [issues](https://github.com/Scottcjn/RustChain/issues)
- Join the Discord community
- Tag @Scottcjn for urgent matters
"""
    
    async def run(self):
        """Run the MCP server."""
        await self.start()
        
        async with stdio_server() as (read_stream, write_stream):
            await self.app.run(
                read_stream,
                write_stream,
                self.app.create_initialization_options()
            )
        
        await self.stop()


async def main():
    """Main entry point."""
    server = RustChainMCP()
    await server.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server terminated by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)
