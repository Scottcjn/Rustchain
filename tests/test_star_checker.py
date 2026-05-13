# SPDX-License-Identifier: MIT

from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
STAR_CHECKER_PATH = REPO_ROOT / "tools" / "bounty_verifier" / "star_checker.py"


def _load_star_checker():
    spec = importlib.util.spec_from_file_location("star_checker_under_test", STAR_CHECKER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


star_checker = _load_star_checker()


class FakeResponse:
    def __init__(self, status_code: int = 200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else []

    def json(self):
        return self._payload


def test_check_user_starred_repo_paginates_and_matches_case_insensitive(monkeypatch):
    first_page = [{"login": f"user-{idx}"} for idx in range(100)]
    pages = {
        1: first_page,
        2: [{"login": "TargetUser"}],
    }
    seen_pages = []

    def fake_get(url, headers, timeout):
        assert headers["Authorization"] == "token secret"
        assert timeout == 10
        page = int(url.rsplit("page=", 1)[1])
        seen_pages.append(page)
        return FakeResponse(payload=pages[page])

    monkeypatch.setattr(star_checker.requests, "get", fake_get)

    assert star_checker.check_user_starred_repo("targetuser", "owner", "repo", "secret") is True
    assert seen_pages == [1, 2]


def test_check_user_starred_repo_stops_after_short_page_without_match(monkeypatch):
    calls = 0

    def fake_get(url, headers, timeout):
        nonlocal calls
        calls += 1
        return FakeResponse(payload=[{"login": "someone-else"}])

    monkeypatch.setattr(star_checker.requests, "get", fake_get)

    assert star_checker.check_user_starred_repo("targetuser", "owner", "repo", "secret") is False
    assert calls == 1


def test_check_user_starred_repo_returns_false_on_api_error(monkeypatch):
    def fake_get(url, headers, timeout):
        return FakeResponse(status_code=500, payload={"message": "server error"})

    monkeypatch.setattr(star_checker.requests, "get", fake_get)

    assert star_checker.check_user_starred_repo("targetuser", "owner", "repo", "secret") is False


def test_count_user_stars_fetches_owner_repos_and_counts_matches(monkeypatch):
    checked_repos = []

    def fake_get(url, headers, timeout):
        assert "/users/owner/repos" in url
        return FakeResponse(payload=[{"name": "alpha"}, {"name": "beta"}, {"name": "gamma"}])

    def fake_check_user_starred_repo(username, owner, repo, token):
        checked_repos.append((username, owner, repo, token))
        return repo in {"alpha", "gamma"}

    monkeypatch.setattr(star_checker.requests, "get", fake_get)
    monkeypatch.setattr(star_checker, "check_user_starred_repo", fake_check_user_starred_repo)

    assert star_checker.count_user_stars("targetuser", "owner", "secret") == 2
    assert checked_repos == [
        ("targetuser", "owner", "alpha", "secret"),
        ("targetuser", "owner", "beta", "secret"),
        ("targetuser", "owner", "gamma", "secret"),
    ]


def test_count_user_stars_uses_supplied_repos_without_fetching_owner_repos(monkeypatch):
    def fail_if_fetching_repos(*args, **kwargs):
        raise AssertionError("owner repo list should not be fetched")

    monkeypatch.setattr(star_checker.requests, "get", fail_if_fetching_repos)
    monkeypatch.setattr(
        star_checker,
        "check_user_starred_repo",
        lambda username, owner, repo, token: repo == "beta",
    )

    assert star_checker.count_user_stars("targetuser", "owner", "secret", repos=["alpha", "beta"]) == 1


def test_check_wallet_exists_uses_local_cert_when_present(monkeypatch, tmp_path):
    cert = tmp_path / ".rustchain" / "node_cert.pem"
    cert.parent.mkdir()
    cert.write_text("certificate", encoding="utf-8")
    seen = {}

    def fake_get(url, verify, timeout):
        seen["url"] = url
        seen["verify"] = verify
        seen["timeout"] = timeout
        return FakeResponse(status_code=200)

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(star_checker.requests, "get", fake_get)

    assert star_checker.check_wallet_exists("rtc-wallet") is True
    assert seen == {
        "url": f"{star_checker.RUSTCHAIN_NODE_URL}/api/balance/rtc-wallet",
        "verify": str(cert),
        "timeout": 10,
    }
