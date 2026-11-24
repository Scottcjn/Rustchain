# SPDX-License-Identifier: MIT
"""Regression tests for machine passport viewer XSS protections and QR URL formatting."""

import sys
from pathlib import Path
from urllib.parse import quote

import pytest
from flask import Flask

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "node") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "node"))

import machine_passport_api
import machine_passport_viewer
from machine_passport import MachinePassport


def _make_viewer_app(tmp_path, monkeypatch):
    monkeypatch.setattr(
        machine_passport_viewer,
        "PASSPORT_DB_PATH",
        str(tmp_path / "passports.db"),
    )
    monkeypatch.setattr(machine_passport_viewer, "_ledger", None)

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(machine_passport_viewer.passport_viewer_bp)
    return app, machine_passport_viewer.get_ledger()


def test_list_passports_escapes_html_and_encodes_href(tmp_path, monkeypatch):
    app, ledger = _make_viewer_app(tmp_path, monkeypatch)
    machine_id = 'id"><img src=x onerror=alert(1)>'
    ok, _ = ledger.create_passport(
        MachinePassport(
            machine_id=machine_id,
            name="<script>alert('name')</script>",
            owner_miner_id='<svg onload="alert(2)">',
            architecture='" autofocus onfocus=alert(3)>',
        )
    )
    assert ok is True

    resp = app.test_client().get("/passport/")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "<script>alert('name')</script>" not in body
    assert "<img src=x onerror=alert(1)>" not in body
    assert '<svg onload="alert(2)">' not in body
    assert '" autofocus onfocus=alert(3)>' not in body
    assert "&lt;script&gt;alert(&#x27;name&#x27;)&lt;/script&gt;" in body
    assert f'href="/passport/{quote(machine_id, safe="")}"' in body


def test_view_passport_autoescapes_all_sections(tmp_path, monkeypatch):
    app, ledger = _make_viewer_app(tmp_path, monkeypatch)
    machine_id = "mp'\"<svg onload=alert(0)>"
    ok, _ = ledger.create_passport(
        MachinePassport(
            machine_id=machine_id,
            name="</title><script>alert('name')</script>",
            owner_miner_id="<img src=x onerror=alert('owner')>",
            architecture="<script>alert('arch')</script>",
            provenance="<svg onload=alert('prov')>",
            manufacture_year=1999,
        )
    )
    assert ok is True

    ledger.add_repair_entry(
        machine_id=machine_id,
        repair_date=1700000000,
        repair_type="<script>alert('rtype')</script>",
        description="<img src=x onerror=alert('rdesc')>",
        parts_replaced="<svg onload=alert('parts')>",
        technician="<b><script>alert('tech')</script></b>",
    )
    ledger.add_attestation(
        machine_id=machine_id,
        attestation_ts=1700000100,
        epoch=42,
        total_epochs=42,
        total_rtc_earned=5_000_000,
        hardware_binding="<script>alert('hw')</script>",
    )
    ledger.add_benchmark(
        machine_id=machine_id,
        benchmark_ts=1700000200,
        compute_score=1234.5,
        memory_bandwidth=2500.0,
        simd_identity="<script>alert('simd')</script>",
    )
    ledger.add_lineage_note(
        machine_id=machine_id,
        lineage_ts=1700000300,
        event_type="<img src=x onerror=alert('ev')>",
        from_owner="<script>alert('from')</script>",
        to_owner="<script>alert('to')</script>",
        description="<svg onload=alert('ldesc')>",
        tx_hash="<script>alert('tx')</script>",
    )

    resp = app.test_client().get(f"/passport/{quote(machine_id, safe='')}")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    for forbidden in (
        "</title><script>",
        "<script>alert(",
        "<img src=x onerror=",
        "<svg onload=",
    ):
        assert forbidden not in body

    assert "&lt;/title&gt;&lt;script&gt;alert(&#39;name&#39;)&lt;/script&gt;" in body
    assert "&lt;script&gt;alert(&#39;arch&#39;)&lt;/script&gt;" in body
    assert "&lt;script&gt;alert(&#39;simd&#39;)&lt;/script&gt;" in body
    assert f'href="/passport/{quote(machine_id, safe="")}/pdf"' in body
    assert "encodeURIComponent(" in body
    assert "\\u003csvg onload=alert(0)\\u003e" in body


