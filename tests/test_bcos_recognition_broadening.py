# SPDX-License-Identifier: MIT
"""Regression tests for BCOS recognition broadening (2026-06).

These lock in two properties:

1. The engine now *recognizes* more source languages, OSI license identifiers,
   and test/CI conventions than the legacy hard-coded sets.
2. Broadening never *lowers* a repository's score — the SPDX subscore is the
   max of the legacy and extended views, retroactively honoring prior scores.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


@pytest.fixture()
def bcos_engine_module():
    module_path = Path(__file__).resolve().parents[1] / "tools" / "bcos_engine.py"
    spec = importlib.util.spec_from_file_location("bcos_engine", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_extended_extension_set_is_a_superset_of_legacy(bcos_engine_module):
    legacy = bcos_engine_module.CODE_EXTS
    extended = bcos_engine_module.CODE_EXTS_EXTENDED
    assert legacy <= extended
    # A few languages the legacy set never recognized.
    for ext in (".scala", ".php", ".ex", ".vue", ".clj"):
        assert ext in extended
        assert ext not in legacy


def test_osi_license_list_recognizes_more_identifiers(bcos_engine_module):
    osi = bcos_engine_module.OSI_LICENSES
    for lic in ("EPL-2.0", "CC0-1.0", "MPL-2.0", "GPL-3.0-or-later",
                "Apache-2.0 WITH LLVM-exception"):
        assert lic in osi


def test_spdx_score_never_below_legacy_view(bcos_engine_module, tmp_path):
    """A repo with un-headered files in a newly-recognized language must not
    score lower than the legacy engine (which ignored that language)."""
    # Legacy-recognized file WITH an SPDX header -> legacy view = 100% coverage.
    (tmp_path / "main.py").write_text("# SPDX-License-Identifier: MIT\nprint(1)\n")
    # Newly-recognized language file WITHOUT a header. Naively counting it would
    # drag coverage below 100%, but the max-guard must protect the legacy score.
    (tmp_path / "app.scala").write_text("object App { def main(a: Array[String]) = () }\n")

    engine = bcos_engine_module.BCOSEngine(str(tmp_path), commit_sha="abc123")
    engine._check_spdx()
    lic = engine.checks["license_compliance"]

    assert lic["spdx_coverage_pct_legacy"] == 100.0
    # Extended view sees the unheadered .scala file -> lower raw coverage...
    assert lic["spdx_coverage_pct_extended"] < 100.0
    # ...but the scored SPDX points must equal the legacy (full) credit.
    # license_compliance = spdx_pts (max view) + dep_score; isolate spdx_pts.
    assert engine.score_breakdown["license_compliance"] >= 10


def test_test_evidence_recognizes_makefile_and_inline_rust(bcos_engine_module, tmp_path):
    # Makefile with a `test:` target — a real harness the fixed list missed.
    (tmp_path / "Makefile").write_text("build:\n\tcc x.c\ntest:\n\t./run-tests\n")
    # Idiomatic inline Rust test in a normal source file (not *_test.rs).
    (tmp_path / "lib.rs").write_text(
        "pub fn add(a: i32, b: i32) -> i32 { a + b }\n"
        "#[cfg(test)]\nmod tests { #[test] fn t() { assert_eq!(2, 1 + 1); } }\n"
    )

    engine = bcos_engine_module.BCOSEngine(str(tmp_path), commit_sha="abc123")
    engine._check_test_evidence()
    ev = engine.checks["test_evidence"]

    assert ev["passed"] is True
    assert "Makefile[test]" in ev["test_configs"]
    assert ev["test_file_count"] >= 1  # inline Rust test recognized
    assert engine.score_breakdown["test_evidence"] >= 5


def test_npm_init_placeholder_test_script_is_ignored(bcos_engine_module, tmp_path):
    (tmp_path / "package.json").write_text(
        '{"scripts": {"test": "echo \\"Error: no test specified\\" && exit 1"}}'
    )
    engine = bcos_engine_module.BCOSEngine(str(tmp_path), commit_sha="abc123")
    engine._check_test_evidence()
    assert "package.json[scripts.test]" not in engine.checks["test_evidence"]["test_configs"]
