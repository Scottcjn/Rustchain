"""Dependency-light RustChain tools for Microsoft AutoGen."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class RustChainAutoGenTools:
    """Expose RustChain public reads as methods and AutoGen FunctionTools."""

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
            headers={"Accept": "application/json", "User-Agent": "rustchain-autogen"},
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
        limit = max(1, min(int(limit), 50))
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
        stats = self._get_json(f"{self.base_url}/api/stats")
        if isinstance(stats, dict) and stats.get("ok") is False:
            return {"ok": False, "error": "health and stats endpoints failed"}
        return {"ok": True, "source": "/api/stats", "health": stats}

    def get_current_epoch(self) -> dict[str, Any]:
        """Return the current epoch from the public node statistics."""
        stats = self._get_json(f"{self.base_url}/api/stats")
        if isinstance(stats, dict) and stats.get("ok") is False:
            return stats
        if not isinstance(stats, dict):
            return {"ok": False, "error": "stats response was not an object"}
        epoch = stats.get("epoch", stats.get("current_epoch"))
        if epoch is None:
            return {"ok": False, "error": "stats response did not include an epoch"}
        return {"ok": True, "epoch": epoch, "stats": stats}

    def as_autogen_tools(self) -> list[Any]:
        """Create AutoGen FunctionTool objects for the four public actions."""
        try:
            from autogen_core.tools import FunctionTool
        except ImportError as exc:
            raise RuntimeError(
                "AutoGen is required for adapters: pip install autogen-core"
            ) from exc

        return [
            FunctionTool(self.check_balance, description=self.check_balance.__doc__ or ""),
            FunctionTool(self.list_bounties, description=self.list_bounties.__doc__ or ""),
            FunctionTool(self.get_node_health, description=self.get_node_health.__doc__ or ""),
            FunctionTool(self.get_current_epoch, description=self.get_current_epoch.__doc__ or ""),
        ]
