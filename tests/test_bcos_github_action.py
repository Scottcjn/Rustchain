#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Unit tests for Bounty #2291 (`BCOS v2: Reusable GitHub Action for any repo`).
Verifies:
  1. `action.yml` and `.github/actions/bcos-scan/action.yml` define all required inputs and outputs
     (`trust_score`, `cert_id`, `tier_met`, `commitment`, `badge_url`, `verify_url`).
  2. `tools/bcos_action_runner.py` scans a repository, writes `$GITHUB_OUTPUT` and `$GITHUB_STEP_SUMMARY`,
     and formats the PR comment with the BCOS badge and 7-component breakdown table.
  3. `post_or_update_pr_comment()` idempotently creates or updates the existing BCOS PR comment.
  4. `submit_attestation()` posts the canonical BCOS v2 report to `/bcos/attest`.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
import sys
import tempfile
import urllib.request

ROOT_DIR = Path(__file__).resolve().parent.parent
TOOLS_DIR = ROOT_DIR / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import bcos_action_runner  # noqa: E402


def test_action_yml_defines_required_inputs_and_outputs():
    root_action = ROOT_DIR / "action.yml"
    sub_action = ROOT_DIR / ".github" / "actions" / "bcos-scan" / "action.yml"
    assert root_action.exists(), "Missing root action.yml"
    assert sub_action.exists(), "Missing .github/actions/bcos-scan/action.yml"

    for path in (root_action, sub_action):
        text = path.read_text(encoding="utf-8")
        assert 'using: "composite"' in text
        for req_input in ("tier:", "reviewer:", "node-url:", "github-token:", "post-pr-comment:", "attest-on-merge:"):
            assert req_input in text, f"Missing input {req_input} in {path}"
        for req_output in ("trust_score:", "cert_id:", "tier_met:", "commitment:", "badge_url:", "verify_url:"):
            assert req_output in text, f"Missing output {req_output} in {path}"


def test_write_github_outputs_and_format_pr_comment():
    sample_report = {
        "schema": "bcos-attestation/v2",
        "repo_name": "Scottcjn/Rustchain",
        "commit_sha": "abcdef1234567890abcdef1234567890abcdef12",
        "tier": "L1",
        "reviewer": "alice",
        "trust_score": 82,
        "tier_met": True,
        "cert_id": "BCOS-a1b2c3d4",
        "commitment": "a1b2c3d4" * 8,
        "score_breakdown": {
            "license_compliance": 18,
            "vulnerability_scan": 25,
            "static_analysis": 16,
            "sbom_completeness": 8,
            "dependency_freshness": 5,
            "test_evidence": 5,
            "review_attestation": 5,
        },
        "checks": {
            "license_compliance": {"passed": True},
            "vulnerability_scan": {"passed": True},
            "static_analysis": {"passed": True},
            "sbom_completeness": {"passed": True},
            "dependency_freshness": {"passed": True},
            "test_evidence": {"passed": True},
            "review_attestation": {"passed": True},
        },
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        out_file = Path(tmpdir) / "github_output.txt"
        sum_file = Path(tmpdir) / "github_summary.md"

        outputs = bcos_action_runner.write_github_outputs(
            report=sample_report,
            node_url="https://rustchain.org",
            github_output_path=str(out_file),
            github_summary_path=str(sum_file),
            attestation_result={"ok": True},
        )

        assert outputs["trust_score"] == "82"
        assert outputs["cert_id"] == "BCOS-a1b2c3d4"
        assert outputs["tier_met"] == "true"
        assert outputs["commitment"] == "a1b2c3d4" * 8
        assert outputs["badge_url"] == "https://rustchain.org/bcos/badge/BCOS-a1b2c3d4.svg"
        assert outputs["verify_url"] == "https://rustchain.org/bcos/verify/BCOS-a1b2c3d4"

        out_text = out_file.read_text(encoding="utf-8")
        assert "trust_score=82" in out_text
        assert "cert_id=BCOS-a1b2c3d4" in out_text
        assert "tier_met=true" in out_text

        sum_text = sum_file.read_text(encoding="utf-8")
        assert bcos_action_runner.COMMENT_MARKER in sum_text
        assert "https://rustchain.org/bcos/badge/BCOS-a1b2c3d4.svg" in sum_text
        assert "License Compliance (SPDX + OSI Deps)" in sum_text
        assert "**18 / 20**" in sum_text


def test_post_or_update_pr_comment_idempotent(monkeypatch):
    recorded_requests = []

    class DummyResponse:
        def __init__(self, payload):
            self._raw = json.dumps(payload).encode("utf-8")

        def read(self):
            return self._raw

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    def fake_urlopen(req, timeout=20, context=None):
        recorded_requests.append((req.get_method(), req.full_url, req.data))
        if req.get_method() == "GET":
            return DummyResponse([
                {"id": 777, "body": f"{bcos_action_runner.COMMENT_MARKER}\nOld BCOS report"}
            ])
        return DummyResponse({"id": 777, "html_url": "https://github.com/Scottcjn/Rustchain/pull/1#issuecomment-777"})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    res = bcos_action_runner.post_or_update_pr_comment(
        repo="Scottcjn/Rustchain",
        pr_number=1,
        token="dummy-token",
        body_markdown=f"{bcos_action_runner.COMMENT_MARKER}\nUpdated BCOS report",
    )
    assert res["id"] == 777
    assert len(recorded_requests) == 2
    assert recorded_requests[0][0] == "GET"
    assert recorded_requests[1][0] == "PATCH"
    assert recorded_requests[1][1].endswith("/repos/Scottcjn/Rustchain/issues/comments/777")


def test_submit_attestation_posts_to_bcos_attest(monkeypatch):
    captured = {}

    class DummyResponse:
        def read(self):
            return json.dumps({
                "ok": True,
                "cert_id": "BCOS-11223344",
                "verify_url": "https://rustchain.org/bcos/verify/BCOS-11223344",
            }).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    def fake_urlopen(req, timeout=20, context=None):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["headers"] = dict(req.header_items())
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return DummyResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    report = {
        "cert_id": "BCOS-11223344",
        "commitment": "11223344" * 8,
        "repo_name": "Scottcjn/Rustchain",
        "tier": "L1",
        "trust_score": 75,
    }
    resp = bcos_action_runner.submit_attestation(
        report=report,
        node_url="https://rustchain.org",
        admin_key="test-admin-key",
    )
    assert resp["ok"] is True
    assert captured["url"] == "https://rustchain.org/bcos/attest"
    assert captured["method"] == "POST"
    assert captured["body"]["report"]["cert_id"] == "BCOS-11223344"
