# SPDX-License-Identifier: MIT
from pathlib import Path
import importlib.util


MODULE_PATH = Path(__file__).resolve().parents[1] / "profile_badge_generator.py"


def load_profile_badge_module(tmp_path):
    spec = importlib.util.spec_from_file_location("profile_badge_generator_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module.DB_PATH = str(tmp_path / "profile_badges.db")
    return module


def test_custom_message_is_escaped_in_generated_badge_markup(tmp_path):
    module = load_profile_badge_module(tmp_path)
    client = module.app.test_client()
    payload = 'Active"] <script>alert(1)</script> / badge'

    response = client.post(
        "/api/badge/create",
        json={
            "username": "alice",
            "badge_type": "contributor",
            "custom_message": payload,
        },
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "%22%5D%20%3Cscript%3Ealert%281%29%3C%2Fscript%3E%20%2F%20badge" in data["shield_url"]
    assert "<script>" not in data["html"]
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in data["html"]
    assert 'Active&quot;] &lt;script&gt;' in data["preview_html"]
    assert 'Active"] <script>' not in data["preview_html"]
    assert 'RustChain Active"\\]' in data["markdown"]
    assert 'RustChain Active"]' not in data["markdown"]


def test_badge_generator_preview_uses_dom_api_not_returned_html():
    source = MODULE_PATH.read_text(encoding="utf-8")

    assert "badgePreview.replaceChildren();" in source
    assert "document.createElement('img')" in source
    assert "previewImage.src = data.shield_url;" in source
    assert "previewImage.alt = data.alt_text || 'RustChain Badge';" in source
    assert "badgePreview.appendChild(previewImage);" in source
    assert "badgePreview').innerHTML = data.preview_html" not in source
