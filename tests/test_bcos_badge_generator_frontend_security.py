from pathlib import Path


def test_bcos_badge_preview_validates_ids_and_uses_dom_nodes():
    page = Path(__file__).resolve().parents[1] / "web" / "bcos" / "badge-generator.html"
    html = page.read_text(encoding="utf-8")

    assert "if (/^BCOS-[a-zA-Z0-9]+$/i.test(input)) return input;" in html
    assert "const previewLink = document.createElement('a');" in html
    assert "previewLink.href = verifyUrl;" in html
    assert "previewLink.rel = 'noopener';" in html
    assert "const previewImage = document.createElement('img');" in html
    assert "previewImage.src = badgeUrl;" in html
    assert "preview.appendChild(previewLink);" in html

    assert "if (/^BCOS-/i.test(input)) return input;" not in html
    assert "document.getElementById('preview').innerHTML =" not in html
    assert '<a href="${verifyUrl}" target="_blank"><img src="${badgeUrl}"' not in html
