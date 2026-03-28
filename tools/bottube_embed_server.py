#!/usr/bin/env python3
"""
BoTTube Embeddable Player Server
=================================
Flask application that serves an embeddable video player for BoTTube videos.

Routes:
    GET /embed/<video_id>          → HTML player page
    GET /embed/api/<video_id>      → JSON video metadata
    GET /embed/bottube-embed.js    → JS loader script

Usage:
    python tools/bottube_embed_server.py [--port 5050] [--host 0.0.0.0]

Environment variables:
    BOTTUBE_API_URL   Base URL of the BoTTube API (default: https://api.bottube.io)
    BOTTUBE_CDN_URL   Base URL for video assets (default: https://cdn.bottube.io)
    FLASK_SECRET_KEY  Flask secret key for sessions
"""

import os
import json
import argparse
import logging
from functools import wraps
from flask import Flask, request, jsonify, Response, abort

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "bottube-embed-dev-key")

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("bottube-embed")

BOTTUBE_API_URL = os.environ.get("BOTTUBE_API_URL", "https://api.bottube.io")
BOTTUBE_CDN_URL = os.environ.get("BOTTUBE_CDN_URL", "https://cdn.bottube.io")

ALLOWED_THEMES = {"dark", "light"}
DEFAULT_THEME = "dark"


# ---------------------------------------------------------------------------
# CORS helper
# ---------------------------------------------------------------------------

def _cors_headers(origin: str = "*") -> dict:
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Access-Control-Max-Age": "3600",
    }


