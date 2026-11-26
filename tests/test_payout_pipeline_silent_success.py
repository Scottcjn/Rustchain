#!/usr/bin/env python3
"""
Regression test suite for Bounty #16471 (Payout Pipeline Silent-Success Audit):
Verifies all silent-success fixes in `scripts/pr_review_gate.py`.
"""

import io
import json
import os
from pathlib import Path
import sys
import urllib.error

SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import pr_review_gate  # noqa: E402


def test_transient_http_503_on_search_issues_raises_instead_of_bypassing_cap(monkeypatch):
    """Finding 2: HTTP 503/403 on `/search/issues` must raise GateTransientError, never default to 0 < CAP."""
    monkeypatch.setattr(pr_review_gate, "NUM", "9001")
    monkeypatch.setattr(pr_review_gate, "CAP", 15)

    calls = []

    def fake_api(path, method="GET", data=None):
        calls.append((method, path, data))
        if path == "/repos/Scottcjn/rustchain-bounties/issues/9001":
            return {
                "state": "open",
                "labels": [],
                "title": "Bounty #73 claim: code review of PR #500",
                "body": "Reviewed PR #500. Wallet: RTCfe0ac752b80e543048c0d91e7dddd1277678b8a5",
                "user": {"login": "alice"},
            }
        if path.startswith("/repos/Scottcjn/Rustchain/pulls/500/reviews"):
            return [
                {
                    "user": {"login": "alice"},
                    "submitted_at": "2026-11-11T00:00:00Z",
                    "body": "Ref: `node/utxo_db.py` L:42 — SQLite snapshot race condition under concurrent WAL writes (" + ("x" * 100) + ")",
                }
            ]
        if path.startswith("/repos/Scottcjn/Rustchain/pulls/500/comments"):
            return [{"user": {"login": "alice"}, "body": "inline comment"}]
        if path.startswith("/search/issues"):
            raise pr_review_gate.GateTransientError("HTTP 403 rate limit on /search/issues")
        return {}

    monkeypatch.setattr(pr_review_gate, "api", fake_api)

    raised = False
    try:
        pr_review_gate.main()
    except pr_review_gate.GateTransientError:
        raised = True
    assert raised, "Expected GateTransientError when /search/issues fails"

    # Verify neither bounty-eligible nor gate-processed was applied!
    post_labels = [c for c in calls if c[0] == "POST" and "/labels" in c[1]]
    assert post_labels == [], f"No labels should be applied on transient failure, got {post_labels}"


def test_premature_gate_processed_not_applied_when_reviews_fail(monkeypatch):
    """Finding 1 (#16710): Transient failure during `/reviews` must not leave `gate-processed` on the issue."""
    monkeypatch.setattr(pr_review_gate, "NUM", "9002")
    calls = []

    def fake_api(path, method="GET", data=None):
        calls.append((method, path, data))
        if path == "/repos/Scottcjn/rustchain-bounties/issues/9002":
            return {
                "state": "open",
                "labels": [],
                "title": "Code review claim for PR #501",
                "body": "RTCfe0ac752b80e543048c0d91e7dddd1277678b8a5",
                "user": {"login": "bob"},
            }
        if path.startswith("/repos/Scottcjn/Rustchain/pulls/501/reviews"):
            raise pr_review_gate.GateTransientError("HTTP 502 Bad Gateway")
        return {}

    monkeypatch.setattr(pr_review_gate, "api", fake_api)

    raised = False
    try:
        pr_review_gate.main()
    except pr_review_gate.GateTransientError:
        raised = True
    assert raised
    post_labels = [c for c in calls if c[0] == "POST" and "/labels" in c[1]]
    assert post_labels == []


def test_transient_error_on_inline_comments_does_not_auto_close_valid_claim(monkeypatch):
    """Finding 3: Transient error on `/pulls/{pr}/comments` must raise instead of treating inline comments as []."""
    monkeypatch.setattr(pr_review_gate, "NUM", "9003")
    calls = []

    def fake_api(path, method="GET", data=None):
        calls.append((method, path, data))
        if path == "/repos/Scottcjn/rustchain-bounties/issues/9003":
            return {
                "state": "open",
                "labels": [],
                "title": "Code review claim for PR #502",
                "body": "RTCfe0ac752b80e543048c0d91e7dddd1277678b8a5",
                "user": {"login": "carol"},
            }
        if path.startswith("/repos/Scottcjn/Rustchain/pulls/502/reviews"):
            return [
                {
                    "user": {"login": "carol"},
                    "submitted_at": "2026-11-11T00:00:00Z",
                    "body": "Ref: `node/server.py` L:12 — see inline comments.",
                }
            ]
        if path.startswith("/repos/Scottcjn/Rustchain/pulls/502/comments"):
            raise pr_review_gate.GateTransientError("HTTP 503 Service Unavailable")
        return {}

    monkeypatch.setattr(pr_review_gate, "api", fake_api)

    raised = False
    try:
        pr_review_gate.main()
    except pr_review_gate.GateTransientError:
        raised = True
    assert raised
    patch_calls = [c for c in calls if c[0] == "PATCH"]
    assert patch_calls == [], "Claim must NOT be closed on transient /comments error"


def test_multiple_reviews_by_same_author_uses_max_body_len(monkeypatch):
    """Finding 4: Author with short initial review followed by >=120 char substantive review is approved."""
    monkeypatch.setattr(pr_review_gate, "NUM", "9004")
    calls = []

    def fake_api(path, method="GET", data=None):
        calls.append((method, path, data))
        if path == "/repos/Scottcjn/rustchain-bounties/issues/9004":
            return {
                "state": "open",
                "labels": [],
                "title": "Code review claim for PR #503",
                "body": "RTCfe0ac752b80e543048c0d91e7dddd1277678b8a5",
                "user": {"login": "dave"},
            }
        if path.startswith("/repos/Scottcjn/Rustchain/pulls/503/reviews"):
            return [
                {
                    "user": {"login": "dave"},
                    "submitted_at": "2026-11-11T00:01:00Z",
                    "body": "Checking this PR now.",
                },
                {
                    "user": {"login": "dave"},
                    "submitted_at": "2026-11-11T00:05:00Z",
                    "body": (
                        "Ref: `node/utxo_endpoints.py` L:95 — `compute_state_root()` and `count_unspent()` run on "
                        "separate implicit transactions without pinning a read snapshot, risking mismatched root/count."
                    ),
                },
            ]
        if path.startswith("/repos/Scottcjn/Rustchain/pulls/503/comments"):
            return []
        if path.startswith("/search/issues"):
            return {"total_count": 2}
        return {}

    monkeypatch.setattr(pr_review_gate, "api", fake_api)
    rc = pr_review_gate.main()
    assert rc == 0
    labels_applied = [c[2]["labels"][0] for c in calls if c[0] == "POST" and "/labels" in c[1]]
    assert "bounty-eligible" in labels_applied
    assert "gate-processed" in labels_applied
    # Verify gate-processed was applied AFTER bounty-eligible
    assert labels_applied.index("bounty-eligible") < labels_applied.index("gate-processed")
