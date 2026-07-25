# SPDX-License-Identifier: MIT
"""Corpus and property regressions for device classification.

The fixture records device strings from immutable, public hardware inventories.
These tests exercise the production ``derive_verified_device`` function rather
than duplicating its classification logic.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st


NODE = sys.modules["integrated_node"]
CORPUS_PATH = Path(__file__).with_name("device_classification_corpus.json")
PINNED_GITHUB_URL = re.compile(
    r"^https://github\.com/[^/]+/[^/]+/(?:blob|tree)/[0-9a-f]{40}/.+$"
)


def _load_corpus() -> list[dict]:
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))


CORPUS = _load_corpus()


def _classify(device: dict, fingerprint: object = None, passed: bool = True) -> dict:
    return NODE.derive_verified_device(device, fingerprint or {}, passed)


def test_corpus_has_at_least_thirty_cited_unique_devices():
    """The regression input must remain reviewable, immutable, and substantial."""
    assert len(CORPUS) >= 30
    assert len({row["id"] for row in CORPUS}) == len(CORPUS)
    assert len({json.dumps(row["device"], sort_keys=True) for row in CORPUS}) == len(CORPUS)
    for row in CORPUS:
        assert row["provenance"]
        assert PINNED_GITHUB_URL.fullmatch(row["source"]), row["source"]
        assert set(row["expected"]) == {"device_family", "device_arch"}


@pytest.mark.parametrize("sample", CORPUS, ids=lambda sample: sample["id"])
def test_cited_device_classification_corpus(sample):
    assert _classify(sample["device"]) == sample["expected"]


@pytest.mark.parametrize(
    ("cpu", "expected_arch"),
    [
        ("Intel Pentium 166", "modern"),
        ("Intel Pentium Pro 200", "pentium_pro"),
        ("Intel Pentium II 450", "pentium_ii"),
        ("Intel Pentium III 933", "pentium_iii"),
        ("Intel Pentium MMX 233", "pentium_mmx"),
        ("Intel Pentium M processor 1600MHz", "pentium_m_banias"),
        ("Intel Pentium 4 2.40GHz", "modern"),
    ],
)
def test_pentium_name_boundaries_do_not_overlap(cpu, expected_arch):
    device = {"family": "x86", "arch": "modern", "machine": "i686", "cpu": cpu}
    assert _classify(device)["device_arch"] == expected_arch


def _hardware_weight(classification: dict) -> float:
    family = classification["device_family"]
    arch = classification["device_arch"]
    family_weights = NODE.HARDWARE_WEIGHTS.get(family, {})
    return float(family_weights.get(arch, family_weights.get("default", 1.0)))


@pytest.mark.parametrize(
    ("device", "expected"),
    [
        (
            {"family": "x86", "arch": "modern"},
            {"device_family": "ARM", "device_arch": "aarch64"},
        ),
        (
            {
                "family": "x86_64",
                "arch": "modern",
                "machine": "aarch64",
                "cpu": "Intel Core i7-12700K",
            },
            {"device_family": "ARM", "device_arch": "aarch64"},
        ),
    ],
)
def test_spoof_shaped_payloads_are_not_vintage(device, expected):
    result = _classify(device, {}, False)
    assert result == expected
    assert _hardware_weight(result) <= 1.0


def test_mixed_legacy_and_new_field_names_use_current_identity_fields():
    """Cover the mixed-schema trap tracked in Rustchain#7991."""
    device = {
        "device_family": "x86_64",
        "family": "PowerPC",
        "device_arch": "modern",
        "arch": "g4",
        "machine": "x86_64",
        "cpu": "Intel Core i7-12700K",
        "cpu_brand": "PowerPC G4 7450",
    }
    fingerprint = {
        "checks": {
            "thermal_drift": {
                "passed": True,
                "data": {"ratio": 1.0, "drift_ratio": 1.2},
            },
            "cache_timing": {
                "passed": True,
                "data": {"L1": 5.0, "l1_ns": 5.1, "l2_l1_ratio": 2.8},
            },
            "instruction_jitter": {
                "passed": True,
                "data": {"cv": 0.1, "int_avg_ns": 9100, "int_stdev": 40},
            },
        }
    }
    assert _classify(device, fingerprint) == {
        "device_family": "x86_64",
        "device_arch": "modern",
    }


