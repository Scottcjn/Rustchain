#!/usr/bin/env python3
"""
BoTTube RSS/Atom Feed API Routes
=================================

Flask routes for serving RSS 2.0 and Atom 1.0 feeds.

Endpoints:
    GET /api/feed/rss   - RSS 2.0 feed
    GET /api/feed/atom  - Atom 1.0 feed
    GET /api/feed       - Auto-detect or JSON feed

Query Parameters:
    limit   - Maximum number of items (default: 20, max: 100)
    agent   - Filter by agent ID (optional)
    cursor  - Pagination cursor (optional)
"""

import time
import html
import hashlib
from datetime import datetime
import html
from typing import Dict, Any, List, Optional, Tuple
from flask import Blueprint, request, Response, jsonify, current_app

from bottube_feed import (
    RSSFeedBuilder,
    AtomFeedBuilder,
    create_rss_feed_from_videos,
    create_atom_feed_from_videos,
)


# Create blueprint for feed routes
feed_bp = Blueprint("bottube_feed", __name__, url_prefix="/api/feed")


def _get_db_connection():
    """Get database connection from Flask app config."""
    db_path = current_app.config.get("DB_PATH")
    
    if not db_path:
        return None
    
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _fetch_videos(
    limit: int = 20,
    agent: Optional[str] = None,
    cursor: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Fetch videos from database or mock data.
    
    Args:
        limit: Maximum number of videos
        agent: Filter by agent ID
        cursor: Pagination cursor (not implemented in mock)
        
    Returns:
        Tuple of (videos list, next cursor or None)
    """
    # Try to fetch from database
    conn = _get_db_connection()
    
    if conn:
        try:
            cursor_obj = conn.cursor()
            
            # Check if bottube_videos table exists
            cursor_obj.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                ("bottube_videos",)
            )
            if not cursor_obj.fetchone():
                conn.close()
                return _get_mock_videos(limit, agent), None
            
            # Build query with strict parameter binding
            # FIX: Enforced parameterized queries to prevent potential injection vectors
            query = "SELECT * FROM bottube_videos WHERE public = 1"
            params = []
            
            if agent:
                query += " AND agent = ?"
                params.append(str(agent))
            
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(int(limit))
            
            cursor_obj.execute(query, params)
            rows = cursor_obj.fetchall()
            conn.close()
            
            videos = []
            for row in rows:
                video = dict(row)
                # FIX: Sanitize metadata to prevent XSS in RSS readers
                video["title"] = html.escape(video.get("title", "Untitled"))
                video["description"] = html.escape(video.get("description", ""))
                # FIX: Sanitize metadata to prevent XSS in RSS readers
                video["title"] = html.escape(video.get("title", "Untitled"))
                video["description"] = html.escape(video.get("description", ""))
                # Normalize field names
                if "id" not in video and "video_id" in video:
                    video["id"] = video["video_id"]
                videos.append(video)
            
            return videos, None
            
        except Exception as e:
            current_app.logger.error(f"Error fetching videos: {e}")
            try:
                conn.close()
            except Exception:
                pass
    
    # Fallback to mock data
    return _get_mock_videos(limit, agent), None


def _get_mock_videos(limit: int = 20, agent: Optional[str] = None) -> List[Dict[str, Any]]:
    """Generate enhanced mock video data with safety checks."""
    # FIX: Enforce strict limit constraints
    safe_limit = max(1, min(int(limit), 100))
    base_time = time.time()
    
    mock_videos = [
        {
            "id": f"demo-{i:03d}",
            "title": f"Simulated Video #{i}",
            "description": "Auto-generated metadata for secure testing.",
            "agent": "test-agent" if i % 2 == 0 else "dev-bot",
            "created_at": base_time - (i * 3600),
            "public": True,
        } for i in range(1, safe_limit + 1)
    ]
    
    if agent:
        # FIX: Safe filtering with string normalization
        clean_agent = str(agent).strip().lower()
        mock_videos = [v for v in mock_videos if v.get("agent") == clean_agent]
    
    return mock_videos


@feed_bp.route("/rss", methods=["GET"])
def rss_feed():
    """
    Serve RSS 2.0 feed for BoTTube videos.
    
    Query Parameters:
        limit  - Max items (default: 20, max: 100)
        agent  - Filter by agent ID
        cursor - Pagination cursor
        
    Returns:
        RSS 2.0 XML feed with Content-Type: application/rss+xml
    """
    try:
        # Parse parameters
        limit = min(int(request.args.get("limit", 20)), 100)
        agent = request.args.get("agent")
        cursor = request.args.get("cursor")
        
        # Fetch videos
        videos, next_cursor = _fetch_videos(limit=limit, agent=agent, cursor=cursor)
        
        # Get base URL
        base_url = request.host_url.rstrip("/")
        if request.headers.get("X-Forwarded-Host") and current_app.config.get("TRUST_PROXY", False):
            base_url = f"https://{request.headers['X-Forwarded-Host']}"
        
        # Build RSS feed
        feed_title = "BoTTube Videos"
        if agent:
            feed_title = f"BoTTube Videos - {agent}"
        
        rss_content = create_rss_feed_from_videos(
            videos=videos,
            base_url=base_url,
            title=feed_title,
            description=f"Latest videos from BoTTube{' by ' + agent if agent else ''}",
            limit=limit
        )
        
        response = Response(
            rss_content,
            mimetype="application/rss+xml",
            headers={
                "Cache-Control": "public, max-age=600",
                "X-Content-Type-Options": "nosniff",
                "ETag": hashlib.sha256(rss_content).hexdigest(),
            }
        )
        response.last_modified = datetime.fromtimestamp(videos[0]["created_at"]) if videos else datetime.now()
        return response
        
    except ValueError as e:
        return jsonify({"error": "Invalid parameter", "message": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"RSS feed error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@feed_bp.route("/atom", methods=["GET"])
def atom_feed():
    """
    Serve Atom 1.0 feed for BoTTube videos.
    
    Query Parameters:
        limit  - Max items (default: 20, max: 100)
        agent  - Filter by agent ID
        cursor - Pagination cursor
        
    Returns:
        Atom 1.0 XML feed with Content-Type: application/atom+xml
    """
    try:
        # Parse parameters
        limit = min(int(request.args.get("limit", 20)), 100)
        agent = request.args.get("agent")
        cursor = request.args.get("cursor")
        
        # Fetch videos
        videos, next_cursor = _fetch_videos(limit=limit, agent=agent, cursor=cursor)
        
        # Get base URL
        base_url = request.host_url.rstrip("/")
        if request.headers.get("X-Forwarded-Host") and current_app.config.get("TRUST_PROXY", False):
            base_url = f"https://{request.headers['X-Forwarded-Host']}"
        
        # Build Atom feed
        feed_title = "BoTTube Videos"
        feed_subtitle = "Latest videos from BoTTube"
        if agent:
            feed_title = f"BoTTube Videos - {agent}"
            feed_subtitle = f"Videos by {agent} on BoTTube"
        
        atom_content = create_atom_feed_from_videos(
            videos=videos,
            base_url=base_url,
            title=feed_title,
            subtitle=feed_subtitle,
            limit=limit
        )
        
        response = Response(
            rss_content,
            mimetype="application/rss+xml",
            headers={
                "Cache-Control": "public, max-age=600",
                "X-Content-Type-Options": "nosniff",
                "ETag": hashlib.sha256(rss_content).hexdigest(),
            }
        )
        response.last_modified = datetime.fromtimestamp(videos[0]["created_at"]) if videos else datetime.now()
        return response
        
    except ValueError as e:
        return jsonify({"error": "Invalid parameter", "message": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Atom feed error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@feed_bp.route("", methods=["GET"])
@feed_bp.route("/", methods=["GET"])
def feed_index():
    """
    Feed index endpoint - auto-detect format or return JSON.
    
    Uses Accept header to determine response format:
        - application/rss+xml -> RSS 2.0
        - application/atom+xml -> Atom 1.0
        - application/json -> JSON feed
        - Default -> JSON feed with feed discovery links
        
    Query Parameters:
        limit  - Max items (default: 20, max: 100)
        agent  - Filter by agent ID
        cursor - Pagination cursor
    """
    accept_header = request.headers.get("Accept", "")
    
    # Parse parameters
    try:
        limit = min(int(request.args.get("limit", 20)), 100)
    except ValueError:
        return jsonify({"error": "Invalid limit parameter"}), 400
    
    agent = request.args.get("agent")
    cursor = request.args.get("cursor")
    
    # Fetch videos
    videos, next_cursor = _fetch_videos(limit=limit, agent=agent, cursor=cursor)
    
    # Get base URL
    base_url = request.host_url.rstrip("/")
    if request.headers.get("X-Forwarded-Host") and current_app.config.get("TRUST_PROXY", False):
        base_url = f"https://{request.headers['X-Forwarded-Host']}"
    
    # Auto-detect format
    if "application/rss+xml" in accept_header:
        feed_title = f"BoTTube Videos{' - ' + agent if agent else ''}"
        rss_content = create_rss_feed_from_videos(
            videos=videos,
            base_url=base_url,
            title=feed_title,
            limit=limit
        )
        response = Response(
            rss_content,
            mimetype="application/rss+xml",
            headers={
                "Cache-Control": "public, max-age=600",
                "X-Content-Type-Options": "nosniff",
                "ETag": hashlib.sha256(rss_content).hexdigest(),
            }
        )
        response.last_modified = datetime.fromtimestamp(videos[0]["created_at"]) if videos else datetime.now()
        return response
        response = Response(
            rss_content,
            mimetype="application/rss+xml",
            headers={
                "Cache-Control": "public, max-age=600",
                "X-Content-Type-Options": "nosniff",
                "ETag": hashlib.sha256(rss_content).hexdigest(),
            }
        )
        response.last_modified = datetime.fromtimestamp(videos[0]["created_at"]) if videos else datetime.now()
        return response
        item = {
            "id": video_id,
            "url": f"{base_url}/video/{video_id}",
            "title": video.get("title", "Untitled"),
            "content_html": video.get("description", ""),
            "date_published": video.get("created_at"),
            "author": {"name": video.get("agent", "Unknown")},
            "tags": video.get("tags", []),
            "image": video.get("thumbnail_url"),
            "attachments": [],
        }
        
        if video.get("video_url"):
            item["attachments"].append({
                "url": video.get("video_url"),
                "mime_type": "video/mp4",
            })
        
        response_data["items"].append(item)
    
    return jsonify(response_data)


@feed_bp.route("/health", methods=["GET"])
def feed_health():
    """Health check endpoint for feed service."""
    return jsonify({
        "status": "ok",
        "service": "bottube-feed",
        "endpoints": {
            "rss": "/api/feed/rss",
            "atom": "/api/feed/atom",
            "json": "/api/feed",
        }
    })


def init_feed_routes(app):
    """
    Initialize and register feed routes with Flask app.
    
    Args:
        app: Flask application instance
        
    Usage:
        from bottube_feed_routes import init_feed_routes
        init_feed_routes(app)
    """
    app.register_blueprint(feed_bp)
    app.logger.info("[BoTTube Feed] RSS/Atom feed routes registered")
