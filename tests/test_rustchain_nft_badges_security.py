# SPDX-License-Identifier: MIT
"""Security and input-validation regression tests for node/rustchain_nft_badges.py."""

from __future__ import annotations

import base64
import importlib.util
import pathlib
from html.parser import HTMLParser
from typing import ClassVar

import pytest

try:
    import defusedxml.ElementTree as _defused_et
except ImportError:
    _defused_et = None

_MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "node" / "rustchain_nft_badges.py"
_SPEC = importlib.util.spec_from_file_location("rustchain_nft_badges", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)

NFTBadgeGenerator = _MOD.NFTBadgeGenerator
BadgeDisplayGenerator = _MOD.BadgeDisplayGenerator


class _SVGTagCollector(HTMLParser):
    """Collect all element tags parsed from generated SVG/XHTML markup."""

    def __init__(self) -> None:
        super().__init__()
        self.tags: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        self.tags.append(tag.lower())

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        self.tags.append(tag.lower())


def _parse_svg_tags(svg: str) -> list[str]:
    """Return element tag names from generated SVG (and XML-validate with defusedxml if present)."""
    if _defused_et is not None:
        root = _defused_et.fromstring(svg)
        return [elem.tag.split("}")[-1].lower() for elem in root.iter()]
    collector = _SVGTagCollector()
    collector.feed(svg)
    collector.close()
    return collector.tags


def test_generate_badge_svg_escapes_script_injection_and_parses_as_xml():
    gen = NFTBadgeGenerator()
    payload = "</text><script>alert(1)</script><text>"
    svg = gen.generate_badge_svg("GENESIS_MINER", "RTCwallet1", payload)

    assert "<script>" not in svg
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in svg

    tags = _parse_svg_tags(svg)
    assert tags.count("svg") == 1
    assert "script" not in tags


def test_generate_badge_svg_strips_illegal_xml_control_chars():
    gen = NFTBadgeGenerator()
    svg = gen.generate_badge_svg("FIRST_BLOCK", "RTCwallet1", "2026-01-01\x00\x07\x1f")

    assert "\x00" not in svg
    assert "\x07" not in svg
    assert "\x1f" not in svg
    tags = _parse_svg_tags(svg)
    assert tags[0] == "svg"


def test_generate_badge_svg_handles_unknown_tier_and_escapes_badge_fields():
    class CustomBadgeGenerator(NFTBadgeGenerator):
        BADGE_TYPES: ClassVar[dict[str, dict[str, str]]] = {
            **NFTBadgeGenerator.BADGE_TYPES,
            "CUSTOM_XSS": {
                "name": '"><script>alert(1)</script>',
                "description": '<img src=x onerror="alert(2)">',
                "tier": "mythic-unknown",
                "icon": "<svg/onload=alert(3)>",
            },
        }

    gen = CustomBadgeGenerator()
    svg = gen.generate_badge_svg("CUSTOM_XSS", "RTCwallet1", "2026-05-01")

    assert "<script>" not in svg
    assert "<img " not in svg
    assert "&lt;svg/onload=alert(3)&gt;" in svg

    tags = _parse_svg_tags(svg)
    assert tags.count("svg") == 1
    assert "script" not in tags
    assert "img" not in tags


def test_generate_badge_showcase_escapes_html_and_allowlists_tier():
    badges = [
        {
            "tier": 'common" onclick="alert(1)',
            "icon": "<img src=x onerror=alert(2)>",
            "name": "<script>alert(3)</script>",
            "description": "<b>desc & \"quotes\"</b>",
            "earned_date": "2026-01-01<svg onload=alert(4)>",
        },
        {
            "tier": "legendary",
            "icon": None,
            "name": None,
            "description": None,
            "earned_date": None,
        },
        "not-a-dict",
    ]
    out = BadgeDisplayGenerator.generate_badge_showcase(badges)

    assert 'onclick="alert(1)' not in out
    assert "<script>" not in out
    assert "<img src=x" not in out
    assert "<svg onload=" not in out
    assert '<div class="badge-card common">' in out
    assert '<div class="badge-card legendary">' in out
    assert "&lt;script&gt;alert(3)&lt;/script&gt;" in out
    assert "&lt;b&gt;desc &amp; &quot;quotes&quot;&lt;/b&gt;" in out
    assert "Earned: Unknown" in out


def test_generate_badge_metadata_encodes_external_url_and_validates_inputs():
    gen = NFTBadgeGenerator()
    meta = gen.generate_badge_metadata(
        "CUSTOM/../?a=1#frag",
        {"wallet": "RTCwallet123", "hardware": "PowerPC G4", "age": 22},
        42,
    )

    assert meta["external_url"].startswith("https://rustchain.org/badge/")
    suffix = meta["external_url"].removeprefix("https://rustchain.org/badge/")
    assert "/" not in suffix
    assert "?" not in suffix
    assert "#" not in suffix

    assert meta["image"].startswith("data:image/svg+xml;base64,")
    decoded_svg = base64.b64decode(meta["image"].split(",", 1)[1]).decode("utf-8")
    tags = _parse_svg_tags(decoded_svg)
    assert tags[0] == "svg"
    assert "script" not in tags

    with pytest.raises(TypeError, match="miner_info"):
        gen.generate_badge_metadata("GENESIS_MINER", None, 10)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="wallet"):
        gen.generate_badge_metadata("GENESIS_MINER", {}, 10)
    with pytest.raises(ValueError, match="wallet"):
        gen.generate_badge_metadata("GENESIS_MINER", {"wallet": "   "}, 10)
    with pytest.raises(ValueError, match="badge_type"):
        gen.generate_badge_metadata("", {"wallet": "RTCwallet123"}, 10)
    with pytest.raises(ValueError, match="block_height"):
        gen.generate_badge_metadata("GENESIS_MINER", {"wallet": "RTCwallet123"}, True)
    with pytest.raises(ValueError, match="block_height"):
        gen.generate_badge_metadata("GENESIS_MINER", {"wallet": "RTCwallet123"}, -1)


def test_check_badge_eligibility_guards_missing_null_bool_and_nonfinite_stats():
    gen = NFTBadgeGenerator()

    # Empty or non-dict stats must not crash or falsely award GENESIS_MINER
    assert gen.check_badge_eligibility({}) == []
    assert gen.check_badge_eligibility(None) == []  # type: ignore[arg-type]

    # Negative, bool, None, string, NaN, inf values must not crash or award badges
    malformed = {
        "first_seen_block": -5,
        "hardware_age": float("nan"),
        "blocks_mined": True,
        "rtc_earned": float("inf"),
        "mining_days": "999",
        "hardware_model": None,
        "unique_hardware": False,
    }
    assert gen.check_badge_eligibility(malformed) == []

    # Valid miner stats keep exact expected badge awards
    valid = {
        "first_seen_block": 50,
        "hardware_age": 36,
        "blocks_mined": 150,
        "rtc_earned": 1500,
        "mining_days": 45,
        "unique_hardware": True,
        "hardware_model": "Intel 486 DX2",
    }
    assert gen.check_badge_eligibility(valid) == [
        "GENESIS_MINER",
        "ANCIENT_KEEPER",
        "MUSEUM_PIECE",
        "BLOCK_CENTURION",
        "RTC_MILLIONAIRE",
        "DEDICATION_MEDAL",
        "FLAMEKEEPER",
        "HARDWARE_DIVERSITY",
        "DIAL_UP_WARRIOR",
    ]
