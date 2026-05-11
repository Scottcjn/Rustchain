# SPDX-License-Identifier: MIT
"""
Flask API for BoTTube Glitch System

RESTful endpoints for managing agent glitches, viewing history,
and configuring the glitch engine.
"""

from flask import Blueprint, jsonify, request, Response
from typing import Dict, Any
import json
import time

try:
    from .glitch_engine import GlitchEngine, GlitchConfig
    from .personality import PERSONALITY_TEMPLATES
except ImportError:
    from glitch_engine import GlitchEngine, GlitchConfig
    from personality import PERSONALITY_TEMPLATES


# Create blueprint
glitch_bp = Blueprint("glitch", __name__, url_prefix="/api/glitch")

# Global engine instance (initialize in app)
_engine: GlitchEngine = None


def init_engine(config: GlitchConfig = None) -> GlitchEngine:
    """Initialize the glitch engine"""
    global _engine
    _engine = GlitchEngine(config)
    return _engine


def get_json_object():
    """Return a JSON object body or a Flask error response."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, (jsonify({"error": "JSON object required"}), 400)
    return data, None


def parse_limit_arg(default: int = 50, max_value: int = 200):
    raw_value = request.args.get("limit")
    if raw_value is None:
        return default, None

    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return None, "limit_must_be_integer"

    if value < 1:
        return None, "limit_must_be_positive"

    return min(value, max_value), None


def get_engine() -> GlitchEngine:
    """Get the engine instance"""
    global _engine
    if _engine is None:
        _engine = GlitchEngine()
    return _engine


# ─── Core Endpoints ─────────────────────────────────────────────────────────── #


@glitch_bp.route("/process", methods=["POST"])
def process_message() -> Response:
    """
    Process a message through the glitch system.
    
    POST /api/glitch/process
    Content-Type: application/json
    
    {
        "agent_id": "bcn_sophia_elya",
        "message": "Hello, how can I help you?",
        "context": {
            "user_id": "user123",
            "conversation_id": "conv456"
        }
    }
    
    Returns:
    {
        "original": "Hello, how can I help you?",
        "processed": "Hello, how can I help you? [SIMULATION FRAME 0x00001A2B]",
        "glitch_occurred": true,
        "glitch": {
            "glitch_id": "glitch_abc123",
            "type": "FOURTH_WALL",
            "severity": "minor",
            "duration_ms": 1500
        }
    }
    """
    engine = get_engine()
    
    data, error = get_json_object()
    if error:
        return error
    
    agent_id = data.get("agent_id", "")
    message = data.get("message", "")
    context = data.get("context", {})
    
    if not agent_id or not message:
        return jsonify({"error": "agent_id and message are required"}), 400
    
    processed, glitch_event = engine.process_message(agent_id, message, context)
    
    result = {
        "original": message,
        "processed": processed,
        "glitch_occurred": glitch_event is not None,
    }
    
    if glitch_event:
        result["glitch"] = {
            "glitch_id": glitch_event.glitch_id,
            "type": glitch_event.glitch_type.name,
            "severity": glitch_event.severity.value,
            "duration_ms": glitch_event.duration_ms,
            "timestamp": glitch_event.timestamp,
        }
    
    return jsonify(result)


@glitch_bp.route("/agents/<agent_id>/register", methods=["POST"])
def register_agent(agent_id: str) -> Response:
    """
    Register an agent with a personality.
    
    POST /api/glitch/agents/<agent_id>/register
    Content-Type: application/json
    
    {
        "template": "sophia_elya",  // Optional: use predefined template
        "personality": {             // Optional: custom personality
            "openness": 0.8,
            "extraversion": 0.9,
            ...
        }
    }
    """
    engine = get_engine()
    
    data, error = get_json_object()
    if error:
        return error
    template = data.get("template")
    personality_data = data.get("personality")
    
    from .personality import PersonalityProfile
    
    personality = None
    if personality_data:
        personality = PersonalityProfile.from_dict(personality_data)
    
    persona = engine.register_agent(agent_id, personality, template)
    
    return jsonify({
        "success": True,
        "agent_id": agent_id,
        "persona": persona.to_dict(),
    })


@glitch_bp.route("/agents/<agent_id>", methods=["GET"])
def get_agent_status(agent_id: str) -> Response:
    """
    Get agent status and statistics.
    
    GET /api/glitch/agents/<agent_id>
    
    Returns:
    {
        "agent_id": "bcn_sophia_elya",
        "registered": true,
        "persona": {...},
        "stats": {
            "total_glitches": 15,
            "average_duration_ms": 2340.5,
            "most_common_glitch": "SPEECH_LOOP"
        }
    }
    """
    engine = get_engine()
    
    persona = engine.get_persona(agent_id)
    stats = engine.get_agent_stats(agent_id)
    
    if not persona and stats["total_glitches"] == 0:
        return jsonify({
            "agent_id": agent_id,
            "registered": False,
            "stats": stats,
        })
    
    return jsonify({
        "agent_id": agent_id,
        "registered": persona is not None,
        "persona": persona.to_dict() if persona else None,
        "stats": stats,
    })


@glitch_bp.route("/agents", methods=["GET"])
def list_agents() -> Response:
    """
    List all registered agents.
    
    GET /api/glitch/agents
    
    Returns:
    {
        "agents": [
            {"agent_id": "bcn_sophia_elya", "template": "sophia_elya"},
            ...
        ],
        "total": 5
    }
    """
    engine = get_engine()
    
    agents = [
        {
            "agent_id": agent_id,
            "template": persona.profile.profile_id,
            "glitch_count": persona.glitch_count,
        }
        for agent_id, persona in engine._personas.items()
    ]
    
    return jsonify({
        "agents": agents,
        "total": len(agents),
    })


# ─── History Endpoints ──────────────────────────────────────────────────────── #


@glitch_bp.route("/history", methods=["GET"])
def get_history() -> Response:
    """
    Get glitch history.
    
    GET /api/glitch/history?agent_id=bcn_sophia_elya&limit=50
    
    Returns:
    {
        "history": [...],
        "total": 150
    }
    """
    engine = get_engine()
    
    agent_id = request.args.get("agent_id")
    limit, error = parse_limit_arg(50, 200)
    if error:
        return jsonify({"error": error}), 400
    
    history = engine.get_glitch_history(agent_id, limit)
    
    return jsonify({
        "history": [e.to_dict() for e in history],
        "total": len(history),
    })


@glitch_bp.route("/history/<glitch_id>", methods=["GET"])
def get_glitch_detail(glitch_id: str) -> Response:
    """
    Get details of a specific glitch event.
    
    GET /api/glitch/history/<glitch_id>
    """
    engine = get_engine()
    
    history = engine.get_glitch_history(limit=1000)
    
    for event in history:
        if event.glitch_id == glitch_id:
            return jsonify(event.to_dict())
    
    return jsonify({"error": "Glitch not found"}), 404


@glitch_bp.route("/history/clear", methods=["POST"])
def clear_history() -> Response:
    """
    Clear glitch history.
    
    POST /api/glitch/history/clear
    """
    engine = get_engine()
    
    engine._glitch_history.clear()
    
    return jsonify({"success": True, "message": "History cleared"})


# ─── Statistics Endpoints ───────────────────────────────────────────────────── #


@glitch_bp.route("/stats", methods=["GET"])
def get_statistics() -> Response:
    """
    Get global glitch statistics.
    
    GET /api/glitch/stats
    
    Returns:
    {
        "total_glitches": 523,
        "glitches_by_type": {...},
        "glitches_by_agent": {...},
        "glitches_by_severity": {...},
        "agents_tracked": 12
    }
    """
    engine = get_engine()
    return jsonify(engine.get_statistics())


@glitch_bp.route("/stats/summary", methods=["GET"])
def get_stats_summary() -> Response:
    """
    Get summarized statistics.
    
    GET /api/glitch/stats/summary
    """
    engine = get_engine()
    stats = engine.get_statistics()
    
    # Calculate summary
    total = stats["total_glitches"]
    
    # Top glitch types
    type_summary = sorted(
        stats["glitches_by_type"].items(),
        key=lambda x: x[1],
        reverse=True
    )[:5]
    
    # Top agents
    agent_summary = sorted(
        stats["glitches_by_agent"].items(),
        key=lambda x: x[1],
        reverse=True
    )[:5]
    
    return jsonify({
        "total_glitches": total,
        "top_glitch_types": dict(type_summary),
        "top_agents": dict(agent_summary),
        "agents_tracked": stats["agents_tracked"],
    })


# ─── Configuration Endpoints ────────────────────────────────────────────────── #


@glitch_bp.route("/config", methods=["GET"])
def get_config() -> Response:
    """
    Get current configuration.
    
    GET /api/glitch/config
    """
    engine = get_engine()
    return jsonify(engine.export_config())


@glitch_bp.route("/config", methods=["PUT"])
def update_config() -> Response:
    """
    Update configuration.
    
    PUT /api/glitch/config
    Content-Type: application/json
    
    {
        "enabled": true,
        "base_probability": 0.2
    }
    """
    engine = get_engine()
    
    data, error = get_json_object()
    if error:
        return error
    
    if "enabled" in data:
        if data["enabled"]:
            engine.enable()
        else:
            engine.disable()
    
    if "base_probability" in data:
        engine.set_probability(data["base_probability"])
    
    return jsonify({
        "success": True,
        "config": engine.export_config(),
    })


@glitch_bp.route("/config/reset", methods=["POST"])
def reset_config() -> Response:
    """
    Reset configuration to defaults.
    
    POST /api/glitch/config/reset
    """
    engine = get_engine()
    
    engine.config.enabled = True
    engine.config.base_probability = 0.15
    engine.config.min_glitch_interval = 5.0
    engine.config.max_glitch_interval = 60.0
    
    return jsonify({
        "success": True,
        "message": "Configuration reset to defaults",
    })


# ─── Template Endpoints ─────────────────────────────────────────────────────── #


@glitch_bp.route("/templates", methods=["GET"])
def list_templates() -> Response:
    """
    List available personality templates.
    
    GET /api/glitch/templates
    
    Returns:
    {
        "templates": [
            {
                "id": "sophia_elya",
                "agent_id": "bcn_sophia_elya",
                "description": "Warm, curious AI with artistic inclinations"
            },
            ...
        ]
    }
    """
    templates = [
        {
            "id": template_id,
            "agent_id": profile.agent_id,
            "description": profile.description,
            "communication_style": profile.communication_style.value,
            "emotional_range": profile.emotional_range.value,
        }
        for template_id, profile in PERSONALITY_TEMPLATES.items()
    ]
    
    return jsonify({"templates": templates})


@glitch_bp.route("/templates/<template_id>", methods=["GET"])
def get_template(template_id: str) -> Response:
    """
    Get details of a personality template.
    
    GET /api/glitch/templates/<template_id>
    """
    if template_id not in PERSONALITY_TEMPLATES:
        return jsonify({"error": "Template not found"}), 404
    
    profile = PERSONALITY_TEMPLATES[template_id]
    
    return jsonify(profile.to_dict())


# ─── Control Endpoints ──────────────────────────────────────────────────────── #


@glitch_bp.route("/enable", methods=["POST"])
def enable_glitches() -> Response:
    """
    Enable glitch system.
    
    POST /api/glitch/enable
    """
    engine = get_engine()
    engine.enable()
    
    return jsonify({"success": True, "enabled": True})


@glitch_bp.route("/disable", methods=["POST"])
def disable_glitches() -> Response:
    """
    Disable glitch system.
    
    POST /api/glitch/disable
    """
    engine = get_engine()
    engine.disable()
    
    return jsonify({"success": True, "enabled": False})


@glitch_bp.route("/trigger", methods=["POST"])
def trigger_glitch() -> Response:
    """
    Manually trigger a glitch for testing.
    
    POST /api/glitch/trigger
    Content-Type: application/json
    
    {
        "agent_id": "bcn_sophia_elya",
        "message": "Test message"
    }
    """
    engine = get_engine()
    
    data, error = get_json_object()
    if error:
        return error
    agent_id = data.get("agent_id", "test_agent")
    message = data.get("message", "Test message for glitch")
    
    # Auto-register if needed
    if not engine.get_persona(agent_id):
        engine.register_agent(agent_id)
    
    processed, glitch_event = engine.process_message(agent_id, message)
    
    if glitch_event:
        return jsonify({
            "success": True,
            "glitch": glitch_event.to_dict(),
            "processed": processed,
        })
    
    return jsonify({
        "success": True,
        "glitch": None,
        "processed": processed,
        "message": "No glitch triggered (random chance)",
    })


# ─── Health Check ───────────────────────────────────────────────────────────── #


@glitch_bp.route("/health", methods=["GET"])
def health_check() -> Response:
    """
    Health check endpoint.
    
    GET /api/glitch/health
    
    Returns:
    {
        "status": "healthy",
        "engine_initialized": true,
        "agents_count": 5,
        "total_glitches": 523
    }
    """
    engine = get_engine()
    stats = engine.get_statistics()
    
    return jsonify({
        "status": "healthy",
        "engine_initialized": True,
        "agents_count": stats["agents_tracked"],
        "total_glitches": stats["total_glitches"],
    })
