# SPDX-License-Identifier: MIT

from pathlib import Path


PROFILE_BADGE_GENERATOR = Path(__file__).resolve().parents[1] / "profile_badge_generator.py"


def test_profile_badge_preview_escapes_custom_message_labels():
    source = PROFILE_BADGE_GENERATOR.read_text(encoding="utf-8")

    assert "from html import escape as escape_html" in source
    assert 'urllib.parse.quote(label, safe="")' in source
    assert "escaped_label = escape_html(label, quote=True)" in source
    assert "markdown_label = escape_markdown_alt_text(label)" in source
    assert 'alt="RustChain {escaped_label}"' in source
    assert 'alt="RustChain {label}"' not in source

    assert "const previewImage = document.createElement('img');" in source
    assert "previewImage.src = data.shield_url;" in source
    assert "previewImage.alt = data.alt_text || 'RustChain badge';" in source
    assert "badgePreview.replaceChildren();" in source
    assert "document.getElementById('badgePreview').innerHTML" not in source
