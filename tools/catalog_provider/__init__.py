# SPDX-License-Identifier: MIT
"""Unattended RTC service catalog provider daemon and pluggable workers.

Watches requested orders on ``/catalog/orders?role=provider&status=requested``,
runs a pluggable :class:`Worker` to produce a deliverable file, computes its
SHA-256, calls ``/catalog/orders/<id>/deliver``, persists idempotent state on
disk across restarts, and watches accepted orders until payment is ``confirmed``
on the RustChain ledger.
"""

from .daemon import (
    KillSwitchActive,
    ProviderConfig,
    ProviderDaemon,
    RateLimitExceeded,
    load_catalog_cli,
)
from .workers import CodeReviewWorker, DocsLintWorker, WorkResult, Worker

__all__ = [
    "CodeReviewWorker",
    "DocsLintWorker",
    "KillSwitchActive",
    "ProviderConfig",
    "ProviderDaemon",
    "RateLimitExceeded",
    "WorkResult",
    "Worker",
    "load_catalog_cli",
]
