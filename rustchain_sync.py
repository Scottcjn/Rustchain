#!/usr/bin/env python3
"""Compatibility wrapper for RustChain sync module.

Issue #36 deliverable asks for `rustchain_sync.py`. The implementation lives in
`node/rustchain_sync.py`; this shim keeps import paths simple for operators.
"""

from node.rustchain_sync import RustChainSyncManager  # re-export

__all__ = ["RustChainSyncManager"]
