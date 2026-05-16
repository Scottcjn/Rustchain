# SPDX-License-Identifier: MIT
"""Unit tests for core BCOS engine helpers."""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "tools" / "bcos_engine.py"


def load_module():
    spec = importlib.util.spec_from_file_location("bcos_engine_tool", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_run_cmd_reports_missing_command_without_raising():
    module = load_module()

    rc, out, err = module._run_cmd(["definitely-not-a-real-bcos-command"])

    assert rc == -1
    assert out == ""
    assert "command not found" in err


def test_git_head_sha_returns_unknown_when_git_fails(tmp_path):
    module = load_module()

    assert module._git_head_sha(str(tmp_path)) == "unknown"


def test_detect_repo_name_parses_https_and_ssh_remotes(tmp_path):
    module = load_module()
    engine = module.BCOSEngine(str(tmp_path))

    with patch.object(module, "_run_cmd", return_value=(0, "https://github.com/owner/repo.git\n", "")):
        assert engine._detect_repo_name() == "owner/repo"

    with patch.object(module, "_run_cmd", return_value=(0, "git@github.com:owner/other.git\n", "")):
        assert engine._detect_repo_name() == "owner/other"


def test_detect_repo_name_falls_back_to_directory_name(tmp_path):
    module = load_module()
    engine = module.BCOSEngine(str(tmp_path))

    with patch.object(module, "_run_cmd", return_value=(1, "", "not a git repo")):
        assert engine._detect_repo_name() == tmp_path.name


def test_tier_met_requires_threshold_and_l2_reviewer(tmp_path):
    module = load_module()
    engine = module.BCOSEngine(str(tmp_path), tier="L1")
    engine.score_breakdown = {"review_attestation": 5, "test_evidence": 10, "license": 45}
    assert engine._tier_met() is True

    engine.score_breakdown = {"low": 59}
    assert engine._tier_met() is False

    l2_without_reviewer = module.BCOSEngine(str(tmp_path), tier="L2", reviewer="")
    l2_without_reviewer.score_breakdown = {"score": 100}
    assert l2_without_reviewer._tier_met() is False

    l2_with_reviewer = module.BCOSEngine(str(tmp_path), tier="L2", reviewer="reviewer")
    l2_with_reviewer.score_breakdown = {"score": 80}
    assert l2_with_reviewer._tier_met() is True


def test_run_all_adds_cert_id_and_commitment_after_checks(tmp_path):
    module = load_module()
    engine = module.BCOSEngine(str(tmp_path), tier="L0", reviewer="qa", commit_sha="abc123")

    with (
        patch.object(engine, "_check_spdx", side_effect=lambda: engine.score_breakdown.update({"license_compliance": 20})),
        patch.object(engine, "_check_semgrep", side_effect=lambda: engine.score_breakdown.update({"static_analysis": 20})),
        patch.object(engine, "_check_osv", side_effect=lambda: engine.score_breakdown.update({"vulnerability_scan": 25})),
        patch.object(engine, "_check_sbom", side_effect=lambda: engine.score_breakdown.update({"sbom_completeness": 10})),
        patch.object(engine, "_check_dep_freshness", side_effect=lambda: engine.score_breakdown.update({"dependency_freshness": 5})),
        patch.object(engine, "_check_test_evidence", side_effect=lambda: engine.score_breakdown.update({"test_evidence": 10})),
        patch.object(engine, "_check_review", side_effect=lambda: engine.score_breakdown.update({"review_attestation": 10})),
        patch.object(engine, "_detect_repo_name", return_value="owner/repo"),
    ):
        report = engine.run_all()

    assert report["schema"] == "bcos-attestation/v2"
    assert report["repo_name"] == "owner/repo"
    assert report["commit_sha"] == "abc123"
    assert report["trust_score"] == 100
    assert report["tier_met"] is True
    assert report["cert_id"].startswith("BCOS-")
    assert len(report["commitment"]) == 64
