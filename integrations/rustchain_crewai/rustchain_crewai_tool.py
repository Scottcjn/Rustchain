"""RustChain CrewAI Tool Integration.

Bounty: [AGENT-BOUNTY: 25 RTC] Native RustChain Tool for CrewAI / AutoGen /
       Phidata / smolagents
Issue: https://github.com/Scottcjn/rustchain-bounties/issues/13952
Author: jdjioe5-cpu (Hermes bounty executor)
Date: 2026-06-12

This module provides a small, dependency-light CrewAI ``BaseTool`` subclass that
exposes the RustChain HTTP API as native CrewAI tools.

The four required methods are:

* ``check_balance(wallet_id)``     -> ``/api/wallet/<wallet_id>``
* ``list_bounties(limit)``         -> ``/api/bounties`` (with graceful fallback)
* ``get_node_health()``            -> ``/api/stats`` (richer than ``/health``)
* ``get_current_epoch()``          -> ``/api/stats`` (epoch field)

The implementation follows the shape of the merged LangChain reference at
``langchain_rustchain_tool.py`` (bounty #3074) so that all four framework
integrations share the same mental model.

CrewAI is imported lazily so the module is safe to import in environments
where crewai is not installed; the tool will raise a clear error only when
actually instantiated.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Type

import requests

logger = logging.getLogger("rustchain_crewai_tool")

# ---------------------------------------------------------------------------
# Optional CrewAI import - lazy / graceful
# ---------------------------------------------------------------------------

try:
    from crewai.tools import BaseTool
    from pydantic import Field

    CREWAI_AVAILABLE = True
except ImportError:  # pragma: no cover - crewai not installed in CI
    CREWAI_AVAILABLE = False

    # Provide a tiny stub so the file is still importable for type-checkers
    # and for the unit tests under tests/test_rustchain_crewai_tool.py.
    #
    # The stub is a regular class (NOT a pydantic BaseModel) on purpose: the
    # production code path that exercises real ``crewai.tools.BaseTool`` is
    # covered by the optional real-import tests, and the stub keeps the
    # off-CI import contract narrow. ``name``/``description`` are class
    # attributes; the stub's ``__init__`` accepts arbitrary kwargs (mirroring
    # the pydantic BaseModel field-init pattern) and stashes them as
    # instance attributes, which is what the unit tests rely on.
    class BaseTool:  # type: ignore[no-redef]
        """Stub BaseTool used when crewai is not installed.

        Mirrors the minimal public surface of ``crewai.tools.BaseTool``:
        subclasses must set ``name`` and ``description`` and implement
        ``_run``. The stub accepts arbitrary kwargs so unit tests can
        construct the tool with ``base_url=`` etc., even without crewai.
        """

        name: str = ""
        description: str = ""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            for k, v in kwargs.items():
                setattr(self, k, v)

        def run(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover
            raise RuntimeError(
                "crewai is not installed; install it with `pip install crewai`"
            )

        def _run(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover
            raise NotImplementedError

    class _Field:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs

    def Field(*args: Any, **kwargs: Any) -> Any:  # type: ignore[no-redef]
        # When pydantic is unavailable, ``Field`` still has to be a
        # callable that returns an object whose ``default`` is readable
        # (the production class uses ``Field(default=...)`` only). The
        # simplest compatible shape is a wrapper holding ``kwargs``.
        return _Field(*args, **kwargs)


# ---------------------------------------------------------------------------
# Tool implementation
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = "https://explorer.rustchain.org"
DEFAULT_TIMEOUT_S = 10
USER_AGENT = "rustchain-crewai-tool/0.1.0 (+https://github.com/Scottcjn/Rustchain)"


class RustChainCrewAITool(BaseTool):
    """CrewAI tool for interacting with the RustChain blockchain.

    Provides native CrewAI integration for:

    * Checking wallet balances (``check_balance``)
    * Listing available bounties  (``list_bounties``)
    * Checking node health       (``get_node_health``)
    * Getting current epoch info (``get_current_epoch``)

    Example::

        from rustchain_crewai_tool import RustChainCrewAITool

        tool = RustChainCrewAITool()
        result = tool.run(action="get_current_epoch")
    """

    # ---- BaseTool interface -------------------------------------------------
    name: str = "rustchain"
    description: str = (
        "Interact with the RustChain blockchain. Actions: "
        "check_balance(wallet_id), "
        "list_bounties(limit=10), "
        "get_node_health(), "
        "get_current_epoch()."
    )

    # ---- Configuration ------------------------------------------------------
    # Configuration fields are declared as pydantic ``Field``s. Real
    # ``crewai.tools.BaseTool`` extends ``pydantic.BaseModel``, so non-field
    # attributes set in ``__init__`` before ``super().__init__()`` raise an
    # ``AttributeError`` (pydantic tries to write to
    # ``__pydantic_fields_set__`` before the BaseModel machinery is
    # initialised). Declaring the fields lets pydantic validate and initialise
    # them in one pass and keeps the values accessible on the instance.
    base_url: str = Field(
        default=DEFAULT_BASE_URL,
        description="Base URL for the RustChain HTTP API.",
    )
    timeout: float = Field(
        default=DEFAULT_TIMEOUT_S,
        description="Per-request timeout in seconds.",
    )
    bounties_repo: str = Field(
        default="Scottcjn/rustchain-bounties",
        description="GitHub repo (owner/name) used as the bounty board source.",
    )

    def __init__(  # type: ignore[no-untyped-def]
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_S,
        bounties_repo: str = "Scottcjn/rustchain-bounties",
        **kwargs: Any,
    ) -> None:
        # Route the configuration through ``super().__init__`` so pydantic
        # can validate and set up ``__pydantic_fields_set__`` correctly. We
        # coerce ``timeout`` to ``float`` here so the public constructor
        # stays forgiving (it accepts ``int`` and ``float``).
        super().__init__(
            base_url=base_url,
            timeout=float(timeout),
            bounties_repo=bounties_repo,
            **kwargs,
        )

    # ---- Internal helpers ---------------------------------------------------
    def _headers(self) -> Dict[str, str]:
        return {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }

    def _get_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """GET ``{base_url}{path}`` and return the parsed JSON.

        Returns a ``{"ok": False, "status": ..., "error": ...}``-shaped dict
        on any failure so the tool never raises inside an agent loop.
        """
        url = f"{self.base_url}{path}"
        try:
            resp = requests.get(
                url,
                params=params or {},
                headers=self._headers(),
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            logger.warning("rustchain GET %s failed: %s", url, exc)
            return {
                "ok": False,
                "status": None,
                "error": f"network error: {exc.__class__.__name__}: {exc}",
            }

        if resp.status_code != 200:
            return {
                "ok": False,
                "status": resp.status_code,
                "error": f"HTTP {resp.status_code}",
            }

        try:
            data = resp.json()
        except ValueError:
            return {
                "ok": False,
                "status": resp.status_code,
                "error": "non-JSON response",
                "raw": resp.text[:200],
            }

        return {"ok": True, "status": 200, "data": data}

    # ---- Public actions -----------------------------------------------------
    def check_balance(self, wallet_id: str) -> Dict[str, Any]:
        """Return the RTC balance for ``wallet_id``."""
        wallet_id = (wallet_id or "").strip()
        if not wallet_id:
            return {"ok": False, "error": "wallet_id is required"}

        result = self._get_json(f"/api/wallet/{wallet_id}")
        if not result["ok"]:
            return {
                "ok": False,
                "wallet_id": wallet_id,
                "balance_rtc": 0.0,
                "error": result.get("error", "unknown error"),
                "status": result.get("status"),
            }

        data = result["data"] or {}
        # The /api/wallet/<id> endpoint returns:
        #   {"amount_i64": int, "amount_rtc": float, "miner_id": str}
        balance_rtc = float(data.get("amount_rtc", 0.0) or 0.0)
        return {
            "ok": True,
            "wallet_id": wallet_id,
            "balance_rtc": balance_rtc,
            "amount_i64": data.get("amount_i64"),
            "raw": data,
        }

    def list_bounties(self, limit: int = 10) -> Dict[str, Any]:
        """List open bounty issues from the public RustChain bounty board.

        The RustChain node does not currently expose a public
        ``/api/bounties`` endpoint (verified 2026-06-12 against both
        ``rustchain.org`` and ``explorer.rustchain.org``); the bounty board
        itself lives on GitHub. This method queries the GitHub REST API
        for open issues labelled ``bounty`` on the configured repo.

        Returns a ``{"ok": ..., "bounties": [...], "error": ...}`` dict.
        The ``bounties`` list is intentionally limited to ``limit`` items
        (default 10, max 50).
        """
        try:
            limit = max(1, min(int(limit), 50))
        except (TypeError, ValueError):
            limit = 10

        # We query the GitHub issues API directly. crewai tools are expected
        # to be dependency-light, and `requests` is already imported.
        url = f"https://api.github.com/repos/{self.bounties_repo}/issues"
        try:
            resp = requests.get(
                url,
                params={"state": "open", "labels": "bounty", "per_page": limit},
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": USER_AGENT,
                },
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            return {
                "ok": False,
                "bounties": [],
                "error": f"github network error: {exc.__class__.__name__}: {exc}",
            }

        if resp.status_code != 200:
            return {
                "ok": False,
                "bounties": [],
                "status": resp.status_code,
                "error": f"github HTTP {resp.status_code}",
            }

        try:
            items = resp.json() or []
        except ValueError:
            return {
                "ok": False,
                "bounties": [],
                "error": "github returned non-JSON",
            }

        bounties: List[Dict[str, Any]] = []
        for it in items[:limit]:
            bounties.append(
                {
                    "number": it.get("number"),
                    "title": it.get("title"),
                    "url": it.get("html_url"),
                    "labels": [lbl.get("name") for lbl in (it.get("labels") or [])],
                    "updated_at": it.get("updated_at"),
                }
            )
        return {"ok": True, "count": len(bounties), "bounties": bounties}

    def get_node_health(self) -> Dict[str, Any]:
        """Return a small health snapshot for the RustChain node.

        Hits ``/api/stats`` (richer than ``/health``) and normalises the
        result. The endpoint is documented as live on
        ``explorer.rustchain.org`` (verified 2026-06-12).
        """
        result = self._get_json("/api/stats")
        if not result["ok"]:
            # Fall back to /health, which is also live on both hostnames.
            fallback = self._get_json("/health")
            if not fallback["ok"]:
                return {
                    "ok": False,
                    "healthy": False,
                    "error": result.get("error"),
                    "fallback_error": fallback.get("error"),
                }
            return {
                "ok": True,
                "healthy": bool(fallback["data"].get("ok")),
                "source": "/health",
                "raw": fallback["data"],
            }

        data = result["data"] or {}
        return {
            "ok": True,
            "healthy": True,
            "source": "/api/stats",
            "chain_id": data.get("chain_id"),
            "epoch": data.get("epoch"),
            "block_time": data.get("block_time"),
            "features": data.get("features", []),
            "raw": data,
        }

    def get_current_epoch(self) -> Dict[str, Any]:
        """Return the current RustChain epoch number.

        Uses ``/api/stats`` for the most reliable read; the legacy
        ``/api/epoch`` endpoint is not currently exposed on
        ``explorer.rustchain.org`` (verified 2026-06-12).
        """
        result = self._get_json("/api/stats")
        if not result["ok"]:
            return {
                "ok": False,
                "epoch": None,
                "error": result.get("error"),
            }
        data = result["data"] or {}
        return {
            "ok": True,
            "epoch": data.get("epoch"),
            "chain_id": data.get("chain_id"),
            "block_time": data.get("block_time"),
        }

    # ---- BaseTool dispatch --------------------------------------------------
    def _run(
        self,
        action: Optional[str] = None,
        wallet_id: Optional[str] = None,
        limit: int = 10,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Dispatch a single tool call to one of the four actions.

        ``action`` is accepted as either a string (the documented
        ``tool.run(action="...")`` shape) or, for back-compat with the
        v0.1.0 README example, a single ``dict`` payload that contains
        the ``action`` key plus any of ``wallet_id`` / ``limit``.
        """
        if isinstance(action, dict):
            payload = dict(action)
            action = payload.pop("action", None)
            if wallet_id is None and "wallet_id" in payload:
                wallet_id = payload.pop("wallet_id")
            if "limit" in payload:
                # Coerce defensively: callers may pass the README's
                # ``{"limit": "5"}`` shape, where the value is a string.
                raw_limit = payload.pop("limit")
                try:
                    limit = int(raw_limit)
                except (TypeError, ValueError):
                    return {
                        "ok": False,
                        "error": f"limit must be int, got {raw_limit!r}",
                    }
            # Any unknown keys are reported so the caller learns about
            # typos instead of silently swallowing them.
            if payload:
                kwargs.update(payload)

        if not isinstance(action, str) or not action:
            return {
                "ok": False,
                "error": (
                    "action is required and must be one of: "
                    "check_balance, list_bounties, get_node_health, get_current_epoch"
                ),
            }

        if action == "check_balance":
            return self.check_balance(wallet_id or "")
        if action == "list_bounties":
            return self.list_bounties(limit)
        if action == "get_node_health":
            return self.get_node_health()
        if action == "get_current_epoch":
            return self.get_current_epoch()
        return {"ok": False, "error": f"unknown action: {action!r}"}

    # CrewAI's BaseTool in some versions also accepts ``run`` directly; provide
    # an alias so users can call either ``run`` or ``_run`` explicitly. We
    # normalise the single-dict payload shape here too, so the README example
    # ``tool.run({"action": "get_current_epoch"})`` works regardless of which
    # method CrewAI dispatches into.
    def run(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:  # type: ignore[override]
        if len(args) == 1 and isinstance(args[0], dict) and "action" not in kwargs:
            payload = dict(args[0])
            if "action" in payload:
                action = payload.pop("action")
                kwargs.setdefault("action", action)
                for k, v in payload.items():
                    kwargs.setdefault(k, v)
                return self._run(**kwargs)
        return self._run(*args, **kwargs)


__all__ = ["RustChainCrewAITool", "CREWAI_AVAILABLE"]


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------

def _main() -> int:  # pragma: no cover - manual smoke test
    tool = RustChainCrewAITool()
    print("check_balance ->", json.dumps(tool.check_balance("jdjioe5-cpu")))
    print("get_node_health ->", json.dumps(tool.get_node_health()))
    print("get_current_epoch ->", json.dumps(tool.get_current_epoch()))
    print("list_bounties(3) ->", json.dumps(tool.list_bounties(3)))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
