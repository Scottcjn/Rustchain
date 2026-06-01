# SPDX-License-Identifier: MIT
from unittest.mock import patch

import tools.os_detector as os_detector


class FixedDateTime:
    @staticmethod
    def now(_tz):
        class FixedNow:
            @staticmethod
            def isoformat():
                return "2026-05-11T12:00:00+00:00"

        return FixedNow()


def test_detect_legacy_os_badges_detects_multiple_matching_environments():
    directory_listing = ["System Folder", "Finder", "win.ini", "progman.exe"]

    with patch.object(
        os_detector.os,
        "listdir",
        return_value=directory_listing,
    ), patch.object(os_detector, "datetime", FixedDateTime):
        result = os_detector.detect_legacy_os_badges()

    assert [badge["title"] for badge in result["badges"]] == [
        "MacInitiate",
        "Progman Pioneer",
    ]
    assert all(badge["class"] == "OS Relic" for badge in result["badges"])
    assert result["badges"][0]["rarity"] == "Legendary"
    assert result["badges"][1]["emotional_resonance"]["timestamp"] == (
        "2026-05-11T12:00:00Z"
    )


def test_detect_legacy_os_badges_returns_empty_list_when_directory_probe_fails():
    with patch.object(
        os_detector.os,
        "listdir",
        side_effect=OSError("dir unavailable"),
    ):
        result = os_detector.detect_legacy_os_badges()

    assert result == {"badges": []}


def test_detect_legacy_os_badges_uses_filesystem_listing_not_shell():
    calls = []

    def fake_listdir(path):
        calls.append(path)
        return ["command.com", "config.sys"]

    with patch.object(os_detector.os, "listdir", fake_listdir):
        result = os_detector.detect_legacy_os_badges()

    assert calls == ["."]
    assert [badge["title"] for badge in result["badges"]] == ["DOS Cowboy", "Explorer Awakener"]
