# SPDX-License-Identifier: MIT
"""Unit tests for the attestation fuzz corpus manager."""

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "tools" / "fuzz" / "corpus_manager.py"


def load_module():
    spec = importlib.util.spec_from_file_location("fuzz_corpus_manager", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def manager(tmp_path):
    module = load_module()
    return module, module.FuzzCorpusManager(str(tmp_path / "corpus.db"))


def store_sample(mgr, module, payload, category=None, severity=None, crash_type="ValueError", trace="line 1"):
    return mgr.store_crash(
        payload_data=payload,
        category=category or module.PayloadCategory.TYPE_CONFUSION,
        severity=severity or module.CrashSeverity.HIGH,
        crash_type=crash_type,
        stack_trace=trace,
        notes="sample",
    )


def test_store_get_and_duplicate_rejection(tmp_path):
    module, mgr = manager(tmp_path)

    assert store_sample(mgr, module, '{"miner": 1}') is True
    assert store_sample(mgr, module, '{"miner": 1}') is False

    payload_hash = mgr._compute_hash('{"miner": 1}')
    crash = mgr.get_crash(payload_hash)
    assert crash is not None
    assert crash.payload_hash == payload_hash
    assert crash.category is module.PayloadCategory.TYPE_CONFUSION
    assert crash.severity is module.CrashSeverity.HIGH
    assert crash.minimized is False
    assert mgr.get_crash("missing") is None


def test_list_stats_and_bookkeeping_filters(tmp_path):
    module, mgr = manager(tmp_path)
    store_sample(
        mgr,
        module,
        "payload-a",
        category=module.PayloadCategory.MISSING_FIELDS,
        severity=module.CrashSeverity.CRITICAL,
        trace="shared\ntrace",
    )
    store_sample(
        mgr,
        module,
        "payload-b",
        category=module.PayloadCategory.ENCODING_ISSUES,
        severity=module.CrashSeverity.LOW,
        trace="other",
    )
    payload_hash = mgr._compute_hash("payload-a")

    assert mgr.mark_minimized(payload_hash, "small") is True
    assert mgr.mark_regression_tested(payload_hash, "passed") is True
    assert mgr.mark_minimized("missing", "small") is False

    critical = mgr.list_crashes(severity=module.CrashSeverity.CRITICAL)
    encoding = mgr.list_crashes(category=module.PayloadCategory.ENCODING_ISSUES)
    stats = mgr.get_stats()

    assert [c.payload_data for c in critical] == ["small"]
    assert [c.payload_data for c in encoding] == ["payload-b"]
    assert stats["total_crashes"] == 2
    assert stats["category_breakdown"]["missing_fields"] == 1
    assert stats["severity_breakdown"]["critical"] == 1
    assert stats["minimized_count"] == 1
    assert stats["regression_tested_count"] == 1


def test_export_import_and_regression_suite(tmp_path):
    module, mgr = manager(tmp_path)
    store_sample(mgr, module, "low", severity=module.CrashSeverity.LOW)
    store_sample(mgr, module, "high", severity=module.CrashSeverity.HIGH)
    store_sample(mgr, module, "critical", severity=module.CrashSeverity.CRITICAL)
    export_path = tmp_path / "corpus.json"

    mgr.export_corpus(str(export_path))
    import_dir = tmp_path / "imported"
    import_dir.mkdir()
    _, imported = manager(import_dir)

    assert imported.import_corpus(str(export_path)) == 3
    assert imported.import_corpus(str(export_path)) == 0
    suite_payloads = [payload for _hash, payload in imported.get_regression_suite()]
    assert set(suite_payloads) == {"critical", "high"}


def test_deduplicate_similar_crashes_removes_same_type_only(tmp_path):
    module, mgr = manager(tmp_path)
    common_trace = "File a.py\nline 10\nboom"
    near_duplicate = "File a.py\nline 10\nboom\nextra context"
    different_type_same_trace = "File a.py\nline 10\nboom"

    store_sample(mgr, module, "payload-1", crash_type="ValueError", trace=common_trace)
    store_sample(mgr, module, "payload-2", crash_type="ValueError", trace=near_duplicate)
    store_sample(mgr, module, "payload-3", crash_type="TypeError", trace=different_type_same_trace)

    assert mgr.deduplicate_similar(threshold=0.7) == 1
    remaining = {crash.payload_data for crash in mgr.list_crashes()}
    assert len(remaining & {"payload-1", "payload-2"}) == 1
    assert "payload-3" in remaining
    assert module.FuzzCorpusManager._jaccard("a\nb", "b\nc") == 1 / 3
    assert module.FuzzCorpusManager._jaccard("", "b") == 0.0
