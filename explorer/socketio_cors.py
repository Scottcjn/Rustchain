# SPDX-License-Identifier: MIT
"""Socket.IO CORS origin helpers for explorer runtimes."""

from __future__ import annotations

import os


TRUSTED_SOCKETIO_ORIGINS = (
    "https://rustchain.org",
    "https://www.rustchain.org",
)


def default_socketio_origins(*, local_port: int | str | None = None) -> list[str]:
    origins = list(TRUSTED_SOCKETIO_ORIGINS)
    if local_port is not None:
        origins.extend(
            [
                f"http://localhost:{local_port}",
                f"http://127.0.0.1:{local_port}",
            ]
        )
    return origins


def parse_socketio_cors_origins(
    raw_value: str | None = None,
    *,
    local_port: int | str | None = None,
) -> list[str]:
    """Return an explicit Socket.IO origin allowlist.

    Flask-SocketIO accepts "*" as a permissive origin policy; explorer feeds
    carry live chain and miner state, so production should be allowlisted.
    """
    if raw_value is None:
        raw_value = os.environ.get("EXPLORER_SOCKETIO_CORS_ORIGINS")

    if raw_value is None or not raw_value.strip():
        return default_socketio_origins(local_port=local_port)

    origins: list[str] = []
    for item in raw_value.split(","):
        origin = item.strip()
        if not origin:
            continue
        if origin == "*":
            raise ValueError("EXPLORER_SOCKETIO_CORS_ORIGINS must not include '*'")
        if origin not in origins:
            origins.append(origin)

    if not origins:
        return default_socketio_origins(local_port=local_port)
    return origins
