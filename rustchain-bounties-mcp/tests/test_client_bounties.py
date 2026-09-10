"""Tests for GitHub-backed bounty discovery."""

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rustchain_bounties_mcp.client import RustChainClient


class AsyncContextManager:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, *args):
        return None


class MockResponse:
    def __init__(self, data, status=200):
        self._data = data
        self.status = status

    async def json(self):
        return self._data

    async def text(self):
        return ""


def github_issue(number, title, labels):
    return {
        "number": number,
        "title": title,
        "html_url": f"https://github.com/Scottcjn/rustchain-bounties/issues/{number}",
        "state": "open",
        "labels": [{"name": label} for label in labels],
        "body": "test issue",
    }


def test_parser_rejects_non_bounty_administrative_issue():
    issue = github_issue(16884, "[WALLET] Register payout identity", [])

    assert RustChainClient._parse_github_issue(issue) is None


def test_parser_keeps_labeled_bounty_without_numeric_reward():
    issue = github_issue(121, "[BOUNTY] SEO audit fix pack", ["bounty", "open"])

    result = RustChainClient._parse_github_issue(issue)

    assert result is not None
    assert result.issue_number == 121
    assert result.reward_rtc == 0


def test_parser_keeps_title_reward_when_label_is_missing():
    issue = github_issue(42, "Fix the widget — 7 RTC", [])

    result = RustChainClient._parse_github_issue(issue)

    assert result is not None
    assert result.reward_rtc == 7


@pytest.mark.asyncio
async def test_fetch_filters_github_query_and_defensively_skips_non_bounties():
    response = MockResponse([
        github_issue(16884, "[WALLET] Register payout identity", []),
        github_issue(520, "[Achievement] Bug Hunter — 3 RTC", ["bounty"]),
    ])
    session = MagicMock()
    session.get = MagicMock(return_value=AsyncContextManager(response))
    client = RustChainClient(session=session)

    results = await client._fetch_bounties_from_github(limit=20)

    assert [result.issue_number for result in results] == [520]
    assert session.get.call_args.kwargs["params"] == {
        "state": "open",
        "labels": "bounty",
        "per_page": 20,
    }
