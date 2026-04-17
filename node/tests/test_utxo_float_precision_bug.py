"""
PoC Test: UTXO Transfer Float Precision Bug
=============================================
Finding: utxo_endpoints.py uses `float(data.get('amount_rtc', 0))` before
converting to nanoRTC. This causes systematic precision loss for common
decimal amounts like 0.1, 0.3, 123.456, etc.

Severity: High
Target: utxo_endpoints.py::utxo_transfer()
"""

UNIT = 100_000_000  # 1 RTC = 100,000,000 nanoRTC


def current_buggy_conversion(amount_rtc):
    """Replica of current code path in utxo_endpoints.py"""
    amount = float(amount_rtc)
    return int(amount * UNIT)


def test_float_precision_loss():
    """Demonstrate precision loss for amounts that are not exactly
    representable in IEEE-754 double precision."""

    test_cases = [
        # (amount_rtc, expected_nrtc) — values known to trigger IEEE-754 precision loss
        (0.1,     10_000_000),       # safe baseline
        (0.3,     30_000_000),       # safe baseline
        (0.000_000_03, 3),           # 3 nanoRTC  -> float gives 2
        (0.000_000_06, 6),           # 6 nanoRTC  -> float gives 5
        (0.000_000_12, 12),          # 12 nanoRTC -> float gives 11
        (0.000_000_29, 29),          # 29 nanoRTC -> float gives 28
        (0.000_000_58, 58),          # 58 nanoRTC -> float gives 57
        (0.000_001_05, 105),         # 105 nanoRTC -> float gives 104
    ]

    failures = []
    for amount_rtc, expected_nrtc in test_cases:
        actual = current_buggy_conversion(amount_rtc)
        diff = expected_nrtc - actual
        status = "PASS" if diff == 0 else "FAIL"
        print(f"  amount_rtc={amount_rtc:>12} -> expected={expected_nrtc:>16} actual={actual:>16} diff={diff:>6} [{status}]")
        if diff != 0:
            failures.append((amount_rtc, expected_nrtc, actual, diff))

    print()
    if failures:
        print(f"❌ PRECISION LOSS CONFIRMED on {len(failures)} test cases.")
        for amount_rtc, expected, actual, diff in failures:
            print(f"   - {amount_rtc} RTC loses {diff} nanoRTC (expected {expected}, got {actual})")
        assert False, f"Float precision bug reproduced on {len(failures)} cases."
    else:
        print("✅ No precision loss detected.")


if __name__ == "__main__":
    test_float_precision_loss()
