# SPDX-License-Identifier: MIT
"""Dependency-light RustChain tools for Hugging Face smolagents."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class RustChainSmolagentsTools:
    """Expose RustChain public reads as methods and smolagents Tool objects."""

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
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[Any]:
        if params:
            url = f"{url}?{urlencode(params)}"
        request = Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "rustchain-smolagents"},
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return {"ok": False, "error": f"HTTP {exc.code}", "url": url}
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            return {"ok": False, "error": str(exc), "url": url}

    def check_balance(self, wallet_id: str) -> dict[str, Any]:
        """Return the confirmed RTC balance for a wallet or miner ID."""
        if not wallet_id.strip():
            return {"ok": False, "error": "wallet_id must not be empty"}
        result = self._get_json(
            f"{self.base_url}/wallet/balance",
            {"miner_id": wallet_id.strip()},
        )
        if isinstance(result, dict) and result.get("ok") is False:
            return result
        return {"ok": True, "wallet_id": wallet_id.strip(), "balance": result}

    def list_bounties(self, limit: int = 10) -> dict[str, Any]:
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

    def get_node_health(self) -> dict[str, Any]:
        """Return public node health, falling back to node statistics."""
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

    def get_current_epoch(self) -> dict[str, Any]:
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

    def as_smolagents_tools(self) -> list[Any]:
        """Create smolagents Tool objects for the four public actions."""
        try:
            from smolagents import Tool
        except ImportError as exc:
            raise RuntimeError(
                "smolagents is required for adapters: pip install smolagents"
            ) from exc

        client = self

        class CheckBalanceTool(Tool):
            name = "check_balance"
            description = "Look up the confirmed RustChain RTC balance for a wallet or miner ID."
            inputs = {
                "wallet_id": {
                    "type": "string",
                    "description": "RustChain wallet or miner identifier to query.",
                }
            }
            output_type = "object"

            def forward(self, wallet_id: str) -> dict[str, Any]:
                return client.check_balance(wallet_id)

        class ListBountiesTool(Tool):
            name = "list_bounties"
            description = "List recent open RustChain bounty-board issues from GitHub."
            inputs = {
                "limit": {
                    "type": "integer",
                    "description": "How many open bounty issues to return, from 1 to 50.",
                }
            }
            output_type = "object"

            def forward(self, limit: int) -> dict[str, Any]:
                return client.list_bounties(limit)

        class GetNodeHealthTool(Tool):
            name = "get_node_health"
            description = "Read RustChain public node health with explorer fallback."
            inputs = {}
            output_type = "object"

            def forward(self) -> dict[str, Any]:
                return client.get_node_health()

        class GetCurrentEpochTool(Tool):
            name = "get_current_epoch"
            description = "Read the current RustChain epoch from the public node API."
            inputs = {}
            output_type = "object"

            def forward(self) -> dict[str, Any]:
                return client.get_current_epoch()

        return [
            CheckBalanceTool(),
            ListBountiesTool(),
            GetNodeHealthTool(),
            GetCurrentEpochTool(),
        ]
