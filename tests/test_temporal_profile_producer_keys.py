"""Regression: extract_temporal_profile must read the keys the fingerprint
producers (fingerprint_checks.py) actually emit.

The real miner builds its attestation payload as
    {"checks": validate_all_checks()...}
where each check's ``data`` uses:
    thermal_drift      -> drift_ratio   (NOT "variance")
    instruction_jitter -> int_stdev/int_avg_ns  (NOT "cv"/"stddev_ns")
    cache_timing       -> l2_l1_ratio   (NOT "hierarchy_ratio")

Before the fix, extract_temporal_profile read variance/cv/hierarchy_ratio, so
thermal_variance, jitter_cv and cache_hierarchy_ratio were 0.0 for every real
attestation. validate_temporal_consistency scores any metric with <3 non-zero
samples a perfect 1.0, so three of the four TEMPORAL_DRIFT_BANDS were silently
skipped and the anti-spoofing detector ran on clock_drift_cv alone.
"""

import integrated_node


def _producer_fp(drift_ratio, int_avg_ns, int_stdev, l2_l1_ratio, cv=0.02):
    """A fingerprint shaped exactly like miners/*/*.py send it."""
    return {
        "checks": {
            "clock_drift": {"data": {"cv": cv}},
            "thermal_drift": {"data": {"drift_ratio": drift_ratio}},
            "instruction_jitter": {
                "data": {"int_avg_ns": int_avg_ns, "int_stdev": int_stdev}
            },
            "cache_timing": {"data": {"l2_l1_ratio": l2_l1_ratio}},
        }
    }


def test_profile_populates_from_producer_keys():
    prof = integrated_node.extract_temporal_profile(
        _producer_fp(drift_ratio=1.18, int_avg_ns=800, int_stdev=40, l2_l1_ratio=3.2)
    )
    # clock always worked; the other three must no longer be silently zero.
    assert prof["clock_drift_cv"] > 0
    assert prof["thermal_variance"] > 0, "thermal band read from producer drift_ratio"
    assert prof["jitter_cv"] > 0, "jitter band derived from int_stdev/int_avg_ns"
    assert prof["cache_hierarchy_ratio"] > 0, "cache band read from producer l2_l1_ratio"
    # jitter_cv must be the coefficient of variation stdev/avg = 40/800 = 0.05
    assert abs(prof["jitter_cv"] - 0.05) < 1e-6


def test_frozen_fingerprint_replay_flagged_on_all_bands():
    """A replayed/frozen fingerprint (identical thermal/jitter/cache readings on
    every attestation) is a spoofing signal the temporal detector is meant to
    catch via its ``frozen_profile`` rule. Before the fix these three bands read
    a constant 0.0, were filtered out (v>0) and skipped with a perfect 1.0 score,
    so a frozen profile could never be flagged on them. After the fix the real
    producer values feed the bands, the frozen rule fires, and each drops to 0.2.
    """
    seq = []
    for i in range(5):
        prof = integrated_node.extract_temporal_profile(
            # identical producer readings every attestation -> frozen profile
            _producer_fp(drift_ratio=1.18, int_avg_ns=800, int_stdev=40, l2_l1_ratio=3.2)
        )
        seq.append({"ts": i + 1, "profile": prof})

    review = integrated_node.validate_temporal_consistency(seq)
    scores = review["check_scores"]
    for band in ("thermal_variance", "jitter_cv", "cache_hierarchy_ratio"):
        # skipped bands score exactly 1.0; an evaluated frozen band scores <=0.2
        assert scores.get(band, 1.0) < 1.0, f"{band} must be evaluated, not skipped"
        assert f"frozen_profile:{band}" in review["flags"]
    assert review["review_flag"] is True
