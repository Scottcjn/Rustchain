# SPDX-License-Identifier: MIT
"""Security and input-sanitization regression tests for node/bottube_embed.py."""

import importlib.util
import pathlib
from unittest.mock import patch

from flask import Flask

_MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "node" / "bottube_embed.py"
_SPEC = importlib.util.spec_from_file_location("bottube_embed_sec", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)


def _make_app() -> Flask:
    app = Flask(__name__)
    app.config["TESTING"] = True
    _MOD.init_embed_routes(app)
    return app


def test_watch_page_script_uses_json_escaping_preventing_script_breakout():
    app = _make_app()
    malicious_id = '</script><script>alert("xss")</script>'
    fake_video = {
        "id": malicious_id,
        "title": "Test Video",
        "description": "Desc",
        "agent": "demo-agent",
        "created_at": 1700000000,
        "thumbnail_url": "https://bottube.ai/thumbnails/demo.jpg",
        "video_url": "https://bottube.ai/videos/demo.mp4",
        "views": 10,
    }

    with (
        patch.object(_MOD, "_get_mock_video", return_value=fake_video),
        app.test_request_context("/watch/demo", base_url="https://bottube.ai"),
    ):
        rendered = _MOD.watch_page(malicious_id)

    assert '</script><script>alert("xss")</script>' not in rendered
    assert 'const videoId = "\\u003c/script\\u003e\\u003cscript\\u003ealert(\\"xss\\")\\u003c/script\\u003e";' in rendered
    assert "encodeURIComponent(videoId)" in rendered


def test_oembed_escapes_iframe_src_and_encodes_author_url():
    app = _make_app()
    client = app.test_client()
    tricky_id = 'vid"onload=alert(1)<x>'
    fake_video = {
        "id": tricky_id,
        "title": "Demo",
        "agent": 'bad"agent/../../x',
        "thumbnail_url": "https://bottube.ai/thumbnails/demo.jpg",
        "video_url": "https://bottube.ai/videos/demo.mp4",
    }

    with patch.object(_MOD, "_get_mock_video", return_value=fake_video):
        resp = client.get(
            "/oembed",
            query_string={"url": f"https://bottube.ai/watch/{tricky_id}"},
            base_url="https://bottube.ai",
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert 'onload=alert(1)' not in data["html"] or "%22onload" in data["html"]
    assert '"onload=' not in data["html"]
    assert "<x>" not in data["html"]
    assert data["author_url"] == "https://bottube.ai/agent/bad%22agent%2F..%2F..%2Fx"


def test_oembed_strips_url_fragments_and_clamps_minimum_dimensions():
    app = _make_app()
    client = app.test_client()

    resp_watch = client.get(
        "/oembed",
        query_string={"url": "https://bottube.ai/watch/demo-001#t=45", "maxwidth": "1"},
        base_url="https://bottube.ai",
    )
    assert resp_watch.status_code == 200
    data = resp_watch.get_json()
    assert data["width"] == 1
    assert data["height"] == 1
    assert 'height="0"' not in data["html"]
    assert 'src="https://bottube.ai/embed/demo-001"' in data["html"]

    resp_embed = client.get(
        "/oembed",
        query_string={"url": "https://bottube.ai/embed/demo-002#section"},
        base_url="https://bottube.ai",
    )
    assert resp_embed.status_code == 200
    assert "demo-002" in resp_embed.get_json()["html"]


def test_sanitize_media_url_blocks_unsafe_schemes_and_control_chars():
    unsafe_urls = [
        "javascript:alert(1)",
        "JavaScript:alert(1)",
        "vbscript:msgbox(1)",
        "data:text/html,<script>alert(1)</script>",
        "//evil.example/video.mp4",
        "/\\evil.example/video.mp4",
        "https://bottube.ai/v.mp4\r\nX-Test: 1",
        "https://bottube.ai/v.mp4\x00",
        12345,
        None,
    ]
    for bad in unsafe_urls:
        assert _MOD._sanitize_media_url(bad) == ""

    assert _MOD._sanitize_media_url("https://bottube.ai/videos/demo-001.mp4") == "https://bottube.ai/videos/demo-001.mp4"
    assert _MOD._sanitize_media_url("http://localhost:8099/v.mp4") == "http://localhost:8099/v.mp4"
    assert _MOD._sanitize_media_url("/videos/demo-001.mp4") == "/videos/demo-001.mp4"

    app = _make_app()
    client = app.test_client()
    unsafe_video = {
        "id": "demo-xss",
        "title": "Unsafe Media",
        "description": "Test",
        "agent": "agent-1",
        "created_at": 1700000000,
        "thumbnail_url": "javascript:alert(1)",
        "video_url": "data:text/html,<script>alert(2)</script>",
        "views": 1,
    }
    with patch.object(_MOD, "_get_mock_video", return_value=unsafe_video):
        embed_resp = client.get("/embed/demo-xss", base_url="https://bottube.ai")
        watch_resp = client.get("/watch/demo-xss", base_url="https://bottube.ai")
        oembed_resp = client.get(
            "/oembed",
            query_string={"url": "https://bottube.ai/watch/demo-xss"},
            base_url="https://bottube.ai",
        )

    assert b"javascript:alert" not in embed_resp.data
    assert b"data:text/html" not in embed_resp.data
    assert b"javascript:alert" not in watch_resp.data
    assert b"data:text/html" not in watch_resp.data
    assert oembed_resp.get_json()["thumbnail_url"] == ""


def test_get_base_url_rejects_injected_host_header():
    app = _make_app()
    client = app.test_client()
    resp = client.get(
        "/oembed",
        query_string={"url": "https://bottube.ai/watch/demo-001"},
        headers={"Host": 'evil.example"><script>alert(1)</script>'},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["provider_url"] == "https://bottube.ai"
    assert "<script>" not in data["html"]
    assert "evil.example" not in data["html"]

    # Even if misconfigured into TRUSTED_FORWARD_HOSTS, unsafe host chars are rejected
    bad_host = 'evil.example" onclick="alert(1)'
    app.config["TRUSTED_FORWARD_HOSTS"] = [bad_host]
    resp2 = client.get(
        "/oembed",
        query_string={"url": "https://bottube.ai/watch/demo-001"},
        headers={"X-Forwarded-Host": bad_host},
        base_url="https://bottube.ai",
    )
    assert resp2.status_code == 200
    assert "onclick=" not in resp2.get_json()["html"]


def test_watch_page_encodes_oembed_discovery_query_param():
    app = _make_app()
    client = app.test_client()
    resp = client.get("/watch/demo-001", base_url="https://bottube.ai")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert (
        'href="https://bottube.ai/oembed?url=https%3A%2F%2Fbottube.ai%2Fwatch%2Fdemo-001"'
        in body
    )
