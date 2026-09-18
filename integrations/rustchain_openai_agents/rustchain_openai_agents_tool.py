# SPDX-License-Identifier: MIT
"""
integrations/rustchain_openai_agents/rustchain_openai_agents_tool.py

Dependency-light RustChain native tools for the OpenAI Agents SDK.
Provides:
  - check_balance(wallet_id)
  - list_bounties(limit)
  - get_node_health()
  - get_current_epoch()

Compatible with OpenAI Agents SDK (`agents.function_tool`), Swarm, and stdlib.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class RustChainOpenAIAgentsTools:
    """Expose RustChain public reads as plain methods and OpenAI Agents SDK function tools."""

    def __init__(
        self,
        base_url: str = "https://rustchain.org",
        bounty_repo: str = "Scottcjn/rustchain-bounties",
        timeout: float = 10.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.bounty_repo = bounty_repo
        self.timeout = timeout

    def _get_json(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        if params:
            url = f"{url}?{urlencode(params)}"
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "rustchain-openai-agents-sdk/1.0",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return {"ok": False, "error": f"HTTP {exc.code}", "url": url}
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            return {"ok": False, "error": str(exc), "url": url}

    def check_balance(self, wallet_id: str) -> Dict[str, Any]:
        """Return the confirmed RTC balance for a wallet or miner ID."""
        wallet_id = (wallet_id or "").strip()
        if not wallet_id:
            return {"ok": False, "error": "wallet_id must not be empty"}
        result = self._get_json(
            f"{self.base_url}/wallet/balance",
            {"miner_id": wallet_id},
        )
        if isinstance(result, dict) and result.get("ok") is False:
            return result
        return {"ok": True, "wallet_id": wallet_id, "balance": result}

    def list_bounties(self, limit: int = 10) -> Dict[str, Any]:
        """List recent open RustChain bounty-board issues."""
        try:
            limit = max(1, min(int(limit), 50))
        except (TypeError, ValueError):
            return {"ok": False, "error": "limit must be an integer from 1 to 50"}

        result = self._get_json(
            f"https://api.github.com/repos/{self.bounty_repo}/issues",
            {"state": "open", "per_page": limit, "labels": "bounty"},
        )
        if isinstance(result, dict):
            return result

        bounties = [
            {
                "number": item.get("number"),
                "title": item.get("title"),
                "url": item.get("html_url"),
                "updated_at": item.get("updated_at"),
            }
            for item in result
            if "pull_request" not in item
        ]
        return {"ok": True, "count": len(bounties), "bounties": bounties}

    def get_node_health(self) -> Dict[str, Any]:
        """Return public node health, falling back to explorer statistics."""
        health = self._get_json(f"{self.base_url}/health")
        if not (isinstance(health, dict) and health.get("ok") is False):
            return {"ok": True, "source": "/health", "health": health}

        stats = self._get_json("https://explorer.rustchain.org/api/stats")
        if isinstance(stats, dict) and stats.get("ok") is False:
            return {
                "ok": False,
                "error": "health and explorer stats endpoints failed",
            }
        return {
            "ok": True,
            "source": "https://explorer.rustchain.org/api/stats",
            "health": stats,
        }

    def get_current_epoch(self) -> Dict[str, Any]:
        """Return the current epoch from the public node epoch endpoint."""
        epoch_data = self._get_json(f"{self.base_url}/epoch")
        if isinstance(epoch_data, dict) and epoch_data.get("ok") is False:
            return epoch_data
        if not isinstance(epoch_data, dict):
            return {"ok": False, "error": "epoch response was not an object"}
        epoch = epoch_data.get("epoch", epoch_data.get("current_epoch"))
        if epoch is None:
            return {"ok": False, "error": "epoch response did not include an epoch"}
        return {"ok": True, "epoch": epoch, "epoch_data": epoch_data}

    def as_openai_agent_tools(self) -> List[Any]:
        """
        Return function tools ready for the OpenAI Agents SDK / Swarm.
        Uses lazy import so environments without `agents` installed can still
        use the plain class methods cleanly.
        """
        try:
            from agents import function_tool
        except ImportError:
            # Fallback decorator for standalone / mock environments
            def function_tool(func: Callable) -> Callable:
                func.is_openai_agent_tool = True
                return func

        @function_tool
        def check_balance_tool(wallet_id: str) -> str:
            """Check confirmed RTC token balance for a RustChain wallet address or miner ID."""
            return json.dumps(self.check_balance(wallet_id), sort_keys=True)

        @function_tool
        def list_bounties_tool(limit: int = 10) -> str:
            """List open bounties available for earning RTC on the RustChain network."""
            return json.dumps(self.list_bounties(limit), sort_keys=True)

        @function_tool
        def get_node_health_tool() -> str:
            """Get real-time health status, block tip, and peer count of the RustChain node."""
            return json.dumps(self.get_node_health(), sort_keys=True)

        @function_tool
        def get_current_epoch_tool() -> str:
            """Get the current consensus epoch number and enrollment state of the RustChain network."""
            return json.dumps(self.get_current_epoch(), sort_keys=True)

        return [
            check_balance_tool,
            list_bounties_tool,
            get_node_health_tool,
            get_current_epoch_tool,
        ]