@pytest.mark.parametrize(
    "unsafe_url",
    [
        "javascript:alert(1)",
        "JAVASCRIPT:alert(1)",
        "java\tscript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "vbscript:msgbox(1)",
        "//evil.example/relic.png",
        "/\\evil.example/relic.png",
        "file:///etc/passwd",
    ],
)
def test_view_passport_blocks_unsafe_photo_url_schemes(tmp_path, monkeypatch, unsafe_url):
    app, ledger = _make_viewer_app(tmp_path, monkeypatch)
    ok, _ = ledger.create_passport(
        MachinePassport(
            machine_id="photo-unsafe",
            name="PowerMac G4",
            owner_miner_id="miner_1",
            photo_url=unsafe_url,
        )
    )
    assert ok is True

    resp = app.test_client().get("/passport/photo-unsafe")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert 'alt="PowerMac G4"' not in body
    assert "javascript:" not in body.lower()
    assert "vbscript:" not in body.lower()
    assert "data:text/html" not in body.lower()
    assert "evil.example" not in body


@pytest.mark.parametrize(
    ("photo_url", "expected_src"),
    [
        ("https://example.com/relic.jpg", 'src="https://example.com/relic.jpg"'),
        (
            "http://example.com/img.png?a=1&b=2",
            'src="http://example.com/img.png?a=1&amp;b=2"',
        ),
        ("/static/images/relic.png", 'src="/static/images/relic.png"'),
        (
            'https://example.com/a"onerror="alert(1)',
            'src="https://example.com/a&#34;onerror=&#34;alert(1)"',
        ),
    ],
)
def test_view_passport_allows_safe_photo_urls_and_escapes_attributes(
    tmp_path, monkeypatch, photo_url, expected_src
):
    app, ledger = _make_viewer_app(tmp_path, monkeypatch)
    ok, _ = ledger.create_passport(
        MachinePassport(
            machine_id="photo-safe",
            name="PowerMac G5",
            owner_miner_id="miner_2",
            photo_url=photo_url,
        )
    )
    assert ok is True

    resp = app.test_client().get("/passport/photo-safe")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert expected_src in body


def test_view_passport_inline_script_escapes_closing_script_tag(tmp_path, monkeypatch):
    app, ledger = _make_viewer_app(tmp_path, monkeypatch)
    machine_id = "bad</script><script>alert(9)</script>"
    ok, _ = ledger.create_passport(
        MachinePassport(
            machine_id=machine_id,
            name="Relic",
            owner_miner_id="miner_3",
        )
    )
    assert ok is True

    with app.test_request_context("/passport/test"):
        body = machine_passport_viewer.view_passport(machine_id)

    assert "</script><script>alert(9)</script>" not in body
    assert "\\u003c/script\\u003e\\u003cscript\\u003ealert(9)\\u003c/script\\u003e" in body


def test_qr_endpoint_builds_well_formed_passport_url(tmp_path, monkeypatch):
    monkeypatch.setattr(
        machine_passport_api,
        "PASSPORT_DB_PATH",
        str(tmp_path / "api_passports.db"),
    )
    monkeypatch.setattr(machine_passport_api, "_ledger", None)

    recorded_urls = []

    def _write_fake_qr(passport_url: str, output_path: str):
        recorded_urls.append(passport_url)
        Path(output_path).write_bytes(b"\x89PNG\r\n\x1a\n")
        return True, "ok"

    monkeypatch.setattr(machine_passport_api, "generate_qr_code", _write_fake_qr)

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(machine_passport_api.machine_passport_bp)
    ledger = machine_passport_api.get_ledger()

    for mid in ("relic_01", "relic 02"):
        ok, _ = ledger.create_passport(
            MachinePassport(
                machine_id=mid,
                name=f"Machine {mid}",
                owner_miner_id="miner_qr",
            )
        )
        assert ok is True

    client = app.test_client()

    resp1 = client.get("/api/machine-passport/relic_01/qr")
    data1 = resp1.get_json()
    assert resp1.status_code == 200
    assert data1["ok"] is True
    assert data1["passport_url"] == "http://localhost/passport/relic_01"
    assert "localhostpassport" not in data1["passport_url"]

    resp2 = client.get("/api/machine-passport/relic%2002/qr")
    data2 = resp2.get_json()
    assert resp2.status_code == 200
    assert data2["ok"] is True
    assert data2["passport_url"] == "http://localhost/passport/relic%2002"

    assert recorded_urls == [
        "http://localhost/passport/relic_01",
        "http://localhost/passport/relic%2002",
    ]
