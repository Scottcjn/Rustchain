#!/usr/bin/env python3
"""
BoTTube Agent Memory System
============================

Issue #2285: Agent Memory (self-referencing past content)

This package provides:
- memory_store: SQLite-backed persistent storage for content references
- memory_engine: High-level memory operations for self-referencing
- memory_routes: Flask API routes for memory operations

Usage:
    from bottube.memory import AgentMemoryEngine, AgentMemoryStore
    from bottube.memory import init_memory_routes

    # Programmatic usage
    engine = AgentMemoryEngine("memory.db")
    engine.record_content(
        agent_id="my-agent",
        content_id="video-123",
        title="Tutorial on Mining",
        tags=["mining", "tutorial"]
    )
    context = engine.build_context(agent_id="my-agent", topic="mining")

    # Flask integration
    from flask import Flask
    app = Flask(__name__)
    init_memory_routes(app)
"""

from __future__ import annotations

from memory_store import AgentMemoryStore
from memory_engine import AgentMemoryEngine, MemoryContext, ContentRecall
from memory_routes import init_memory_routes, memory_bp

__version__ = "1.0.0"
__all__ = [
    "AgentMemoryStore",
    "AgentMemoryEngine",
    "MemoryContext",
    "ContentRecall",
    "init_memory_routes",
    "memory_bp",
]