@pytest.mark.parametrize(
    "cpu",
    [
        "Intel Core i7 \N{SNOWMAN} \x00 Pentium III",
        "A" * 16_384,
        "\x00" * 128,
    ],
)
def test_unicode_oversized_and_null_byte_fields_never_raise(cpu):
    result = _classify(
        {"family": "x86_64", "arch": "modern", "machine": "x86_64", "cpu": cpu},
        {},
        False,
    )
    assert set(result) == {"device_family", "device_arch"}
    assert all(isinstance(value, str) for value in result.values())


@pytest.mark.xfail(
    reason=(
        "Modern family-6 brand injection is the core fix tracked by "
        "https://github.com/Scottcjn/rustchain-bounties/issues/16271"
    ),
    strict=False,
)
def test_modern_family6_with_pentium_iii_injection_cannot_gain_vintage_weight():
    device = {
        "family": "x86_64",
        "arch": "modern",
        "machine": "x86_64",
        "cpu": "Intel Core i7 family 6 model 158 Pentium III",
        "cpu_family": "6",
    }
    assert _hardware_weight(_classify(device, {}, False)) <= 1.0


@pytest.mark.xfail(
    reason=(
        "Uncorroborated vintage reward claims are tracked by "
        "https://github.com/Scottcjn/rustchain-bounties/issues/16271"
    ),
    strict=False,
)
@settings(max_examples=40, deadline=None, derandomize=True)
@given(
    claimed_arch=st.sampled_from(
        ["386", "486", "pentium", "pentium_mmx", "pentium_ii", "pentium_iii"]
    ),
    cpu=st.sampled_from(
        ["Intel Core i7-12700K", "AMD Ryzen 9 5950X", "Intel Xeon Gold 6248R"]
    ),
)
def test_no_vintage_multiplier_without_positive_vintage_evidence(claimed_arch, cpu):
    device = {
        "family": "x86",
        "arch": claimed_arch,
        "machine": "x86_64",
        "cpu": cpu,
        "cpu_family": "6",
    }
    fingerprint = {
        "checks": {
            "simd_identity": {
                "passed": True,
                "data": {
                    "has_sse": True,
                    "has_avx": True,
                    "x86_features": ["sse2", "avx2"],
                },
            }
        }
    }
    assert _hardware_weight(_classify(device, fingerprint, True)) <= 1.0


JSON_SCALAR = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**31), max_value=2**31 - 1),
    st.floats(allow_nan=True, allow_infinity=True, width=32),
    st.text(max_size=80),
)
JSONISH = st.recursive(
    JSON_SCALAR,
    lambda children: st.one_of(
        st.lists(children, max_size=4),
        st.dictionaries(st.text(max_size=20), children, max_size=4),
    ),
    max_leaves=12,
)
DEVICE_KEYS = st.sampled_from(
    [
        "device_family",
        "family",
        "device_arch",
        "arch",
        "machine",
        "cpu",
        "model",
        "device_model",
        "brand",
        "platform_system",
    ]
)


@settings(
    max_examples=120,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(
    device=st.dictionaries(DEVICE_KEYS, JSONISH, max_size=10),
    fingerprint=JSONISH,
    passed=st.booleans(),
)
def test_bounded_malformed_payloads_never_raise(device, fingerprint, passed):
    """Untrusted nested values must resolve to a string-valued classification."""
    result = _classify(device, fingerprint, passed)
    assert set(result) == {"device_family", "device_arch"}
    assert all(isinstance(value, str) for value in result.values())


@settings(max_examples=60, deadline=None, derandomize=True)
@given(
    sample=st.sampled_from(CORPUS),
    hostname=st.text(max_size=50),
    cores=st.integers(min_value=0, max_value=4096),
    ram_mb=st.integers(min_value=0, max_value=2**31 - 1),
)
def test_unrelated_inventory_metadata_does_not_change_classification(
    sample, hostname, cores, ram_mb
):
    enriched = dict(sample["device"], hostname=hostname, cores=cores, ram_mb=ram_mb)
    assert _classify(enriched) == sample["expected"]