def cors(fn):
    """Decorator that adds CORS headers to every response."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if request.method == "OPTIONS":
            resp = Response("", status=204)
            for k, v in _cors_headers().items():
                resp.headers[k] = v
            return resp
        result = fn(*args, **kwargs)
        if isinstance(result, Response):
            resp = result
        else:
            resp = Response(*result) if isinstance(result, tuple) else Response(result)
        for k, v in _cors_headers().items():
            resp.headers[k] = v
        return resp
    return wrapper


# ---------------------------------------------------------------------------
# Mock metadata — replace with real BoTTube API call in production
# ---------------------------------------------------------------------------

def _fetch_video_metadata(video_id: str) -> dict | None:
    """
    Returns video metadata dict or None if not found.
    In production: call BOTTUBE_API_URL/v1/videos/<video_id>
    """
    if not video_id or not video_id.replace("-", "").replace("_", "").isalnum():
        return None

    return {
        "id": video_id,
        "title": f"BoTTube Video {video_id}",
        "description": "A video hosted on BoTTube.",
        "duration": 300,
        "thumbnail_url": f"{BOTTUBE_CDN_URL}/thumbs/{video_id}.jpg",
        "stream_url": f"{BOTTUBE_CDN_URL}/videos/{video_id}/master.m3u8",
        "mp4_url": f"{BOTTUBE_CDN_URL}/videos/{video_id}/720p.mp4",
        "author": "BoTTube Creator",
        "published_at": "2026-01-01T00:00:00Z",
        "tags": [],
        "embed_url": f"/embed/{video_id}",
    }


# ---------------------------------------------------------------------------
# Player HTML builder (pure Python — no Jinja templates, no HTML files)
# ---------------------------------------------------------------------------

def _build_player_html(video_id: str, meta: dict, *, autoplay: bool,
                        theme: str, start_time: int) -> str:
    bg = "#111" if theme == "dark" else "#f5f5f5"
    fg = "#eee" if theme == "dark" else "#111"
    ctrl_bg = "#1a1a1a" if theme == "dark" else "#ddd"

    autoplay_attr = "autoplay muted" if autoplay else ""
    stream_url = meta["mp4_url"]  # fallback to mp4; HLS needs hls.js
    title = meta["title"]
    thumb = meta["thumbnail_url"]

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} – BoTTube Player</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:{bg};color:{fg};font-family:sans-serif;height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;overflow:hidden}}
#player-wrap{{width:100%;height:100%;position:relative}}
video{{width:100%;height:100%;object-fit:contain;display:block;background:#000}}
#overlay{{position:absolute;top:0;left:0;width:100%;height:100%;display:flex;align-items:center;justify-content:center;cursor:pointer;transition:opacity .2s}}
#overlay.hidden{{opacity:0;pointer-events:none}}
#play-btn{{width:64px;height:64px;border-radius:50%;background:rgba(0,0,0,.6);border:3px solid #fff;display:flex;align-items:center;justify-content:center}}
#play-btn svg{{margin-left:4px}}
#title-bar{{position:absolute;top:0;left:0;width:100%;padding:8px 12px;background:linear-gradient(to bottom,rgba(0,0,0,.7),transparent);font-size:13px;color:#fff;pointer-events:none}}
</style>
</head>
<body>
<div id="player-wrap">
  <video id="btv" src="{stream_url}#t={start_time}" poster="{thumb}"
         controls preload="metadata" {autoplay_attr}
         playsinline crossorigin="anonymous">
    Your browser does not support HTML5 video.
  </video>
  <div id="title-bar">{title}</div>
</div>
<script>
(function(){{
  "use strict";
  var vid = document.getElementById("btv");
  var parent = window.parent;
  var origin = "*";

  function post(type, data){{
    parent.postMessage(Object.assign({{type:"bottube:"+type,videoId:"{video_id}"}}, data||{{}}), origin);
  }}

  // Expose postMessage command API
  window.addEventListener("message", function(e){{
    if(!e.data||!e.data.type) return;
    switch(e.data.type){{
      case "bottube:play":   vid.play();  break;
      case "bottube:pause":  vid.pause(); break;
      case "bottube:seek":   if(typeof e.data.time==="number") vid.currentTime=e.data.time; break;
      case "bottube:volume": if(typeof e.data.volume==="number") vid.volume=e.data.volume; break;
      case "bottube:mute":   vid.muted=!!e.data.muted; break;
      case "bottube:getState":
        post("state",{{paused:vid.paused,currentTime:vid.currentTime,duration:vid.duration,volume:vid.volume,muted:vid.muted}});
        break;
    }}
  }});

  // Emit lifecycle events to parent
  vid.addEventListener("play",      function(){{ post("play",{{currentTime:vid.currentTime}}); }});
  vid.addEventListener("pause",     function(){{ post("pause",{{currentTime:vid.currentTime}}); }});
  vid.addEventListener("ended",     function(){{ post("ended",{{}}); }});
  vid.addEventListener("timeupdate",function(){{ post("timeupdate",{{currentTime:vid.currentTime,duration:vid.duration}}); }});
  vid.addEventListener("volumechange",function(){{ post("volumechange",{{volume:vid.volume,muted:vid.muted}}); }});
  vid.addEventListener("error",     function(){{ post("error",{{message:"Playback error"}}); }});
  vid.addEventListener("loadedmetadata",function(){{ post("ready",{{duration:vid.duration}}); }});

  // Signal ready on load
  window.addEventListener("load", function(){{ post("loaded",{{}}); }});
}})();
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/embed/bottube-embed.js")
@cors
def serve_js_loader():
    """Serve the JS loader script from the filesystem next to this file."""
    js_path = os.path.join(os.path.dirname(__file__), "bottube_embed_loader.js")
    try:
        with open(js_path, "r", encoding="utf-8") as fh:
            js_content = fh.read()
    except FileNotFoundError:
        abort(404)
    return Response(js_content, mimetype="application/javascript")


@app.route("/embed/api/<video_id>", methods=["GET", "OPTIONS"])
@cors
def video_api(video_id: str):
    """Return JSON metadata for a video."""
    meta = _fetch_video_metadata(video_id)
    if not meta:
        return jsonify({"error": "Video not found", "video_id": video_id}), 404
    return jsonify(meta)


@app.route("/embed/<video_id>", methods=["GET", "OPTIONS"])
@cors
def embed_player(video_id: str):
    """Render the embeddable player HTML page."""
    meta = _fetch_video_metadata(video_id)
    if not meta:
        abort(404)

    autoplay = request.args.get("autoplay", "0") in ("1", "true", "yes")
    theme = request.args.get("theme", DEFAULT_THEME)
    if theme not in ALLOWED_THEMES:
        theme = DEFAULT_THEME
    try:
        start_time = max(0, int(request.args.get("t", 0)))
    except (ValueError, TypeError):
        start_time = 0

    html = _build_player_html(video_id, meta,
                               autoplay=autoplay, theme=theme, start_time=start_time)
    return Response(html, mimetype="text/html")


@app.route("/embed/health")
def health():
    return jsonify({"status": "ok", "service": "bottube-embed-server"})


@app.route("/")
def index():
    return jsonify({
        "service": "BoTTube Embed Server",
        "version": "1.0.0",
        "docs": "https://github.com/b1t0r/rustchain/blob/main/docs/EMBED_GUIDE.md",
        "routes": {
            "player": "/embed/<video_id>",
            "api":    "/embed/api/<video_id>",
            "loader": "/embed/bottube-embed.js",
            "health": "/embed/health",
        },
    })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BoTTube Embed Server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5050, help="Bind port (default: 5050)")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode")
    args = parser.parse_args()

    log.info("Starting BoTTube Embed Server on %s:%d", args.host, args.port)
    app.run(host=args.host, port=args.port, debug=args.debug)
