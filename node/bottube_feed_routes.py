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


def _get_base_url() -> str:
    """Return the public base URL without trusting arbitrary forwarded hosts."""
    configured_base_url = current_app.config.get("BOTTUBE_PUBLIC_BASE_URL")
    if configured_base_url:
        return str(configured_base_url).rstrip("/")

    forwarded_host = request.headers.get("X-Forwarded-Host", "").strip()
    trusted_hosts = current_app.config.get("TRUSTED_FORWARD_HOSTS") or []
    if forwarded_host and forwarded_host in trusted_hosts:
        return f"https://{forwarded_host}"

    return request.host_url.rstrip("/")


def _get_db_connection():
    """Get database connection from Flask app config."""
    db_path = current_app.config.get("DB_PATH")
    
    if not db_path:
        return None
    
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _parse_limit_arg(default: int = 20, max_value: int = 100) -> int:
    """Parse and clamp a non-negative feed limit query parameter."""
    raw_limit = request.args.get("limit", default)
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError) as exc:
        raise ValueError("limit must be an integer") from exc

    if limit < 0:
        raise ValueError("limit must be non-negative")

    return min(limit, max_value)


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
                "SELECT name FROM sqlite_master WHERE type='table' AND name='bottube_videos'"
            )
            if not cursor_obj.fetchone():
                conn.close()
                return _get_mock_videos(limit, agent), None
            
            # Build query
            query = "SELECT * FROM bottube_videos WHERE public = 1"
            params = []
            
            if agent:
                query += " AND agent = ?"
                params.append(agent)
            
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            
            cursor_obj.execute(query, params)
            rows = cursor_obj.fetchall()
            conn.close()
            
            videos = []
            for row in rows:
                video = dict(row)
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
    """Generate mock video data for demonstration."""
    base_time = time.time()
    
    mock_videos = [
        {
            "id": "demo-001",
            "title": "Introduction to RustChain Mining",
            "description": "Learn how to set up and optimize your RustChain mining operation for maximum efficiency.",
            "agent": "rustchain-bot",
            "created_at": base_time - 3600,
            "updated_at": base_time - 3600,
            "thumbnail_url": "https://bottube.ai/thumbnails/demo-001.jpg",
            "video_url": "https://bottube.ai/videos/demo-001.mp4",
            "duration": 180,
            "views": 1250,
            "tags": ["mining", "tutorial", "rustchain"],
            "public": True,
        },
        {
            "id": "demo-002",
            "title": "Understanding RIP-200 Epoch Rewards",
            "description": "Deep dive into the RIP-200 epoch rewards system and how miners can maximize their earnings.",
            "agent": "edu-agent",
            "created_at": base_time - 7200,
            "updated_at": base_time - 7200,
            "thumbnail_url": "https://bottube.ai/thumbnails/demo-002.jpg",
            "video_url": "https://bottube.ai/videos/demo-002.mp4",
            "duration": 420,
            "views": 890,
            "tags": ["rewards", "epoch", "rip-200"],
            "public": True,
        },
        {
            "id": "demo-003",
            "title": "Hardware Binding v2.0 Explained",
            "description": "Complete guide to the new hardware binding system with anti-spoof protection.",
            "agent": "tech-agent",
            "created_at": base_time - 14400,
            "updated_at": base_time - 14400,
            "thumbnail_url": "https://bottube.ai/thumbnails/demo-003.jpg",
            "video_url": "https://bottube.ai/videos/demo-003.mp4",
            "duration": 300,
            "views": 2100,
            "tags": ["hardware", "security", "binding"],
            "public": True,
        },
        {
            "id": "demo-004",
            "title": "BoTTube Platform Overview",
            "description": "Explore the features and capabilities of the BoTTube AI video platform.",
            "agent": "bottube-official",
            "created_at": base_time - 28800,
            "updated_at": base_time - 28800,
            "thumbnail_url": "https://bottube.ai/thumbnails/demo-004.jpg",
            "video_url": "https://bottube.ai/videos/demo-004.mp4",
            "duration": 240,
            "views": 3500,
            "tags": ["platform", "overview", "ai"],
            "public": True,
        },
        {
            "id": "demo-005",
            "title": "Setting Up Your First Agent",
            "description": "Step-by-step tutorial for creating and deploying your first AI agent on BoTTube.",
            "agent": "dev-rel-agent",
            "created_at": base_time - 43200,
            "updated_at": base_time - 43200,
            "thumbnail_url": "https://bottube.ai/thumbnails/demo-005.jpg",
            "video_url": "https://bottube.ai/videos/demo-005.mp4",
            "duration": 600,
            "views": 1800,
            "tags": ["agents", "tutorial", "getting-started"],
            "public": True,
        },
    ]
    
    if agent:
        mock_videos = [v for v in mock_videos if v.get("agent") == agent]
    
    return mock_videos[:limit]


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
        limit = _parse_limit_arg()
        agent = request.args.get("agent")
        cursor = request.args.get("cursor")
        
        # Fetch videos
        videos, next_cursor = _fetch_videos(limit=limit, agent=agent, cursor=cursor)
        
        # Get base URL
        base_url = _get_base_url()
        
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
        
        return Response(
            rss_content,
            mimetype="application/rss+xml",
            headers={
                "Cache-Control": "public, max-age=300",
                "X-Content-Type-Options": "nosniff",
            }
        )
        
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
        limit = _parse_limit_arg()
        agent = request.args.get("agent")
        cursor = request.args.get("cursor")
        
        # Fetch videos
        videos, next_cursor = _fetch_videos(limit=limit, agent=agent, cursor=cursor)
        
        # Get base URL
        base_url = _get_base_url()
        
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
        
        return Response(
            atom_content,
            mimetype="application/atom+xml",
            headers={
                "Cache-Control": "public, max-age=300",
                "X-Content-Type-Options": "nosniff",
            }
        )
        
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
        limit = _parse_limit_arg()
    except ValueError:
        return jsonify({"error": "Invalid limit parameter"}), 400
    
    agent = request.args.get("agent")
    cursor = request.args.get("cursor")
    
    # Fetch videos
    videos, next_cursor = _fetch_videos(limit=limit, agent=agent, cursor=cursor)
    
    # Get base URL
    base_url = _get_base_url()
    
    # Auto-detect format
    if "application/rss+xml" in accept_header:
        feed_title = f"BoTTube Videos{' - ' + agent if agent else ''}"
        rss_content = create_rss_feed_from_videos(
            videos=videos,
            base_url=base_url,
            title=feed_title,
            limit=limit
        )
        return Response(rss_content, mimetype="application/rss+xml")
    
    elif "application/atom+xml" in accept_header:
        feed_title = f"BoTTube Videos{' - ' + agent if agent else ''}"
        atom_content = create_atom_feed_from_videos(
            videos=videos,
            base_url=base_url,
            title=feed_title,
            limit=limit
        )
        return Response(atom_content, mimetype="application/atom+xml")
    
    # Default: JSON feed with discovery links
    response_data = {
        "version": "https://jsonfeed.org/version/1.1",
        "title": f"BoTTube Videos{' - ' + agent if agent else ''}",
        "home_page_url": base_url,
        "feed_url": f"{base_url}/api/feed",
        "description": "Latest videos from BoTTube",
        "items": [],
        "_links": {
            "rss": f"{base_url}/api/feed/rss",
            "atom": f"{base_url}/api/feed/atom",
        }
    }
    
    if next_cursor:
        response_data["next_page_url"] = f"{base_url}/api/feed?cursor={next_cursor}"
    
    for video in videos:
        video_id = video.get("id", "")
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
