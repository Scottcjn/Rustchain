# SPDX-License-Identifier: MIT

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture()
def bcos_engine_module():
    module_path = Path(__file__).resolve().parents[1] / "tools" / "bcos_engine.py"
    spec = importlib.util.spec_from_file_location("bcos_engine", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_run_cmd_handles_success_missing_binary_and_timeout(
    bcos_engine_module,
    monkeypatch,
):
    def fake_success(cmd, capture_output, text, timeout):
        assert cmd == ["tool", "--json"]
        assert capture_output is True
        assert text is True
        assert timeout == 7
        return SimpleNamespace(returncode=0, stdout="out", stderr="err")

    monkeypatch.setattr(bcos_engine_module.subprocess, "run", fake_success)
    assert bcos_engine_module._run_cmd(["tool", "--json"], timeout=7) == (
        0,
        "out",
        "err",
    )

    def fake_missing(_cmd, capture_output, text, timeout):
        raise FileNotFoundError

    monkeypatch.setattr(bcos_engine_module.subprocess, "run", fake_missing)
    assert bcos_engine_module._run_cmd(["missing-tool"])[0:2] == (-1, "")
    assert "command not found: missing-tool" in bcos_engine_module._run_cmd(
        ["missing-tool"]
    )[2]

    def fake_timeout(cmd, capture_output, text, timeout):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)

    monkeypatch.setattr(bcos_engine_module.subprocess, "run", fake_timeout)
    rc, stdout, stderr = bcos_engine_module._run_cmd(["slow", "scan"], timeout=3)
    assert rc == -2
    assert stdout == ""
    assert "timeout after 3s: slow scan" == stderr


def test_repo_name_detection_parses_github_remotes(bcos_engine_module, tmp_path, monkeypatch):
    engine = bcos_engine_module.BCOSEngine(str(tmp_path), commit_sha="abc123")

    monkeypatch.setattr(
        bcos_engine_module,
        "_run_cmd",
        lambda _cmd: (0, "https://github.com/acme/widgets.git\n", ""),
    )
    assert engine._detect_repo_name() == "acme/widgets"

    monkeypatch.setattr(
        bcos_engine_module,
        "_run_cmd",
        lambda _cmd: (0, "git@github.com:scottcjn/rustchain.git\n", ""),
    )
    assert engine._detect_repo_name() == "scottcjn/rustchain"

    monkeypatch.setattr(bcos_engine_module, "_run_cmd", lambda _cmd: (1, "", "no git"))
    assert engine._detect_repo_name() == tmp_path.name


def test_tier_met_uses_thresholds_and_requires_l2_reviewer(
    bcos_engine_module,
    tmp_path,
):
    engine = bcos_engine_module.BCOSEngine(str(tmp_path), tier="L1", commit_sha="abc123")
    engine.score_breakdown = {"license_compliance": 59}
    assert engine._tier_met() is False

    engine.score_breakdown = {"license_compliance": 60}
    assert engine._tier_met() is True

    engine.tier = "L2"
    engine.score_breakdown = {"license_compliance": 90}
    engine.reviewer = ""
    assert engine._tier_met() is False

    engine.reviewer = "reviewer"
    assert engine._tier_met() is True


def test_dep_license_scoring_handles_osi_and_fallback(
    bcos_engine_module,
    tmp_path,
    monkeypatch,
):
    engine = bcos_engine_module.BCOSEngine(str(tmp_path), commit_sha="abc123")
    license_report = [
        {"Name": "one", "License": "MIT License"},
        {"Name": "two", "License": "Apache-2.0"},
        {"Name": "three", "License": "Proprietary"},
    ]
    monkeypatch.setattr(
        bcos_engine_module,
        "_run_cmd",
        lambda _cmd, timeout=30: (0, json.dumps(license_report), ""),
    )
    assert engine._check_dep_licenses() == 6

    monkeypatch.setattr(
        bcos_engine_module,
        "_run_cmd",
        lambda _cmd, timeout=30: (1, "", "missing"),
    )
    assert engine._check_dep_licenses() == 5


