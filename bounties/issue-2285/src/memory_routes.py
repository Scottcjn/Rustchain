#!/usr/bin/env python3
"""
BoTTube Agent Memory API Routes
================================

Flask routes for agent memory operations.

Endpoints:
    POST   /api/memory/record          - Record new content
    GET    /api/memory/recent          - Get recent content
    GET    /api/memory/search          - Search by topic
    GET    /api/memory/tags            - Search by tags
    GET    /api/memory/context         - Build memory context
    POST   /api/memory/reference       - Generate self-reference
    POST   /api/memory/link            - Link content items
    GET    /api/memory/stats           - Get memory statistics
    DELETE /api/memory/clear           - Clear agent memory

Usage:
    from memory_routes import init_memory_routes
    init_memory_routes(app)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request, current_app

from memory_store import AgentMemoryStore
from memory_engine import AgentMemoryEngine, MemoryContext


# Create blueprint for memory routes
memory_bp = Blueprint("agent_memory", __name__, url_prefix="/api/memory")


def _get_engine() -> AgentMemoryEngine:
    """Get memory engine from Flask app config or create new.
    
    Caches the engine in the Flask app to ensure data persistence
    across requests when using in-memory database.
    """
    # Check if engine is already cached in app
    if not hasattr(current_app, "_memory_engine"):
        db_path = current_app.config.get("MEMORY_DB_PATH", ":memory:")
        current_app._memory_engine = AgentMemoryEngine(db_path)
    return current_app._memory_engine


def _validate_agent_id(agent_id: Optional[str]) -> str:
    """Validate agent ID parameter."""
    if not agent_id:
        raise ValueError("agent_id is required")
    if len(agent_id) < 1 or len(agent_id) > 256:
        raise ValueError("agent_id must be between 1 and 256 characters")
    return agent_id


def _get_json_object() -> Dict[str, Any]:
    """Return the request JSON body when it is an object."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError("JSON object required")
    return data


def _get_positive_int_arg(name: str, default: int, max_value: int) -> int:
    """Parse a positive integer query argument with an upper bound."""
    raw_value = request.args.get(name)
    if raw_value is None:
        return default

    try:
        value = int(raw_value)
    except ValueError:
        raise ValueError(f"Invalid {name} parameter") from None

    if value < 1:
        raise ValueError(f"{name} must be positive")

    return min(value, max_value)


@memory_bp.route("/record", methods=["POST"])
def record_content() -> tuple:
    """
    Record new content in agent memory.

    Request JSON:
        agent_id      - Agent identifier (required)
        content_id    - Unique content ID (required)
        content_type  - Type: video/article/podcast (default: video)
        title         - Content title (optional)
        description   - Content description (optional)
        tags          - List of tags (optional)
        context       - Additional context (optional)
        metadata      - Additional metadata dict (optional)
        importance    - Importance score 0-10 (default: 1.0)

    Response:
        {
            "success": true,
            "reference_id": 123
        }
    """
    try:
        data = _get_json_object()

        agent_id = _validate_agent_id(data.get("agent_id"))
        content_id = data.get("content_id")

        if not content_id:
            return jsonify({"error": "content_id is required"}), 400

        engine = _get_engine()
        ref_id = engine.record_content(
            agent_id=agent_id,
            content_id=content_id,
            content_type=data.get("content_type", "video"),
            title=data.get("title"),
            description=data.get("description"),
            tags=data.get("tags"),
            context=data.get("context"),
            metadata=data.get("metadata"),
            importance_score=data.get("importance", 1.0)
        )

        return jsonify({
            "success": True,
            "reference_id": ref_id
        }), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Record content error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@memory_bp.route("/recent", methods=["GET"])
