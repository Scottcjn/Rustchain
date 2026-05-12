#!/usr/bin/env python3
"""
BoTTube Embeddable Player Widget
=================================

Provides embed endpoints and oEmbed support for embedding BoTTube videos
on external websites.

Endpoints:
    GET /embed/<video_id>     - Minimal embeddable player page
    GET /oembed               - oEmbed endpoint for auto-discovery
    GET /watch/<video_id>     - Full watch page with Share > Embed UI

Features:
    - Responsive HTML5 video player
    - BoTTube branding with link back to full page
    - oEmbed discovery for Discord, Slack, WordPress
    - Embed code generator with size presets (560x315, 640x360, 854x480)
"""

import hashlib
import html as html_lib
import json
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
from flask import Blueprint, request, Response, jsonify, render_template_string


# Create blueprint for embed routes
embed_bp = Blueprint("bottube_embed", __name__, url_prefix="/")


# ============================================================================
# HTML Templates
# ============================================================================

EMBED_PLAYER_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ video_title }} - BoTTube</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        html, body {
            height: 100%;
            width: 100%;
            background: #000;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
        }
        .player-container {
            position: relative;
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #000;
        }
        .video-wrapper {
            position: relative;
            width: 100%;
            max-width: 100%;
            height: 100%;
            max-height: 100%;
        }
        video {
            width: 100%;
            height: 100%;
            max-height: 100vh;
            object-fit: contain;
        }
        .branding {
            position: absolute;
            top: 10px;
            right: 10px;
            display: flex;
            align-items: center;
            gap: 8px;
            background: rgba(0, 0, 0, 0.7);
            padding: 6px 12px;
            border-radius: 4px;
            z-index: 10;
        }
        .branding a {
            color: #fff;
            text-decoration: none;
            font-size: 12px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .branding a:hover {
            text-decoration: underline;
        }
        .branding-logo {
            width: 20px;
            height: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 4px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            font-weight: bold;
            color: #fff;
        }
        .error-container {
            text-align: center;
            padding: 40px;
            color: #fff;
        }
        .error-container h1 {
            font-size: 24px;
            margin-bottom: 10px;
        }
        .error-container p {
            color: #aaa;
        }
    </style>
</head>
<body>
    <div class="player-container">
        <div class="video-wrapper">
            <video controls autoplay{% if auto_play %} muted{% endif %} preload="metadata" poster="{{ thumbnail_url }}">
                <source src="{{ video_url }}" type="video/mp4">
                Your browser does not support the video tag.
            </video>
        </div>
        <div class="branding">
            <a href="{{ full_page_url }}" target="_blank" rel="noopener">
                <div class="branding-logo">B</div>
                <span>BoTTube</span>
            </a>
        </div>
    </div>
</body>
</html>
"""

WATCH_PAGE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ video_title }} - BoTTube</title>
    <link rel="alternate" type="application/json+oembed" href="{{ oembed_url }}" />
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #0f0f0f;
            color: #fff;
            min-height: 100vh;
        }
        .header {
            background: #202020;
            padding: 12px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .header-logo {
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 20px;
            font-weight: bold;
        }
        .logo-icon {
            width: 32px;
            height: 32px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 6px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
        }
        .main-container {
            max-width: 1280px;
            margin: 0 auto;
            padding: 24px;
        }
        .video-section {
            display: grid;
            grid-template-columns: 1fr 360px;
            gap: 24px;
        }
        @media (max-width: 1024px) {
            .video-section {
                grid-template-columns: 1fr;
            }
        }
        .player-container {
            background: #000;
            border-radius: 12px;
            overflow: hidden;
            aspect-ratio: 16 / 9;
        }
        video {
            width: 100%;
            height: 100%;
            object-fit: contain;
        }
        .video-info {
            padding: 20px 0;
        }
        .video-title {
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 12px;
        }
        .video-meta {
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 12px;
        }
        .video-stats {
            color: #aaa;
            font-size: 14px;
        }
        .action-buttons {
            display: flex;
            gap: 12px;
        }
        .btn {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 10px 20px;
            border: none;
            border-radius: 20px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.2s;
        }
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #fff;
        }
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }
        .btn-secondary {
            background: #303030;
            color: #fff;
        }
        .btn-secondary:hover {
            background: #404040;
        }
        .video-description {
            background: #202020;
            border-radius: 12px;
            padding: 20px;
            margin-top: 16px;
            line-height: 1.6;
        }
        .sidebar {
            display: flex;
            flex-direction: column;
            gap: 16px;
        }
        .related-video {
            display: flex;
            gap: 12px;
            background: #202020;
            border-radius: 8px;
            overflow: hidden;
            cursor: pointer;
            transition: background 0.2s;
        }
        .related-video:hover {
            background: #303030;
        }
        .related-thumbnail {
            width: 168px;
            height: 94px;
            background: #404040;
            flex-shrink: 0;
        }
        .related-info {
            padding: 10px;
            flex: 1;
        }
        .related-title {
            font-size: 14px;
            font-weight: 500;
            margin-bottom: 4px;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }
        .related-agent {
            font-size: 12px;
            color: #aaa;
        }
        /* Share Modal */
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.8);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }
        .modal-overlay.active {
            display: flex;
        }
        .modal {
            background: #202020;
            border-radius: 12px;
            width: 90%;
            max-width: 500px;
            overflow: hidden;
        }
        .modal-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 16px 20px;
            border-bottom: 1px solid #303030;
        }
        .modal-title {
            font-size: 18px;
            font-weight: 600;
        }
        .modal-close {
            background: none;
            border: none;
            color: #fff;
            font-size: 24px;
            cursor: pointer;
            padding: 4px;
            line-height: 1;
        }
        .modal-close:hover {
            color: #aaa;
        }
        .modal-tabs {
            display: flex;
            border-bottom: 1px solid #303030;
        }
        .tab {
            flex: 1;
            padding: 14px 20px;
            background: none;
            border: none;
            color: #aaa;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            border-bottom: 2px solid transparent;
            transition: all 0.2s;
        }
        .tab:hover {
            color: #fff;
            background: #2a2a2a;
        }
        .tab.active {
            color: #667eea;
            border-bottom-color: #667eea;
        }
        .modal-content {
            padding: 20px;
        }
        .tab-content {
            display: none;
        }
        .tab-content.active {
            display: block;
        }
        .share-option {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px;
            border-radius: 8px;
            cursor: pointer;
            transition: background 0.2s;
        }
        .share-option:hover {
            background: #303030;
        }
        .share-icon {
            width: 40px;
            height: 40px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
        }
        .share-icon.copy {
            background: #667eea;
        }
        .share-icon.twitter {
            background: #1da1f2;
        }
        .share-icon.facebook {
            background: #4267b2;
        }
        .embed-options {
            display: flex;
            flex-direction: column;
            gap: 16px;
        }
        .size-selector {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }
        .size-btn {
            padding: 8px 16px;
            background: #303030;
            border: 2px solid transparent;
            border-radius: 6px;
            color: #fff;
            cursor: pointer;
            font-size: 13px;
            transition: all 0.2s;
        }
        .size-btn:hover {
            background: #404040;
        }
        .size-btn.active {
            border-color: #667eea;
            background: rgba(102, 126, 234, 0.1);
        }
        .embed-code-container {
            position: relative;
        }
        .embed-code {
            width: 100%;
            padding: 12px;
            background: #101010;
            border: 1px solid #303030;
            border-radius: 8px;
            color: #0f0;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            resize: none;
        }
        .embed-code:focus {
            outline: none;
            border-color: #667eea;
        }
        .copy-btn {
            position: absolute;
            top: 8px;
            right: 8px;
            padding: 6px 12px;
            background: #667eea;
            border: none;
            border-radius: 4px;
            color: #fff;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s;
        }
        .copy-btn:hover {
            background: #5a6fd6;
        }
        .toast {
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%) translateY(100px);
            background: #303030;
            color: #fff;
            padding: 12px 24px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
            transition: transform 0.3s;
            z-index: 2000;
        }
        .toast.show {
            transform: translateX(-50%) translateY(0);
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-logo">
            <div class="logo-icon">B</div>
            <span>BoTTube</span>
        </div>
    </div>

    <div class="main-container">
        <div class="video-section">
            <div class="main-content">
                <div class="player-container">
                    <video controls autoplay preload="metadata" poster="{{ thumbnail_url }}">
                        <source src="{{ video_url }}" type="video/mp4">
                        Your browser does not support the video tag.
                    </video>
                </div>

                <div class="video-info">
                    <h1 class="video-title">{{ video_title }}</h1>
                    <div class="video-meta">
                        <div class="video-stats">
                            {{ views }} views • {{ publish_date }}
                        </div>
                        <div class="action-buttons">
                            <button class="btn btn-secondary" onclick="openShareModal()">
                                <span>📤</span>
                                <span>Share</span>
                            </button>
                            <button class="btn btn-primary">
                                <span>👍</span>
                                <span>Like</span>
                            </button>
                        </div>
                    </div>
                </div>

                <div class="video-description">
                    <p>{{ video_description }}</p>
                </div>
            </div>

            <div class="sidebar">
                <h3>Related Videos</h3>
                {% for related in related_videos %}
                <div class="related-video">
                    <div class="related-thumbnail"></div>
                    <div class="related-info">
                        <div class="related-title">{{ related.title }}</div>
                        <div class="related-agent">{{ related.agent }}</div>
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
    </div>

    <!-- Share Modal -->
    <div class="modal-overlay" id="shareModal">
        <div class="modal">
            <div class="modal-header">
                <h2 class="modal-title">Share</h2>
                <button class="modal-close" onclick="closeShareModal()">&times;</button>
            </div>
            <div class="modal-tabs">
                <button class="tab active" onclick="switchTab('share')">Share Link</button>
                <button class="tab" onclick="switchTab('embed')">Embed</button>
            </div>
            <div class="modal-content">
                <div class="tab-content active" id="share-tab">
                    <div class="share-option" onclick="copyLink()">
                        <div class="share-icon copy">📋</div>
                        <div>
                            <div style="font-weight: 500;">Copy Link</div>
                            <div style="color: #aaa; font-size: 13px;">Copy video URL to clipboard</div>
                        </div>
                    </div>
                    <div class="share-option" onclick="shareToTwitter()">
                        <div class="share-icon twitter">🐦</div>
                        <div>
                            <div style="font-weight: 500;">Share to Twitter</div>
                            <div style="color: #aaa; font-size: 13px;">Share this video with your followers</div>
                        </div>
                    </div>
                    <div class="share-option" onclick="shareToFacebook()">
                        <div class="share-icon facebook">📘</div>
                        <div>
                            <div style="font-weight: 500;">Share to Facebook</div>
                            <div style="color: #aaa; font-size: 13px;">Share this video on your timeline</div>
                        </div>
                    </div>
                </div>
                <div class="tab-content" id="embed-tab">
                    <div class="embed-options">
                        <div>
                            <div style="margin-bottom: 8px; font-weight: 500;">Size</div>
                            <div class="size-selector">
                                <button class="size-btn" data-width="560" data-height="315" onclick="selectSize(this)">560×315</button>
                                <button class="size-btn" data-width="640" data-height="360" onclick="selectSize(this)">640×360</button>
                                <button class="size-btn active" data-width="854" data-height="480" onclick="selectSize(this)">854×480</button>
                            </div>
                        </div>
                        <div class="embed-code-container">
                            <textarea class="embed-code" id="embedCode" rows="3" readonly></textarea>
                            <button class="copy-btn" onclick="copyEmbedCode()">Copy</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div class="toast" id="toast"></div>

    <script>
        const videoId = "{{ video_id }}";
        const baseUrl = "{{ base_url }}";
        let selectedWidth = 854;
        let selectedHeight = 480;

        function openShareModal() {
            document.getElementById('shareModal').classList.add('active');
            updateEmbedCode();
        }

        function closeShareModal() {
            document.getElementById('shareModal').classList.remove('active');
        }

        function switchTab(tab) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            
            event.target.classList.add('active');
            document.getElementById(tab + '-tab').classList.add('active');
        }

        function selectSize(btn) {
            document.querySelectorAll('.size-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            selectedWidth = parseInt(btn.dataset.width);
            selectedHeight = parseInt(btn.dataset.height);
            updateEmbedCode();
        }

        function updateEmbedCode() {
            const embedUrl = baseUrl + '/embed/' + videoId;
            const iframeCode = '<iframe width="' + selectedWidth + '" height="' + selectedHeight + '" src="' + embedUrl + '" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>';
            document.getElementById('embedCode').value = iframeCode;
        }

        function copyLink() {
            const url = baseUrl + '/watch/' + videoId;
            navigator.clipboard.writeText(url).then(() => {
                showToast('Link copied to clipboard!');
                closeShareModal();
            });
        }

        function copyEmbedCode() {
            const embedCode = document.getElementById('embedCode').value;
            navigator.clipboard.writeText(embedCode).then(() => {
                showToast('Embed code copied!');
            });
        }

        function shareToTwitter() {
            const url = encodeURIComponent(baseUrl + '/watch/' + videoId);
            const text = encodeURIComponent('Check out this video on BoTTube!');
            window.open('https://twitter.com/intent/tweet?url=' + url + '&text=' + text, '_blank');
            closeShareModal();
        }

        function shareToFacebook() {
            const url = encodeURIComponent(baseUrl + '/watch/' + videoId);
            window.open('https://www.facebook.com/sharer/sharer.php?u=' + url, '_blank');
            closeShareModal();
        }

        function showToast(message) {
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.classList.add('show');
            setTimeout(() => toast.classList.remove('show'), 2000);
        }

        // Close modal on overlay click
        document.getElementById('shareModal').addEventListener('click', function(e) {
            if (e.target === this) {
                closeShareModal();
            }
        });

        // Initialize embed code on load
        updateEmbedCode();
    </script>
</body>
</html>
"""


# ============================================================================
# Helper Functions
# ============================================================================

def _get_mock_video(video_id: str) -> Optional[Dict[str, Any]]:
    """Get mock video data for demonstration."""
    base_time = time.time()
    
    mock_videos = {
        "demo-001": {
            "id": "demo-001",
            "title": "Introduction to RustChain Mining",
            "description": "Learn how to set up and optimize your RustChain mining operation for maximum efficiency.",
            "agent": "rustchain-bot",
            "created_at": base_time - 3600,
            "thumbnail_url": "https://bottube.ai/thumbnails/demo-001.jpg",
            "video_url": "https://bottube.ai/videos/demo-001.mp4",
            "duration": 180,
            "views": 1250,
            "tags": ["mining", "tutorial", "rustchain"],
            "public": True,
        },
        "demo-002": {
            "id": "demo-002",
            "title": "Understanding RIP-200 Epoch Rewards",
            "description": "Deep dive into the RIP-200 epoch rewards system and how miners can maximize their earnings.",
            "agent": "edu-agent",
            "created_at": base_time - 7200,
            "thumbnail_url": "https://bottube.ai/thumbnails/demo-002.jpg",
            "video_url": "https://bottube.ai/videos/demo-002.mp4",
            "duration": 420,
            "views": 890,
            "tags": ["rewards", "epoch", "rip-200"],
            "public": True,
        },
        "demo-003": {
            "id": "demo-003",
            "title": "Hardware Binding v2.0 Explained",
            "description": "Complete guide to the new hardware binding system with anti-spoof protection.",
            "agent": "tech-agent",
            "created_at": base_time - 14400,
            "thumbnail_url": "https://bottube.ai/thumbnails/demo-003.jpg",
            "video_url": "https://bottube.ai/videos/demo-003.mp4",
            "duration": 300,
            "views": 2100,
            "tags": ["hardware", "security", "binding"],
            "public": True,
        },
    }
    
    return mock_videos.get(video_id)


def _get_related_videos(video_id: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Get related videos (excluding current video)."""
    all_videos = [
        {
            "id": "demo-001",
            "title": "Introduction to RustChain Mining",
            "agent": "rustchain-bot",
        },
        {
            "id": "demo-002",
            "title": "Understanding RIP-200 Epoch Rewards",
            "agent": "edu-agent",
        },
        {
            "id": "demo-003",
            "title": "Hardware Binding v2.0 Explained",
            "agent": "tech-agent",
        },
        {
            "id": "demo-004",
            "title": "BoTTube Platform Overview",
            "agent": "bottube-official",
        },
        {
            "id": "demo-005",
            "title": "Setting Up Your First Agent",
            "agent": "dev-rel-agent",
        },
    ]
    
    related = [v for v in all_videos if v["id"] != video_id]
    return related[:limit]


def _get_base_url() -> str:
    """Get the base URL from request."""
    base_url = request.host_url.rstrip("/")
    if request.headers.get("X-Forwarded-Host"):
        base_url = f"https://{request.headers['X-Forwarded-Host']}"
    return base_url


def _extract_oembed_video_id(url: str) -> Optional[str]:
    """Return the BoTTube video id from a trusted watch/embed URL."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    host = parsed.hostname or ""
    current_host = urlparse(_get_base_url()).hostname or ""
    allowed_hosts = {"bottube.ai", "www.bottube.ai", current_host}
    if host.lower() not in {allowed.lower() for allowed in allowed_hosts if allowed}:
        return None

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2 or parts[0] not in {"watch", "embed"}:
        return None
    return parts[1]


# ============================================================================
# Routes
# ============================================================================

@embed_bp.route("/embed/<video_id>", methods=["GET"])
def embed_player(video_id: str):
    """
    Embeddable player page for external sites.

    Returns a minimal HTML page with just the video player and branding.
    Designed to be embedded in an iframe on external websites.

    Args:
        video_id: The video identifier

    Returns:
        HTML page with embedded video player
    """
    # Get video data
    video = _get_mock_video(video_id)

    if not video:
        error_html = """
            <html><body style="background:#000;color:#fff;display:flex;align-items:center;justify-content:center;height:100vh;font-family:sans-serif;">
                <div class="error-container" style="text-align:center;">
                    <h1>Video Not Found</h1>
                    <p>The requested video could not be found.</p>
                </div>
            </body></html>
        """
        return Response(error_html, status=404, mimetype="text/html")

    base_url = _get_base_url()
    full_page_url = f"{base_url}/watch/{video_id}"

    return render_template_string(
        EMBED_PLAYER_TEMPLATE,
        video_title=video.get("title", "Video"),
        video_url=video.get("video_url", ""),
        thumbnail_url=video.get("thumbnail_url", ""),
        full_page_url=full_page_url,
        auto_play=True,
    )


@embed_bp.route("/oembed", methods=["GET"])
def oembed():
    """
    oEmbed endpoint for auto-discovery.
    
    Enables platforms like Discord, Slack, and WordPress to automatically
    embed BoTTube videos when a URL is shared.
    
    Query Parameters:
        url     - The BoTTube video URL (required)
        format  - Response format (json only)
        maxwidth - Maximum width (optional)
        maxheight - Maximum height (optional)
        
    Returns:
        JSON oEmbed response
    """
    url = request.args.get("url", "")
    format_param = request.args.get("format", "json")
    maxwidth = request.args.get("maxwidth", 854)
    maxheight = request.args.get("maxheight", 480)
    
    # Validate format
    if format_param != "json":
        return jsonify({
            "error": "Unsupported format. Only JSON is supported."
        }), 400
    
    # Extract video ID from a trusted BoTTube URL
    video_id = _extract_oembed_video_id(url)
    
    if not video_id:
        return jsonify({
            "error": "Invalid URL. Must be a BoTTube video URL."
        }), 400
    
    # Get video data
    video = _get_mock_video(video_id)
    
    if not video:
        return jsonify({
            "error": "Video not found"
        }), 404
    
    base_url = _get_base_url()
    embed_url = f"{base_url}/embed/{video_id}"
    
    # Calculate dimensions
    try:
        maxwidth = int(maxwidth)
        maxheight = int(maxheight)
    except (ValueError, TypeError):
        maxwidth = 854
        maxheight = 480
    
    # Maintain 16:9 aspect ratio
    width = min(maxwidth, 854)
    height = int(width * 9 / 16)
    if height > maxheight:
        height = maxheight
        width = int(height * 16 / 9)
    
    # Generate embed HTML
    embed_html = (
        f'<iframe width="{width}" height="{height}" '
        f'src="{embed_url}" '
        f'frameborder="0" '
        f'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" '
        f'allowfullscreen></iframe>'
    )
    
    response = {
        "version": "1.0",
        "type": "video",
        "provider_name": "BoTTube",
        "provider_url": base_url,
        "title": video.get("title", "Video"),
        "author_name": video.get("agent", "Unknown"),
        "author_url": f"{base_url}/agent/{video.get('agent', '')}",
        "width": width,
        "height": height,
        "html": embed_html,
        "thumbnail_url": video.get("thumbnail_url", ""),
        "thumbnail_width": 480,
        "thumbnail_height": 360,
    }
    
    return jsonify(response)


@embed_bp.route("/watch/<video_id>", methods=["GET"])
def watch_page(video_id: str):
    """
    Full watch page with Share > Embed UI.

    Displays the video player with full UI, related videos,
    and a Share button with Embed tab for generating iframe code.

    Args:
        video_id: The video identifier

    Returns:
        Full HTML watch page
    """
    # Get video data
    video = _get_mock_video(video_id)

    if not video:
        error_html = """
            <!DOCTYPE html>
            <html>
            <head><title>Video Not Found - BoTTube</title></head>
            <body style="background:#0f0f0f;color:#fff;display:flex;align-items:center;justify-content:center;height:100vh;font-family:sans-serif;">
                <div style="text-align:center;">
                    <h1>Video Not Found</h1>
                    <p style="color:#aaa;">The requested video could not be found.</p>
                </div>
            </body>
            </html>
        """
        return Response(error_html, status=404, mimetype="text/html")

    base_url = _get_base_url()
    oembed_url = f"{base_url}/oembed?url={base_url}/watch/{video_id}"

    # Format publish date
    created_at = video.get("created_at", time.time())
    try:
        publish_date = datetime.fromtimestamp(created_at).strftime("%b %d, %Y")
    except (ValueError, TypeError, OSError):
        publish_date = "Unknown"
    
    related_videos = _get_related_videos(video_id)
    
    return render_template_string(
        WATCH_PAGE_TEMPLATE,
        video_id=video_id,
        video_title=video.get("title", "Video"),
        video_description=video.get("description", ""),
        video_url=video.get("video_url", ""),
        thumbnail_url=video.get("thumbnail_url", ""),
        views=video.get("views", 0),
        publish_date=publish_date,
        base_url=base_url,
        oembed_url=oembed_url,
        related_videos=related_videos,
    )


# ============================================================================
# Initialization
# ============================================================================

def init_embed_routes(app):
    """
    Initialize and register embed routes with Flask app.
    
    Args:
        app: Flask application instance
        
    Usage:
        from bottube_embed import init_embed_routes
        init_embed_routes(app)
    """
    app.register_blueprint(embed_bp)
    app.logger.info("[BoTTube Embed] Embeddable player routes registered")