def test_sbom_check_scores_generated_sbom_and_manifests(
    bcos_engine_module,
    tmp_path,
    monkeypatch,
):
    (tmp_path / "requirements.txt").write_text("pytest\n")
    (tmp_path / "package.json").write_text("{}")
    engine = bcos_engine_module.BCOSEngine(str(tmp_path), commit_sha="abc123")

    def fake_run_cmd(cmd, timeout=60):
        assert cmd[0] == "cyclonedx-py"
        return (0, '{"bomFormat": "CycloneDX"}', "")

    monkeypatch.setattr(bcos_engine_module, "_run_cmd", fake_run_cmd)

    engine._check_sbom()

    check = engine.checks["sbom_completeness"]
    assert check["passed"] is True
    assert check["sbom_generated"] is True
    assert len(check["sbom_hash"]) == 64
    assert check["dependency_manifests"] == ["requirements.txt", "package.json"]
    assert engine.score_breakdown["sbom_completeness"] == 9


def test_test_evidence_detects_tests_ci_and_pytest_config(
    bcos_engine_module,
    tmp_path,
):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_sample.py").write_text("def test_sample():\n    assert True\n")
    workflow_dir = tmp_path / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    (workflow_dir / "ci.yml").write_text("name: CI\n")
    (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")

    engine = bcos_engine_module.BCOSEngine(str(tmp_path), commit_sha="abc123")

    engine._check_test_evidence()

    check = engine.checks["test_evidence"]
    assert check["passed"] is True
    assert check["test_dirs"] == ["tests"]
    assert check["test_file_count"] >= 1
    assert check["ci_configs"] == [".github/workflows"]
    assert check["test_configs"] == ["pyproject.toml[pytest]"]
    assert engine.score_breakdown["test_evidence"] == 10


def test_run_all_builds_commitment_and_caps_scores(
    bcos_engine_module,
    tmp_path,
    monkeypatch,
):
    def set_check(name, score):
        def _set(engine):
            engine.checks[name] = {"passed": True}
            engine.score_breakdown[name] = score

        return _set

    monkeypatch.setattr(bcos_engine_module.BCOSEngine, "_detect_repo_name", lambda self: "owner/repo")
    monkeypatch.setattr(
        bcos_engine_module.BCOSEngine,
        "_check_spdx",
        set_check("license_compliance", 25),
    )
    monkeypatch.setattr(
        bcos_engine_module.BCOSEngine,
        "_check_semgrep",
        set_check("static_analysis", 19),
    )
    monkeypatch.setattr(
        bcos_engine_module.BCOSEngine,
        "_check_osv",
        set_check("vulnerability_scan", 24),
    )
    monkeypatch.setattr(
        bcos_engine_module.BCOSEngine,
        "_check_sbom",
        set_check("sbom_completeness", 8),
    )
    monkeypatch.setattr(
        bcos_engine_module.BCOSEngine,
        "_check_dep_freshness",
        set_check("dependency_freshness", 4),
    )
    monkeypatch.setattr(
        bcos_engine_module.BCOSEngine,
        "_check_test_evidence",
        set_check("test_evidence", 9),
    )
    monkeypatch.setattr(
        bcos_engine_module.BCOSEngine,
        "_check_review",
        set_check("review_attestation", 5),
    )

    report = bcos_engine_module.scan_repo(
        str(tmp_path),
        tier="L1",
        reviewer="reviewer",
        commit_sha="abc123",
    )

    assert report["schema"] == "bcos-attestation/v2"
    assert report["repo_name"] == "owner/repo"
    assert report["commit_sha"] == "abc123"
    assert report["score_breakdown"]["license_compliance"] == 20
    assert report["trust_score"] == 89
    assert report["tier_met"] is True
    assert report["cert_id"].startswith("BCOS-")
    assert len(report["commitment"]) == 64
