#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Unit tests for Bounty #2292 (`BCOS v2: Badge generator web tool`).
Verifies:
  1. `_generate_badge_svg()` renders valid SVG in `flat`, `flat-square`, and `for-the-badge` styles
     and escapes untrusted characters.
  2. `GET /bcos/badge/<cert_id>.svg?style=...` serves the requested style for attested certificates.
  3. `GET /bcos/badge-generator` serves the interactive HTML badge generator tool and JSON embed mode.
  4. `docs/bcos/badge-generator.html` contains live preview, style switcher, and Markdown/HTML copy controls.
"""

from __future__ import annotations

from hashlib import blake2b
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile

from flask import Flask

NODE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = NODE_DIR.parent
if str(NODE_DIR) not in sys.path:
    sys.path.insert(0, str(NODE_DIR))

import bcos_routes  # noqa: E402


def _make_sample_report(cert_suffix: str = "2292beef", tier: str = "L2", score: int = 92) -> dict:
    base = {
        "schema": "bcos-attestation/v2",
        "repo_name": "Scottcjn/Rustchain",
        "commit_sha": "1234567890abcdef1234567890abcdef12345678",
        "tier": tier,
        "trust_score": score,
        "reviewer": "scottcjn",
        "score_breakdown": {"license_compliance": 20},
        "checks": {"license_compliance": {"passed": True}},
        "engine_version": "2.0.0",
    }
    canonical = json.dumps(base, sort_keys=True, separators=(",", ":"))
    commitment = blake2b(canonical.encode(), digest_size=32).hexdigest()
    return {
        **base,
        "cert_id": f"BCOS-{cert_suffix}",
        "commitment": commitment,
    }


def test_generate_badge_svg_styles_and_escaping():
    svg_flat = bcos_routes._generate_badge_svg("L1", 78, style="flat")
    assert "<svg" in svg_flat
    assert "L1 78/100" in svg_flat
    assert "#08c" in svg_flat

    svg_square = bcos_routes._generate_badge_svg("L2", 91, style="flat-square")
    assert 'data-style="flat-square"' in svg_square
    assert "L2 91/100" in svg_square
    assert "#93c" in svg_square

    svg_banner = bcos_routes._generate_badge_svg("L0", 45, style="for-the-badge")
    assert 'data-style="for-the-badge"' in svg_banner
    assert 'height="28"' in svg_banner
    assert "L0 45/100" in svg_banner

    svg_escaped = bcos_routes._generate_badge_svg("<script>", 10, style="flat")
    assert "<script>" not in svg_escaped
    assert "&lt;script&gt;" in svg_escaped


def test_badge_svg_endpoint_and_badge_generator_routes(monkeypatch):
    monkeypatch.setenv("RC_ADMIN_KEY", "test-admin-secret")
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "bcos_test.db")
        with sqlite3.connect(db_path) as conn:
            bcos_routes.init_bcos_table(conn)
            conn.commit()

        app = Flask(__name__)
        bcos_routes.register_bcos_routes(app, db_path)
        client = app.test_client()

        report = _make_sample_report()
        res_attest = client.post(
            "/bcos/attest",
            json={"report": report},
            headers={"X-Admin-Key": "test-admin-secret"},
        )
        assert res_attest.status_code == 200
        attest_json = res_attest.get_json()
        assert attest_json["ok"] is True

        for style in ("flat", "flat-square", "for-the-badge"):
            res_svg = client.get(f"/bcos/badge/{report['cert_id']}.svg?style={style}")
            assert res_svg.status_code == 200
            assert "image/svg+xml" in res_svg.content_type
            svg_body = res_svg.get_data(as_text=True)
            assert "L2 92/100" in svg_body
            if style != "flat":
                assert f'data-style="{style}"' in svg_body

        res_gen_html = client.get("/bcos/badge-generator")
        assert res_gen_html.status_code == 200
        html_body = res_gen_html.get_data(as_text=True)
        assert "BCOS v2" in html_body
        assert "markdownSnippet" in html_body or "BCOS Certified" in html_body

        res_gen_json = client.get(
            f"/bcos/badge-generator?cert_id={report['cert_id']}&style=for-the-badge&format=json"
        )
        assert res_gen_json.status_code == 200
        embed_data = res_gen_json.get_json()
        assert embed_data["ok"] is True
        assert embed_data["style"] == "for-the-badge"
        assert f"/bcos/badge/{report['cert_id']}.svg?style=for-the-badge" in embed_data["markdown"]
        assert f"/bcos/verify/{report['cert_id']}" in embed_data["html"]


def test_standalone_badge_generator_html_file():
    html_file = ROOT_DIR / "docs" / "bcos" / "badge-generator.html"
    assert html_file.exists(), f"Missing {html_file}"
    content = html_file.read_text(encoding="utf-8")
    assert "/bcos/verify/" in content
    assert "/bcos/directory" in content
    assert "flat-square" in content
    assert "for-the-badge" in content
    assert "[![BCOS Certified]" in content
