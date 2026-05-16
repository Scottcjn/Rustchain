# SPDX-License-Identifier: MIT

from __future__ import annotations

import importlib.util
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ARTICLE_CHECKER_PATH = REPO_ROOT / "tools" / "bounty_verifier" / "article_checker.py"


def _load_article_checker():
    spec = importlib.util.spec_from_file_location("article_checker_under_test", ARTICLE_CHECKER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


article_checker = _load_article_checker()


class FakeResponse:
    def __init__(self, status_code: int = 200, text: str = ""):
        self.status_code = status_code
        self.text = text


class FakeTitle:
    def __init__(self, string: str):
        self.string = string


class FakeSoup:
    def __init__(self, html: str, parser: str):
        assert parser == "lxml"
        self.html = html
        match = re.search(r"<title>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
        self.title = FakeTitle(match.group(1)) if match else None

    def get_text(self, separator: str = " "):
        return re.sub(r"<[^>]+>", separator, self.html)


def _enable_fake_parser(monkeypatch):
    monkeypatch.setattr(article_checker, "BS4_AVAILABLE", True)
    monkeypatch.setattr(article_checker, "BeautifulSoup", FakeSoup, raising=False)


def test_check_article_returns_dependency_error_when_bs4_missing(monkeypatch):
    monkeypatch.setattr(article_checker, "BS4_AVAILABLE", False)

    passed, details = article_checker.ArticleChecker().check_article("https://example.test/post")

    assert passed is False
    assert details == {
        "url": "https://example.test/post",
        "error": "beautifulsoup4 not installed",
    }


def test_check_article_passes_for_live_rustchain_article_with_author(monkeypatch):
    _enable_fake_parser(monkeypatch)
    seen = {}

    def fake_get(url, headers, timeout, allow_redirects):
        seen.update(
            {
                "url": url,
                "headers": headers,
                "timeout": timeout,
                "allow_redirects": allow_redirects,
            }
        )
        return FakeResponse(
            text="<title> RustChain launch </title><main>Alice writes about RustChain and RTC rewards.</main>"
        )

    monkeypatch.setattr(article_checker.requests, "get", fake_get)

    passed, details = article_checker.ArticleChecker(timeout=7).check_article(
        "https://example.test/post",
        expected_author="alice",
    )

    assert passed is True
    assert details["mentions_rustchain"] == "True"
    assert details["author_found"] == "True"
    assert details["title"] == "RustChain launch"
    assert seen == {
        "url": "https://example.test/post",
        "headers": {"User-Agent": article_checker.ArticleChecker.USER_AGENT},
        "timeout": 7,
        "allow_redirects": True,
    }


def test_check_article_fails_for_non_200_response(monkeypatch):
    _enable_fake_parser(monkeypatch)
    monkeypatch.setattr(
        article_checker.requests,
        "get",
        lambda url, headers, timeout, allow_redirects: FakeResponse(status_code=404),
    )

    passed, details = article_checker.ArticleChecker().check_article("https://example.test/missing")

    assert passed is False
    assert details["error"] == "HTTP 404"


def test_check_article_fails_when_required_keywords_are_absent(monkeypatch):
    _enable_fake_parser(monkeypatch)
    monkeypatch.setattr(
        article_checker.requests,
        "get",
        lambda url, headers, timeout, allow_redirects: FakeResponse(text="<p>Unrelated article</p>"),
    )

    passed, details = article_checker.ArticleChecker().check_article("https://example.test/unrelated")

    assert passed is False
    assert details["mentions_rustchain"] == "False"
    assert details["error"] == "Article does not mention RustChain or RTC"


def test_check_article_warns_but_passes_when_author_is_missing(monkeypatch):
    _enable_fake_parser(monkeypatch)
    monkeypatch.setattr(
        article_checker.requests,
        "get",
        lambda url, headers, timeout, allow_redirects: FakeResponse(text="<p>RTC bounty guide</p>"),
    )

    passed, details = article_checker.ArticleChecker().check_article(
        "https://example.test/rtc",
        expected_author="alice",
    )

    assert passed is True
    assert details["mentions_rustchain"] == "True"
    assert details["author_found"] == "False"
    assert details["warning"] == "Author 'alice' not found in article text"


def test_check_article_handles_request_timeout(monkeypatch):
    _enable_fake_parser(monkeypatch)

    def fake_get(url, headers, timeout, allow_redirects):
        raise article_checker.requests.exceptions.Timeout

    monkeypatch.setattr(article_checker.requests, "get", fake_get)

    passed, details = article_checker.ArticleChecker().check_article("https://example.test/slow")

    assert passed is False
    assert details["error"] == "Request timed out"