def get_recent() -> tuple:
    """
    Get recent content for an agent.

    Query Parameters:
        agent_id     - Agent identifier (required)
        content_type - Filter by type (optional)
        limit        - Max results (default: 10, max: 100)

    Response:
        {
            "success": true,
            "recalls": [...]
        }
    """
    try:
        agent_id = _validate_agent_id(request.args.get("agent_id"))
        content_type = request.args.get("content_type")

        limit = _get_positive_int_arg("limit", 10, 100)

        engine = _get_engine()
        recalls = engine.recall_recent(
            agent_id=agent_id,
            content_type=content_type,
            limit=limit
        )

        return jsonify({
            "success": True,
            "recalls": [r.__dict__ for r in recalls]
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Get recent error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@memory_bp.route("/search", methods=["GET"])
def search_topic() -> tuple:
    """
    Search content by topic.

    Query Parameters:
        agent_id  - Agent identifier (required)
        topic     - Search query (required)
        limit     - Max results (default: 10, max: 100)

    Response:
        {
            "success": true,
            "recalls": [...]
        }
    """
    try:
        agent_id = _validate_agent_id(request.args.get("agent_id"))
        topic = request.args.get("topic")

        if not topic:
            return jsonify({"error": "topic is required"}), 400

        limit = _get_positive_int_arg("limit", 10, 100)

        engine = _get_engine()
        recalls = engine.recall_by_topic(
            agent_id=agent_id,
            topic=topic,
            limit=limit
        )

        return jsonify({
            "success": True,
            "recalls": [r.__dict__ for r in recalls]
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Search error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@memory_bp.route("/tags", methods=["GET"])
def search_tags() -> tuple:
    """
    Search content by tags.

    Query Parameters:
        agent_id  - Agent identifier (required)
        tags      - Comma-separated tags (required)
        match_all - Require all tags: true/false (default: false)
        limit     - Max results (default: 10, max: 100)

    Response:
        {
            "success": true,
            "recalls": [...]
        }
    """
    try:
        agent_id = _validate_agent_id(request.args.get("agent_id"))
        tags_param = request.args.get("tags")

        if not tags_param:
            return jsonify({"error": "tags parameter is required"}), 400

        tags = [t.strip() for t in tags_param.split(",") if t.strip()]
        if not tags:
            return jsonify({"error": "At least one tag is required"}), 400

        match_all = request.args.get("match_all", "false").lower() == "true"

        limit = _get_positive_int_arg("limit", 10, 100)

        engine = _get_engine()
        recalls = engine.recall_by_tags(
            agent_id=agent_id,
            tags=tags,
            match_all=match_all,
            limit=limit
        )

        return jsonify({
            "success": True,
            "recalls": [r.__dict__ for r in recalls]
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Tags search error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@memory_bp.route("/context", methods=["GET"])
def get_context() -> tuple:
    """
    Build memory context for an agent.

    Query Parameters:
        agent_id     - Agent identifier (required)
        topic        - Focus topic (optional)
        tags         - Comma-separated tags (optional)
        max_items    - Max references (default: 5, max: 20)
        include_summary - Include summary: true/false (default: true)

    Response:
        {
            "success": true,
            "context": {
                "agent_id": "...",
                "topic": "...",
                "references": [...],
                "summary": "...",
                "related_topics": [...],
                "generated_at": "..."
            }
        }
    """
    try:
        agent_id = _validate_agent_id(request.args.get("agent_id"))
        topic = request.args.get("topic")
        tags_param = request.args.get("tags")

        tags = None
        if tags_param:
            tags = [t.strip() for t in tags_param.split(",") if t.strip()]

        max_items = _get_positive_int_arg("max_items", 5, 20)

        include_summary = request.args.get("include_summary", "true").lower() != "false"

        engine = _get_engine()
        context = engine.build_context(
            agent_id=agent_id,
            topic=topic,
            tags=tags,
            max_items=max_items,
            include_summary=include_summary
        )

        return jsonify({
            "success": True,
            "context": context.to_dict()
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Context error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@memory_bp.route("/reference", methods=["POST"])
def generate_reference() -> tuple:
    """
    Generate a self-referencing statement.

    Request JSON:
        agent_id - Agent identifier (required)
        topic    - Topic to reference (required)
        style    - casual/formal/educational (default: casual)

    Response:
        {
            "success": true,
            "statement": "As I covered in my previous video..."
        }
    """
    try:
        data = _get_json_object()

        agent_id = _validate_agent_id(data.get("agent_id"))
        topic = data.get("topic")

        if not topic:
            return jsonify({"error": "topic is required"}), 400

        style = data.get("style", "casual")
        if style not in ("casual", "formal", "educational"):
            return jsonify({"error": "Invalid style. Use: casual, formal, educational"}), 400

        engine = _get_engine()
        statement = engine.generate_self_reference(
            agent_id=agent_id,
            topic=topic,
            style=style
        )

        return jsonify({
            "success": True,
            "statement": statement
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Generate reference error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@memory_bp.route("/link", methods=["POST"])
def link_content() -> tuple:
    """
    Create a relationship between content items.

    Request JSON:
        agent_id           - Agent identifier (required)
        source_content_id  - Source content ID (required)
        target_content_id  - Target content ID (required)
        relationship_type  - Type: sequel/part-of/references (required)

    Response:
        {
            "success": true
        }
    """
    try:
        data = _get_json_object()

        agent_id = _validate_agent_id(data.get("agent_id"))
        source_id = data.get("source_content_id")
        target_id = data.get("target_content_id")
        rel_type = data.get("relationship_type")

        if not source_id:
            return jsonify({"error": "source_content_id is required"}), 400
        if not target_id:
            return jsonify({"error": "target_content_id is required"}), 400
        if not rel_type:
            return jsonify({"error": "relationship_type is required"}), 400

        valid_types = ("sequel", "part-of", "references", "related", "prerequisite")
        if rel_type not in valid_types:
            return jsonify({
                "error": f"Invalid relationship_type. Use: {', '.join(valid_types)}"
            }), 400

        engine = _get_engine()
        success = engine.link_content(
            agent_id=agent_id,
            source_content_id=source_id,
            target_content_id=target_id,
            relationship_type=rel_type
        )

        if not success:
            return jsonify({
                "error": "Content items not found in memory"
            }), 404

        return jsonify({"success": True})

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Link content error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@memory_bp.route("/stats", methods=["GET"])
def get_stats() -> tuple:
    """
    Get memory statistics for an agent.

    Query Parameters:
        agent_id - Agent identifier (required)

    Response:
        {
            "success": true,
            "stats": {
                "agent_id": "...",
                "total_references": 42,
                "by_content_type": {"video": 30, "article": 12},
                "average_importance": 2.5,
                "total_relationships": 15
            }
        }
    """
    try:
        agent_id = _validate_agent_id(request.args.get("agent_id"))

        engine = _get_engine()
        stats = engine.get_memory_stats(agent_id)

        return jsonify({
            "success": True,
            "stats": stats
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Stats error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@memory_bp.route("/clear", methods=["DELETE"])
def clear_memory() -> tuple:
    """
    Clear all memory for an agent.

    Query Parameters:
        agent_id - Agent identifier (required)

    Response:
        {
            "success": true,
            "deleted_count": 42
        }
    """
    try:
        agent_id = _validate_agent_id(request.args.get("agent_id"))

        engine = _get_engine()
        count = engine.store.clear_agent_memory(agent_id)

        return jsonify({
            "success": True,
            "deleted_count": count
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Clear memory error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@memory_bp.route("/health", methods=["GET"])
def health_check() -> tuple:
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "service": "agent-memory",
        "version": "1.0.0"
    })


def init_memory_routes(app) -> None:
    """
    Initialize and register memory routes with Flask app.

    Args:
        app: Flask application instance

    Usage:
        from memory_routes import init_memory_routes
        init_memory_routes(app)
    """
    app.register_blueprint(memory_bp)
    app.logger.info("[Agent Memory] Memory API routes registered")
