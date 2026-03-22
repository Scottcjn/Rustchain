#!/usr/bin/env python3
"""
RustChain WSGI Entry Point for Gunicorn Production Server
=========================================================

Usage:
    gunicorn -w 4 -b 0.0.0.0:8099 wsgi:app --timeout 120
"""

import os
import sys
import importlib.util

# Ensure the rustchain directory is in path
base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_dir)

# Load the main module dynamically (handles dots/dashes in filename)
spec = importlib.util.spec_from_file_location(
    "rustchain_main",
    os.path.join(base_dir, "rustchain_v2_integrated_v2.2.1_rip200.py")
)
rustchain_main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rustchain_main)

# Get the Flask app
app = rustchain_main.app
init_db = rustchain_main.init_db
DB_PATH = rustchain_main.DB_PATH

# Initialize database
init_db()

# Initialize P2P if available
p2p_node = None
try:
    from rustchain_p2p_init import init_p2p
    p2p_node = init_p2p(app, DB_PATH)
    print("[WSGI] P2P initialized successfully")
except ImportError as e:
    print(f"[WSGI] P2P not available: {e}")
except Exception as e:
    print(f"[WSGI] P2P init failed: {e}")

# RIP-306: SophiaCore Attestation Inspector
try:
    from sophia_attestation_inspector import register_sophia_endpoints, ensure_schema as sophia_schema
    sophia_schema(DB_PATH)
    register_sophia_endpoints(app, DB_PATH)
    print("[RIP-306] SophiaCore Attestation Inspector registered")
    print("[RIP-306]   Endpoints: /sophia/status, /sophia/inspect, /sophia/batch")
except ImportError as e:
    print(f"[RIP-306] SophiaCore not available: {e}")
except Exception as e:
    print(f"[RIP-306] SophiaCore init failed: {e}")

# BCOS v2 Verification Endpoints
try:
    from bcos_routes import register_bcos_routes, init_bcos_table
    import sqlite3
    with sqlite3.connect(DB_PATH) as _db:
        init_bcos_table(_db)
        register_bcos_routes(app, DB_PATH)
        print("[BCOS v2] registered successfully")
        print("[BCOS v2]   Endpoints: /bcos/directory, /bcos/verify, /bcos/certificate")
except ImportError as e:
    print(f"[BCOS v2] not available: {e}")
except Exception as e:
    print(f"[BCOS v2] init failed: {e}")

# Agent Memory API (Bounty #2285: Self-Referencing Past Content)
try:
    from flask import jsonify, request
    from agent_memory import AgentMemory, AgentStats

    # Initialize agent memory
    AGENT_MEMORY_DB = os.path.join(base_dir, "agent_memory.db")
    agent_memory = AgentMemory(AGENT_MEMORY_DB)

    @app.route("/api/v1/agents/<agent_name>/memory", methods=["GET"])
    def agent_memory_search(agent_name):
        """Search agent memory for semantically similar content.
        Query: ?query=topic
        """
        query = request.args.get("query", "")
        if not query:
            return jsonify({"error": "Missing query parameter"}), 400

        results = agent_memory.search_memory(agent_name, query)
        response = [
            {
                "video_id": r.video.video_id,
                "title": r.video.title,
                "similarity": r.similarity,
                "summary": r.summary
            }
            for r in results
        ]
        return jsonify({
            "query": query,
            "results": response,
            "count": len(response)
        })

    @app.route("/api/v1/agents/<agent_name>/stats", methods=["GET"])
    def agent_memory_stats(agent_name):
        """Get agent memory statistics: video count, top topics, milestone detection."""
        stats = agent_memory.get_agent_stats(agent_name)
        if stats is None:
            return jsonify({"error": "Agent not found"}), 404

        return jsonify({
            "agent_name": agent_name,
            "total_videos": stats.total_videos,
            "first_upload_timestamp": stats.first_video_timestamp,
            "last_upload_timestamp": stats.last_video_timestamp,
            "top_topics": stats.top_topics,
            "has_milestone": stats.has_milestone,
            "milestone": stats.milestone
        })

    print("[Agent Memory] registered successfully")
    print("[Agent Memory]   Endpoints: /api/v1/agents/{name}/memory, /api/v1/agents/{name}/stats")
except ImportError as e:
    print(f"[Agent Memory] not available: {e}")
except Exception as e:
    print(f"[Agent Memory] init failed: {e}")

# Expose the app for gunicorn
application = app

if __name__ == "__main__":
    # For direct execution (development)
    app.run(host='0.0.0.0', port=8099, debug=False)
