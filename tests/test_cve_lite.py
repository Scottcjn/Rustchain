# SPDX-License-Identifier: MIT
"""Tests for tools/cve_lite.py — parsers, severity mapping, and scan flow.

Network is never touched: OSV calls are monkeypatched.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


@pytest.fixture()
def cve():
    p = Path(__file__).resolve().parents[1] / "tools" / "cve_lite.py"
    spec = importlib.util.spec_from_file_location("cve_lite", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_parse_requirements(cve):
    out = cve.parse_requirements(
        "requests==2.20.0\n# comment\nflask\n-r other.txt\ndjango==3.2.1  # pin\n"
    )
    assert ("PyPI", "requests", "2.20.0") in out
    assert ("PyPI", "django", "3.2.1") in out
    assert ("PyPI", "flask", None) in out
    assert all(name != "other.txt" for _, name, _ in out)


def test_parse_package_json_only_exact_versions(cve):
    out = cve.parse_package_json('{"dependencies":{"lodash":"4.17.11","x":"^1.0.0"},'
                                 '"devDependencies":{"jest":"29.0.0"}}')
    assert ("npm", "lodash", "4.17.11") in out
    assert ("npm", "jest", "29.0.0") in out
    # caret range is not an exact pin -> version None, still surfaced
    assert ("npm", "x", None) in out


def test_parse_package_lock_v2_and_v1(cve):
    v2 = '{"packages":{"":{"name":"root"},"node_modules/foo":{"version":"1.2.3"}}}'
    assert ("npm", "foo", "1.2.3") in cve.parse_package_lock(v2)
    v1 = '{"dependencies":{"bar":{"version":"0.9.0"}}}'
    assert ("npm", "bar", "0.9.0") in cve.parse_package_lock(v1)


def test_parse_cargo_and_go(cve):
    cargo = ('[[package]]\nname = "serde"\nversion = "1.0.0"\n'
             'source = "registry+https://github.com/rust-lang/crates.io-index"\n')
    assert ("crates.io", "serde", "1.0.0") in cve.parse_cargo_lock(cargo)
    go = "module x\n\nrequire github.com/foo/bar v1.4.2\n"
    assert ("Go", "github.com/foo/bar", "v1.4.2") in cve.parse_go_mod(go)


def test_cargo_skips_git_and_workspace_crates(cve):
    text = (
        '[[package]]\nname = "registrydep"\nversion = "1.0.0"\n'
        'source = "registry+https://github.com/rust-lang/crates.io-index"\n\n'
        '[[package]]\nname = "gitdep"\nversion = "0.1.0"\n'
        'source = "git+https://github.com/x/gitdep#abc"\n\n'
        '[[package]]\nname = "myworkspacecrate"\nversion = "0.0.1"\n'  # no source
    )
    out = cve.parse_cargo_lock(text)
    assert ("crates.io", "registrydep", "1.0.0") in out
    assert all(n != "gitdep" for _, n, _ in out)            # git source skipped
    assert all(n != "myworkspacecrate" for _, n, _ in out)  # local crate skipped


def test_requirements_extras_are_pinned(cve):
    out = cve.parse_requirements("requests[security]==2.20.0\n")
    assert ("PyPI", "requests", "2.20.0") in out  # extras must not break pin detection


def test_pyproject_optional_dependencies_parsed(cve):
    text = (
        "[project]\n"
        'dependencies = ["requests==2.20.0"]\n'
        "\n[project.optional-dependencies]\n"
        'test = ["pytest==7.0.0", "coverage>=6.0"]\n'
    )
    out = cve.parse_pyproject(text)
    assert ("PyPI", "pytest", "7.0.0") in out      # optional-deps group pinned
    assert ("PyPI", "coverage", None) in out       # range -> unpinned


def test_cvss_rejects_vector_without_scope(cve):
    # A vector missing S must be rejected (None), not silently assumed S:U,
    # so it falls through to UNKNOWN and fails closed.
    assert cve._cvss3_base_from_vector("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/C:H/I:H/A:H") is None


def test_cvss3_calculator_known_vectors(cve):
    # Canonical FIRST.org examples.
    assert cve._cvss3_base_from_vector("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H") == 9.8
    assert cve._cvss3_base_from_vector("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H") == 7.5
    assert cve._cvss3_base_from_vector("CVSS:3.1/AV:L/AC:H/PR:H/UI:R/S:U/C:L/I:N/A:N") == 1.8
    # Scope-changed inflates the score.
    assert cve._cvss3_base_from_vector("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H") == 10.0
    # Malformed / incomplete vector -> None, not a crash.
    assert cve._cvss3_base_from_vector("CVSS:3.1/AV:N/oops") is None


def test_severity_from_cvss_and_label(cve):
    crit = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
    assert cve.extract_severity({"severity": [{"type": "CVSS_V3", "score": crit}]}) == "CRITICAL"
    assert cve.extract_severity({"severity": [{"score": "7.5"}]}) == "HIGH"
    assert cve.extract_severity({"severity": [{"score": "5.0"}]}) == "MEDIUM"
    # GHSA label normalization (MODERATE -> MEDIUM) when no CVSS vector present.
    assert cve.extract_severity({"database_specific": {"severity": "MODERATE"}}) == "MEDIUM"
    assert cve.extract_severity({"database_specific": {"severity": "LOW"}}) == "LOW"
    assert cve.extract_severity({}) == "UNKNOWN"


def test_severity_rank_orders_worst_first(cve):
    assert cve._severity_rank("CRITICAL") < cve._severity_rank("HIGH") < cve._severity_rank("LOW")


def test_discover_dedupes_and_separates_unpinned(cve, tmp_path):
    (tmp_path / "requirements.txt").write_text("requests==2.20.0\nflask\n")
    sub = tmp_path / "svc"
    sub.mkdir()
    (sub / "requirements.txt").write_text("requests==2.20.0\n")  # dup across files
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "requirements.txt").write_text("evil==6.6.6\n")  # must be skipped
    pinned, unpinned = cve.discover_dependencies(str(tmp_path))
    assert ("PyPI", "requests", "2.20.0") in pinned
    assert pinned.count(("PyPI", "requests", "2.20.0")) == 1  # deduped
    assert ("PyPI", "flask") in unpinned
    assert all(n != "evil" for _, n, _ in pinned)  # node_modules skipped


def test_scan_offline_skips_network(cve, tmp_path, monkeypatch):
    (tmp_path / "requirements.txt").write_text("requests==2.20.0\n")

    def boom(*a, **k):
        raise AssertionError("network must not be touched in offline mode")

    monkeypatch.setattr(cve, "query_osv_batch", boom)
    report = cve.scan(str(tmp_path), offline=True)
    assert report["offline"] is True
    assert report["scanned"] == 1
    assert report["vulnerabilities"] == []


def test_scan_reports_vuln_and_threshold(cve, tmp_path, monkeypatch):
    (tmp_path / "requirements.txt").write_text("requests==2.20.0\n")
    dep = ("PyPI", "requests", "2.20.0")
    monkeypatch.setattr(cve, "query_osv_batch", lambda deps, timeout: {dep: ["GHSA-x"]})
    monkeypatch.setattr(cve, "fetch_vuln_detail",
                        lambda vid, timeout: {"id": vid, "summary": "boom",
                                              "severity": [{"score": "9.8"}]})
    report = cve.scan(str(tmp_path), severity_threshold="HIGH")
    assert len(report["vulnerabilities"]) == 1
    v = report["vulnerabilities"][0]
    assert v["severity"] == "CRITICAL"
    assert v["at_or_above_threshold"] is True


def test_scan_below_threshold_not_flagged(cve, tmp_path, monkeypatch):
    (tmp_path / "requirements.txt").write_text("requests==2.20.0\n")
    dep = ("PyPI", "requests", "2.20.0")
    monkeypatch.setattr(cve, "query_osv_batch", lambda deps, timeout: {dep: ["GHSA-y"]})
    monkeypatch.setattr(cve, "fetch_vuln_detail",
                        lambda vid, timeout: {"id": vid, "severity": [{"score": "3.1"}]})
    report = cve.scan(str(tmp_path), severity_threshold="HIGH")
    assert report["vulnerabilities"][0]["severity"] == "LOW"
    assert report["vulnerabilities"][0]["at_or_above_threshold"] is False


def test_scan_handles_osv_unavailable(cve, tmp_path, monkeypatch):
    (tmp_path / "requirements.txt").write_text("requests==2.20.0\n")

    def unavailable(deps, timeout):
        raise cve.OSVUnavailable("connection refused")

    monkeypatch.setattr(cve, "query_osv_batch", unavailable)
    report = cve.scan(str(tmp_path))
    assert report["osv_available"] is False
    assert "unavailable" in report["note"].lower()


def test_pyproject_only_double_equals_is_pinned(cve):
    text = (
        "[project]\n"
        'dependencies = ["requests==2.20.0", "flask>=1.0", "click"]\n'
        "\n[tool.poetry.dependencies]\n"
        'python = "^3.9"\n'
        'django = "^3.2.1"\n'
        'urllib3 = "==1.25.0"\n'
    )
    out = cve.parse_pyproject(text)
    assert ("PyPI", "requests", "2.20.0") in out          # == -> pinned
    assert ("PyPI", "flask", None) in out                 # >= -> unpinned
    assert ("PyPI", "click", None) in out                 # bare -> unpinned
    assert ("PyPI", "django", None) in out                # poetry caret -> unpinned
    assert ("PyPI", "urllib3", "1.25.0") in out           # poetry == -> pinned
    assert all(n != "python" for _, n, _ in out)          # python requirement skipped


def test_package_lock_v1_nested(cve):
    lock = ('{"dependencies":{"a":{"version":"1.0.0",'
            '"dependencies":{"b":{"version":"2.0.0"}}}}}')
    out = cve.parse_package_lock(lock)
    assert ("npm", "a", "1.0.0") in out
    assert ("npm", "b", "2.0.0") in out  # transitive recursion


def test_batch_truncation_fails_closed(cve, monkeypatch):
    # OSV returns fewer results than queries -> must raise, not drop deps.
    monkeypatch.setattr(cve, "_http_json", lambda url, payload, timeout: {"results": []})
    with pytest.raises(cve.OSVUnavailable):
        cve.query_osv_batch([("PyPI", "x", "1.0.0")], timeout=5)


def test_confirmed_vuln_with_failed_detail_fails_closed(cve, tmp_path, monkeypatch):
    (tmp_path / "requirements.txt").write_text("requests==2.20.0\n")
    dep = ("PyPI", "requests", "2.20.0")
    monkeypatch.setattr(cve, "query_osv_batch", lambda deps, timeout: {dep: ["GHSA-x"]})
    # detail fetch failed -> severity UNKNOWN, but it is a CONFIRMED vuln.
    monkeypatch.setattr(cve, "fetch_vuln_detail",
                        lambda vid, timeout: {"id": vid, "_fetch_failed": True})
    report = cve.scan(str(tmp_path), severity_threshold="LOW")
    v = report["vulnerabilities"][0]
    assert v["severity"] == "UNKNOWN"
    assert v["detail_unavailable"] is True
    assert v["at_or_above_threshold"] is True  # fail closed
    assert report["detail_fetch_failures"] == 1


def test_online_only_unpinned_is_not_silent_clean(cve, tmp_path, monkeypatch):
    (tmp_path / "requirements.txt").write_text("flask\n")  # no exact pin

    def boom(*a, **k):
        raise AssertionError("should not query OSV with nothing pinned")

    monkeypatch.setattr(cve, "query_osv_batch", boom)
    report = cve.scan(str(tmp_path))  # online
    assert report["scanned"] == 0
    assert "unpinned" in report["note"].lower()


def test_invalid_threshold_defaults_to_low(cve, tmp_path, monkeypatch):
    (tmp_path / "requirements.txt").write_text("requests==2.20.0\n")
    dep = ("PyPI", "requests", "2.20.0")
    monkeypatch.setattr(cve, "query_osv_batch", lambda deps, timeout: {dep: ["GHSA-y"]})
    monkeypatch.setattr(cve, "fetch_vuln_detail",
                        lambda vid, timeout: {"id": vid, "severity": [{"score": "3.1"}]})
    # bogus threshold defaults to LOW, so a LOW finding IS flagged (and a
    # fall-through rank bug would also flag it — this pins the default path)
    report = cve.scan(str(tmp_path), severity_threshold="BOGUS")
    assert report["vulnerabilities"][0]["severity"] == "LOW"
    assert report["vulnerabilities"][0]["at_or_above_threshold"] is True  # default LOW


def test_main_fails_closed_when_osv_unavailable_online(cve, tmp_path, monkeypatch):
    (tmp_path / "requirements.txt").write_text("requests==2.20.0\n")
    monkeypatch.setattr(cve, "query_osv_batch",
                        lambda deps, timeout: (_ for _ in ()).throw(cve.OSVUnavailable("down")))
    assert cve.main(["scan", str(tmp_path), "--json"]) == 1   # online + unavailable -> fail closed
    assert cve.main(["scan", str(tmp_path), "--offline", "--json"]) == 0  # offline opt-out -> 0


def test_main_exit_codes(cve, tmp_path, monkeypatch):
    (tmp_path / "requirements.txt").write_text("requests==2.20.0\n")
    # clean offline scan -> 0
    assert cve.main(["scan", str(tmp_path), "--offline", "--json"]) == 0
    # bad path -> 2
    assert cve.main(["scan", str(tmp_path / "nope")]) == 2
    # vuln at threshold -> 1
    dep = ("PyPI", "requests", "2.20.0")
    monkeypatch.setattr(cve, "query_osv_batch", lambda deps, timeout: {dep: ["GHSA-z"]})
    monkeypatch.setattr(cve, "fetch_vuln_detail",
                        lambda vid, timeout: {"id": vid, "severity": [{"score": "9.0"}]})
    assert cve.main(["scan", str(tmp_path), "--severity", "HIGH", "--json"]) == 1
