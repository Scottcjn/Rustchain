"""WebSocket integration for real-time RustChain block feeds.

Uses the standard `websockets` library (httpx does not support WebSocket on its own).
Reference: websocket_feed.py in the RustChain repository.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Callable, Awaitable

import websockets

from rustchain.exceptions import NetworkError
from rustchain.models import Block

logger = logging.getLogger(__name__)

DEFAULT_WS_URL = "ws://50.28.86.131:8099/ws/blocks"


BlockCallback = Callable[[Block], Awaitable[None]]


class WebSocketFeed:
    """Real-time block feed subscriber via WebSocket.

    Parameters
    ----------
    url : str
        WebSocket endpoint URL (default: ws://host:port/ws/blocks).
    """

    def __init__(self, url: str = DEFAULT_WS_URL) -> None:
        self._url = url
        self._running = False
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._tasks: list[asyncio.Task[None]] = []

    async def connect(self) -> None:
        """Establish the WebSocket connection."""
        try:
            self._ws = await websockets.connect(self._url, ping_interval=20)
            self._running = True
            logger.info("WebSocket connected to %s", self._url)
        except Exception as e:
            raise NetworkError(f"Failed to connect to WebSocket: {e}") from e

    async def disconnect(self) -> None:
        """Close the WebSocket connection gracefully."""
        self._running = False
        if self._ws:
            await self._ws.close()
            self._ws = None
        logger.info("WebSocket disconnected")

    async def _recv_loop(self, callback: BlockCallback) -> None:
        """Internal loop that receives messages and dispatches to callback."""
        if self._ws is None:
            raise NetworkError("WebSocket not connected")

        try:
            while self._running:
                try:
                    raw = await self._ws.recv()
                except websockets.ConnectionClosed:
                    logger.warning("WebSocket connection closed by server")
                    break

                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning("Received non-JSON message: %s", raw)
                    continue

                # Expected payload: {"type": "new_block", "block": {...}}
                block_data = data.get("block", data)
                try:
                    block = Block(**block_data)
                except Exception:
                    logger.warning("Failed to parse block data: %s", block_data)
                    continue

                try:
                    await callback(block)
                except Exception as e:
                    logger.error("Callback raised: %s", e)

        except asyncio.CancelledError:
            logger.info("Receive loop cancelled")
        finally:
            self._running = False

    async def subscribe(self, callback: BlockCallback) -> None:
        """Subscribe to new blocks and invoke callback for each one.

        This method runs the receive loop in the background. Use
        ``disconnect()`` to stop.

        Parameters
        ----------
        callback : BlockCallback
            Async callable invoked with each new :class:`Block`.
        """
        if not self._running or self._ws is None:
            await self.connect()

        task = asyncio.create_task(self._recv_loop(callback))
        self._tasks.append(task)

    async def subscribe_once(self, timeout: float = 60.0) -> Block:
        """Subscribe and wait for the next block.

        Parameters
        ----------
        timeout : float
            Seconds to wait before raising TimeoutError.

        Returns
        -------
        Block
            The next newly received block.
        """
        result: dict[str, object] = {}

        async def _capture(block: Block) -> None:
            result["block"] = block

        await self.subscribe(_capture)
        deadline = asyncio.get_event_loop().time() + timeout
        while not result:
            if asyncio.get_event_loop().time() >= deadline:
                raise TimeoutError("Timed out waiting for next block")
            await asyncio.sleep(0.5)
        return result["block"]  # type: ignore[index]

    async def __aenter__(self) -> "WebSocketFeed":
        await self.connect()
        return self

    async def __aexit__(self, *args: object) -> None:
        for task in self._tasks:
            task.cancel()
        await self.disconnect()
